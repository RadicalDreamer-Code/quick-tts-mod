"""Main window: drag-and-drop image -> OCR text -> TTS playback."""

import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import ocr_claude
import ocr_local
import tts_engine

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".gif"}


class Worker(QThread):
    """Runs a callable off the UI thread and reports back via signals."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user via the signal
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)


class DropArea(QLabel):
    imageDropped = Signal(str)

    def __init__(self):
        super().__init__("Drop an image here")
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setMinimumHeight(200)
        self.setStyleSheet(
            "QLabel { border: 2px dashed #888; border-radius: 8px; color: #888; }"
        )

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            ext = os.path.splitext(path)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                self.imageDropped.emit(path)
                return

    def show_image(self, path: str):
        pixmap = QPixmap(path)
        self.setPixmap(
            pixmap.scaled(
                self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quick TTS")
        self.resize(600, 500)

        self.current_image_path: str | None = None
        self._worker: Worker | None = None

        self.drop_area = DropArea()
        self.drop_area.imageDropped.connect(self.on_image_dropped)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Extracted text will appear here — feel free to edit it before speaking.")

        self.reocr_button = QPushButton("Re-OCR with Claude")
        self.reocr_button.setEnabled(False)
        self.reocr_button.clicked.connect(self.on_reocr_claude)

        self.speak_button = QPushButton("Speak")
        self.speak_button.clicked.connect(self.on_speak)

        self.save_button = QPushButton("Save audio…")
        self.save_button.clicked.connect(self.on_save_audio)

        if not ocr_claude.available():
            self.reocr_button.setToolTip(
                "Set the ANTHROPIC_API_KEY environment variable to enable this."
            )

        button_row = QHBoxLayout()
        button_row.addWidget(self.reocr_button)
        button_row.addWidget(self.speak_button)
        button_row.addWidget(self.save_button)

        layout = QVBoxLayout()
        layout.addWidget(self.drop_area)
        layout.addWidget(self.text_edit)
        layout.addLayout(button_row)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.statusBar().showMessage("Ready")

    def _run_async(self, fn, on_success, *args, **kwargs):
        self._worker = Worker(fn, *args, **kwargs)
        self._worker.succeeded.connect(on_success)
        self._worker.failed.connect(self.on_error)
        self._worker.start()

    def _set_busy(self, busy: bool, message: str = ""):
        for widget in (self.reocr_button, self.speak_button, self.save_button):
            widget.setEnabled(not busy and self._widget_should_be_enabled(widget))
        if message:
            self.statusBar().showMessage(message)

    def _widget_should_be_enabled(self, widget) -> bool:
        if widget is self.reocr_button:
            return ocr_claude.available() and self.current_image_path is not None
        return True

    def on_image_dropped(self, path: str):
        self.current_image_path = path
        self.drop_area.show_image(path)
        self.reocr_button.setEnabled(ocr_claude.available())
        self._set_busy(True, "Reading text locally…")
        self._run_async(ocr_local.extract_text, self.on_ocr_done, path)

    def on_reocr_claude(self):
        if not self.current_image_path:
            return
        self._set_busy(True, "Asking Claude to read the image…")
        self._run_async(ocr_claude.extract_text, self.on_ocr_done, self.current_image_path)

    def on_ocr_done(self, text: str):
        self.text_edit.setPlainText(text)
        self._set_busy(False, "Done" if text else "No text found")

    def on_speak(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        self._set_busy(True, "Synthesizing speech…")
        self._run_async(tts_engine.speak, lambda _: self._set_busy(False, "Done"), text)

    def on_save_audio(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        out_path, _ = QFileDialog.getSaveFileName(self, "Save audio", "speech.wav", "WAV files (*.wav)")
        if not out_path:
            return
        self._set_busy(True, "Synthesizing speech…")
        self._run_async(
            tts_engine.save,
            lambda _: self._set_busy(False, f"Saved to {out_path}"),
            text,
            out_path,
        )

    def on_error(self, message: str):
        self._set_busy(False, "Error")
        QMessageBox.critical(self, "Error", message)
