"""
reference_drop_zone.py — Drag-and-drop zone for reference images (Phase 2, Step 1).

Accepts up to 3 PNG/JPEG reference images via drag-and-drop or click-to-browse.
Displays a vertical list of thumbnails with remove buttons and a slot counter.
Emits references_changed(list[str]) whenever the loaded set changes.

Structurally mirrors SketchDropZone: same drag/drop plumbing, same visual states,
same signal-only contract with MainWindow. The only difference is multi-file logic.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

ACCEPTED_SUFFIXES = {".png", ".jpg", ".jpeg"}
MAX_REFERENCES = 3


class ReferenceDropZone(QWidget):
    """
    A bordered zone accepting up to 3 reference images (PNG or JPEG).

    Each accepted file is displayed as a thumbnail row (48 px thumbnail +
    truncated filename + × remove button). A counter in the top-right corner
    shows "References: N/3".

    Signals:
        references_changed(list[str]):
            Emitted whenever the loaded set changes — on add or remove.
            Carries the complete current list of absolute file paths.
            MainWindow listens to this and stores the list as reference_paths.
    """

    references_changed = Signal(list)  # list[str]

    # ------------------------------------------------------------------ #
    # Construction                                                         #
    # ------------------------------------------------------------------ #

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._paths: list[str] = []

        self.setAcceptDrops(True)
        self.setMinimumHeight(200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._build_ui()
        self._set_idle_style()
        self._refresh_display()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Counter: "References: 0/3" — right-aligned at top
        self._counter_label = QLabel(f"References: 0/{MAX_REFERENCES}")
        self._counter_label.setStyleSheet("font-size: 11px; color: #aaaaaa;")
        self._counter_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._counter_label)

        # Scroll area containing the thumbnail rows.
        # Hidden when no files are loaded; content rebuilt on every change.
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background-color: transparent;")

        self._list_container = QWidget()
        self._list_container.setStyleSheet("background-color: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._scroll.setWidget(self._list_container)
        layout.addWidget(self._scroll, 1)

        # Status / instruction label — shown when empty or on overflow warning
        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

    # ------------------------------------------------------------------ #
    # Display state                                                        #
    # ------------------------------------------------------------------ #

    def _refresh_display(self) -> None:
        """Rebuild the thumbnail list and update the counter and status label."""
        # Remove all existing thumbnail rows
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        count = len(self._paths)
        self._counter_label.setText(f"References: {count}/{MAX_REFERENCES}")

        if count == 0:
            self._scroll.hide()
            self._status_label.setText(
                "Drop reference images here\nor click to browse\n(PNG / JPEG, up to 3)"
            )
            self._status_label.setStyleSheet("color: #888888; font-size: 11px;")
            self._status_label.show()
        else:
            for i, path_str in enumerate(self._paths):
                self._list_layout.addWidget(self._build_thumbnail_row(i, path_str))
            self._scroll.show()

            remaining = MAX_REFERENCES - count
            if remaining > 0:
                slot_word = "slot" if remaining == 1 else "slots"
                self._status_label.setText(f"{remaining} {slot_word} remaining — drop to add")
                self._status_label.setStyleSheet("color: #666666; font-size: 10px;")
                self._status_label.show()
            else:
                self._status_label.hide()

    def _build_thumbnail_row(self, index: int, path_str: str) -> QWidget:
        """Build one thumbnail row: 64 px thumb + filename + × remove button."""
        row = QWidget()
        row.setStyleSheet(
            "QWidget { background-color: #333333; border-radius: 4px; }"
        )
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 4, 4, 4)
        row_layout.setSpacing(6)

        # Thumbnail (64×64, aspect-ratio preserved)
        thumb_label = QLabel()
        thumb_label.setFixedSize(64, 64)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(path_str)
        if not pixmap.isNull():
            thumb_label.setPixmap(
                pixmap.scaled(
                    64, 64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        row_layout.addWidget(thumb_label)

        # Filename — truncated to fit the narrow sidebar
        name = Path(path_str).name
        if len(name) > 22:
            name = name[:19] + "…"
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 10px; color: #cccccc; background: transparent;")
        name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row_layout.addWidget(name_label)

        # Remove button — uses a default-arg capture to freeze the loop index
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(22, 22)
        remove_btn.setStyleSheet(
            "QPushButton { background-color: transparent; border: none;"
            " color: #777777; font-size: 14px; }"
            "QPushButton:hover { color: #cc3333; }"
        )
        remove_btn.clicked.connect(lambda _checked=False, i=index: self._remove_file(i))
        row_layout.addWidget(remove_btn)

        return row

    # ------------------------------------------------------------------ #
    # Visual states                                                        #
    # ------------------------------------------------------------------ #

    def _set_idle_style(self) -> None:
        self.setStyleSheet("""
            ReferenceDropZone {
                border: 2px dashed #555555;
                border-radius: 6px;
                background-color: #2a2a2a;
            }
        """)

    def _set_hover_style(self) -> None:
        self.setStyleSheet("""
            ReferenceDropZone {
                border: 2px solid #4a9eff;
                border-radius: 6px;
                background-color: #1a2a3a;
            }
        """)

    def _set_reject_style(self) -> None:
        self.setStyleSheet("""
            ReferenceDropZone {
                border: 2px solid #cc3333;
                border-radius: 6px;
                background-color: #2a1a1a;
            }
        """)

    # ------------------------------------------------------------------ #
    # Drag & drop event handlers                                           #
    # ------------------------------------------------------------------ #

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept if at least one dragged URL is a supported image type."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).suffix.lower() in ACCEPTED_SUFFIXES:
                    event.acceptProposedAction()
                    self._set_hover_style()
                    return
        self._set_reject_style()
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001
        self._set_idle_style()

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_idle_style()
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if Path(url.toLocalFile()).suffix.lower() in ACCEPTED_SUFFIXES
        ]
        self._add_files(paths)

    # ------------------------------------------------------------------ #
    # Click-to-browse                                                      #
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Open a multi-file dialog when the user clicks the zone."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_file_dialog()

    def _open_file_dialog(self) -> None:
        path_strs, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Reference Images",
            "",
            "Images (*.png *.jpg *.jpeg)",
        )
        if path_strs:
            self._add_files([Path(p) for p in path_strs])

    # ------------------------------------------------------------------ #
    # File management                                                      #
    # ------------------------------------------------------------------ #

    def _add_files(self, paths: list[Path]) -> None:
        """
        Add new files to the loaded set, up to MAX_REFERENCES.

        Deduplicates against already-loaded paths. If the batch would exceed
        the cap, the overflow files are dropped and a warning is shown.
        """
        # Skip already-loaded paths (dedup by str comparison)
        new_paths = [str(p) for p in paths if str(p) not in self._paths]
        if not new_paths:
            return

        available = MAX_REFERENCES - len(self._paths)
        if available == 0:
            # All slots full — show a persistent message
            self._status_label.setText(
                "Max 3 references reached. Remove one to add another."
            )
            self._status_label.setStyleSheet("color: #cc3333; font-size: 10px;")
            self._status_label.show()
            return

        rejected = max(0, len(new_paths) - available)
        accepted = new_paths[:available]
        self._paths.extend(accepted)
        self._refresh_display()

        if rejected:
            # Refresh wrote the "N slots remaining" message; overwrite it with
            # a more informative overflow warning.
            self._status_label.setText(
                f"{rejected} file{'s' if rejected != 1 else ''} not added"
                f" — max {MAX_REFERENCES} references reached."
            )
            self._status_label.setStyleSheet("color: #cc7700; font-size: 10px;")
            self._status_label.show()

        self.references_changed.emit(list(self._paths))

    def _remove_file(self, index: int) -> None:
        """Remove the file at the given index, refresh display, emit signal."""
        if 0 <= index < len(self._paths):
            self._paths.pop(index)
            self._refresh_display()
            self.references_changed.emit(list(self._paths))
