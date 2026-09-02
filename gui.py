"""Main window: drag-and-drop image -> OCR text -> TTS playback."""

import os
import tempfile

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QImage,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
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

import ocr_ollama
import tts_engine

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".gif"}


class Worker(QThread):
    """Runs a callable off the UI thread and reports back via signals."""

    succeeded = Signal(object)
    failed = Signal(str)
    interrupted = Signal()

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
        except tts_engine.Interrupted:
            self.interrupted.emit()
        except Exception as exc:  # noqa: BLE001 - surfaced to the user via the signal
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)


class DropArea(QLabel):
    imageDropped = Signal(str)

    def __init__(self):
        super().__init__("Drop an image here, or paste one with Ctrl+V")
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
        self._pasted_image_path: str | None = None
        self._worker: Worker | None = None

        self.drop_area = DropArea()
        self.drop_area.imageDropped.connect(self.load_image)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Extracted text will appear here — feel free to edit it before speaking.")

        self.paste_button = QPushButton("Paste image")
        self.paste_button.setToolTip("Read the image on the clipboard (Ctrl+V)")
        self.paste_button.clicked.connect(self.on_paste)

        paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        paste_shortcut.activated.connect(self.on_paste)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.on_stop)

        self.reocr_button = QPushButton("Re-run OCR")
        self.reocr_button.setEnabled(False)
        self.reocr_button.clicked.connect(self.on_reocr_ollama)

        self.speak_button = QPushButton("Speak")
        self.speak_button.clicked.connect(self.on_speak)

        self.save_button = QPushButton("Save audio…")
        self.save_button.clicked.connect(self.on_save_audio)

        self.backend_combo = QComboBox()
        for name, label in tts_engine.BACKEND_LABELS.items():
            self.backend_combo.addItem(label, userData=name)
        self.backend_combo.setCurrentIndex(self.backend_combo.findData(tts_engine.current_backend()))
        self.backend_combo.currentIndexChanged.connect(self.on_backend_changed)

        if not ocr_ollama.available():
            self.drop_area.setText(
                f"GLM-OCR model not found.\nRun: ollama pull {ocr_ollama.MODEL}"
            )
            self.reocr_button.setToolTip(
                f"Pull the model first: ollama pull {ocr_ollama.MODEL}"
            )

        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("Voice:"))
        voice_row.addWidget(self.backend_combo)
        voice_row.addStretch()

        button_row = QHBoxLayout()
        button_row.addWidget(self.paste_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.reocr_button)
        button_row.addWidget(self.speak_button)
        button_row.addWidget(self.save_button)

        layout = QVBoxLayout()
        layout.addWidget(self.drop_area)
        layout.addWidget(self.text_edit)
        layout.addLayout(voice_row)
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
        for widget in (self.paste_button, self.reocr_button, self.speak_button, self.save_button):
            widget.setEnabled(not busy and self._widget_should_be_enabled(widget))
        self.stop_button.setEnabled(busy)
        self.backend_combo.setEnabled(not busy)
        if message:
            self.statusBar().showMessage(message)

    def _widget_should_be_enabled(self, widget) -> bool:
        if widget is self.reocr_button:
            return ocr_ollama.available() and self.current_image_path is not None
        return True

    def load_image(self, path: str):
        if not ocr_ollama.available():
            QMessageBox.warning(
                self,
                "GLM-OCR not available",
                f"Couldn't reach the '{ocr_ollama.MODEL}' model in Ollama.\n\n"
                f"Make sure Ollama is running and run: ollama pull {ocr_ollama.MODEL}",
            )
            return
        self.current_image_path = path
        self.drop_area.show_image(path)
        self.reocr_button.setEnabled(True)
        self._set_busy(True, "Asking GLM-OCR to read the image…")
        self._run_async(ocr_ollama.extract_text, self.on_ocr_done, path)

    def on_paste(self):
        """Ctrl+V (or the button): an image on the clipboard becomes the current
        image. Anything else falls through to the focused widget's own paste, so
        Ctrl+V still works normally inside the text box."""
        path = self._image_from_clipboard()
        if path is None:
            paste = getattr(QApplication.focusWidget(), "paste", None)
            if callable(paste):
                paste()
            else:
                self.statusBar().showMessage("No image on the clipboard")
            return
        self.load_image(path)

    def _image_from_clipboard(self) -> str | None:
        """Path to the clipboard's image, or None if it doesn't hold one.
        Copied files are used where they are; raw image data is written to a
        temp file, since OCR needs a path."""
        mime = QGuiApplication.clipboard().mimeData()
        if mime is None:
            return None
        for url in mime.urls():
            local = url.toLocalFile()
            if os.path.splitext(local)[1].lower() in IMAGE_EXTENSIONS and os.path.isfile(local):
                return local
        if mime.hasImage():
            image = QGuiApplication.clipboard().image()
            if not image.isNull():
                return self._save_temp_image(image)
        return None

    def _save_temp_image(self, image: QImage) -> str:
        fd, path = tempfile.mkstemp(prefix="quick-tts-paste-", suffix=".png")
        os.close(fd)
        image.save(path, "PNG")
        self._discard_pasted_image()
        self._pasted_image_path = path
        return path

    def _discard_pasted_image(self):
        """Only one pasted image is ever current; drop the previous temp file."""
        if self._pasted_image_path is None:
            return
        try:
            os.remove(self._pasted_image_path)
        except OSError:
            pass
        self._pasted_image_path = None

    def closeEvent(self, event):
        self._discard_pasted_image()
        super().closeEvent(event)

    def on_reocr_ollama(self):
        if not self.current_image_path:
            return
        self._set_busy(True, "Asking GLM-OCR to read the image…")
        self._run_async(ocr_ollama.extract_text, self.on_ocr_done, self.current_image_path)

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

    def on_backend_changed(self, index: int):
        name = self.backend_combo.itemData(index)
        if not tts_engine.available(name):
            QMessageBox.warning(
                self,
                "Voice engine not available",
                f"{tts_engine.BACKEND_LABELS[name]} isn't available right now.\n\n"
                + (
                    "Set ELEVENLABS_API_KEY (e.g. in .env) to enable this."
                    if name == "elevenlabs"
                    else ""
                ),
            )
            self.backend_combo.blockSignals(True)
            self.backend_combo.setCurrentIndex(self.backend_combo.findData(tts_engine.current_backend()))
            self.backend_combo.blockSignals(False)
            return
        tts_engine.set_backend(name)
        self.statusBar().showMessage(f"Voice engine: {tts_engine.BACKEND_LABELS[name]}")

    def on_stop(self):
        """Interrupt whatever's running (OCR call or speech synthesis/playback)
        and reset the UI so a new action can start right away."""
        tts_engine.interrupt()
        if self._worker is not None:
            for signal in (self._worker.succeeded, self._worker.failed):
                try:
                    signal.disconnect()
                except (RuntimeError, TypeError):
                    pass
        self._set_busy(False, "Stopped")
