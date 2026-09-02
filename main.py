import sys

from dotenv import load_dotenv

load_dotenv()

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui import MainWindow  # noqa: E402


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
