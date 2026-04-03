"""
sketch_drop_zone.py — Drag-and-drop (and click-to-browse) widget for sketch input.

Phase 1, Step 1.

Responsibilities:
  - Accept PNG/JPEG via drag-and-drop or click-to-browse
  - Validate file type before accepting
  - Display a thumbnail of the accepted file
  - Emit sketch_loaded(str) signal so MainWindow can update app state

This widget knows nothing about the pipeline or the render button.
It only knows: "a file was chosen — here is the path."
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# File types this widget will accept. Checked against the dropped file's suffix.
ACCEPTED_SUFFIXES = {".png", ".jpg", ".jpeg"}


class SketchDropZone(QWidget):
    """
    A bordered zone that accepts a single sketch image (PNG or JPEG).

    Signals:
        sketch_loaded(str): Emitted when a valid file is accepted.
                            Carries the absolute file path as a str.
                            MainWindow listens to this and stores a Path object.
    """

    sketch_loaded = Signal(str)

    # ------------------------------------------------------------------ #
    # Construction                                                         #
    # ------------------------------------------------------------------ #

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setAcceptDrops(True)           # tell Qt this widget handles drops
        self.setMinimumHeight(160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)  # hint: clickable

        self._build_ui()
        self._set_idle_style()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Single label — switches between instruction text and thumbnail.
        self._label = QLabel("Drop sketch here\nor click to browse\n(PNG / JPEG)")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        layout.addWidget(self._label)

    # ------------------------------------------------------------------ #
    # Visual states                                                        #
    # ------------------------------------------------------------------ #

    def _set_idle_style(self) -> None:
        """Default appearance: dashed border, muted text."""
        self.setStyleSheet("""
            SketchDropZone {
                border: 2px dashed #555555;
                border-radius: 6px;
                background-color: #2a2a2a;
            }
        """)
        # Only reset text if no file has been loaded yet (don't clobber thumbnail)
        if not self._label.pixmap():
            self._label.setStyleSheet("color: #888888; font-size: 11px;")

    def _set_hover_style(self) -> None:
        """Highlighted appearance while a valid file is being dragged over."""
        self.setStyleSheet("""
            SketchDropZone {
                border: 2px solid #4a9eff;
                border-radius: 6px;
                background-color: #1a2a3a;
            }
        """)

    def _set_reject_style(self) -> None:
        """Red border when an unsupported file type is dragged over."""
        self.setStyleSheet("""
            SketchDropZone {
                border: 2px solid #cc3333;
                border-radius: 6px;
                background-color: #2a1a1a;
            }
        """)

    # ------------------------------------------------------------------ #
    # Drag & drop event handlers                                           #
    # ------------------------------------------------------------------ #

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """
        Qt calls this as soon as the user drags something over the widget.
        We decide here whether to accept or ignore the drag.

        event.mimeData().hasUrls() is True when files are being dragged.
        We peek at the first URL's suffix to decide if it's a supported type.
        """
        if event.mimeData().hasUrls():
            path = Path(event.mimeData().urls()[0].toLocalFile())
            if path.suffix.lower() in ACCEPTED_SUFFIXES:
                event.acceptProposedAction()  # green light — we'll handle this
                self._set_hover_style()
                return

        # Unsupported type — show red and ignore
        self._set_reject_style()
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001
        """User dragged out without dropping — restore normal appearance."""
        self._set_idle_style()

    def dropEvent(self, event: QDropEvent) -> None:
        """
        Qt calls this when the user releases the mouse over the widget
        after a successful dragEnterEvent.

        We extract the file path from the first URL and load it.
        """
        self._set_idle_style()
        path = Path(event.mimeData().urls()[0].toLocalFile())
        self._load_file(path)

    # ------------------------------------------------------------------ #
    # Click-to-browse                                                      #
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Open a file dialog when the user clicks the zone."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_file_dialog()

    def _open_file_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Sketch",
            "",                                      # start dir — OS default
            "Images (*.png *.jpg *.jpeg)",           # filter shown in dialog
        )
        if path_str:                                 # empty str = user cancelled
            self._load_file(Path(path_str))

    # ------------------------------------------------------------------ #
    # File loading                                                         #
    # ------------------------------------------------------------------ #

    def _load_file(self, path: Path) -> None:
        """
        Validate, display thumbnail, and emit signal.
        Called by both drop and click-to-browse paths.
        """
        if path.suffix.lower() not in ACCEPTED_SUFFIXES:
            # Shouldn't normally reach here (dialog filter + dragEnter guard),
            # but defensive programming is good practice.
            self._label.setText("Unsupported file type.\nPNG or JPEG only.")
            self._label.setStyleSheet("color: #cc3333; font-size: 11px;")
            return

        # Build a thumbnail that fits inside the widget's label area
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._label.setText("Could not read image.")
            self._label.setStyleSheet("color: #cc3333; font-size: 11px;")
            return

        scaled = pixmap.scaled(
            self._label.width(),
            self._label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label.setPixmap(scaled)

        # Tell MainWindow a file was chosen. We emit str because Qt signals
        # don't natively carry pathlib.Path objects (Qt is C++ under the hood).
        # MainWindow will convert back to Path immediately on receipt.
        self.sketch_loaded.emit(str(path))