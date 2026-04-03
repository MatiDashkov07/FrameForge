"""
main.py — FrameForge application entry point.

Run from the project root:
    python main.py

The venv must be activated first:
    .venv\\Scripts\\activate   (Windows)
    source .venv/bin/activate  (macOS / Linux)
"""

import sys

from PySide6.QtWidgets import QApplication

from frameforge.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("FrameForge")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
