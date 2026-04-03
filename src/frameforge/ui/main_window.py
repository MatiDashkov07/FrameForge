"""
main_window.py — FrameForge main application window.

Phase 0: skeleton layout only. No real functionality yet.
This file owns the top-level window, menu bar, splitter layout, and status bar.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QSplitter,
    QVBoxLayout,
    QLabel,
    QFrame,
    QStatusBar,
    QMenuBar,
    QMenu,
    QSizePolicy,
)
from PySide6.QtGui import QAction


class MainWindow(QMainWindow):
    """Top-level application window for FrameForge."""

    WINDOW_TITLE = "FrameForge"
    DEFAULT_WIDTH = 1280
    DEFAULT_HEIGHT = 800

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        self._build_menu_bar()
        self._build_central_widget()
        self._build_status_bar()

    # ------------------------------------------------------------------ #
    # Menu bar                                                             #
    # ------------------------------------------------------------------ #

    def _build_menu_bar(self) -> None:
        """
        Top menu bar with File and Help menus.
        Phase 1+: File → Open Sketch, Save Project, Export Frame, etc.
        """
        menu_bar: QMenuBar = self.menuBar()

        # File menu — will hold open/save/export actions in Phase 1
        file_menu: QMenu = menu_bar.addMenu("&File")
        file_menu.addAction(QAction("Open Sketch…", self))
        file_menu.addAction(QAction("Open Reference Sheet…", self))
        file_menu.addSeparator()
        file_menu.addAction(QAction("Export Frame…", self))
        file_menu.addSeparator()
        file_menu.addAction(QAction("Exit", self))

        # Help menu — will link to docs/changelog in a later phase
        help_menu: QMenu = menu_bar.addMenu("&Help")
        help_menu.addAction(QAction("About FrameForge", self))
        help_menu.addAction(QAction("Documentation", self))

    # ------------------------------------------------------------------ #
    # Central widget: sidebar + canvas                                     #
    # ------------------------------------------------------------------ #

    def _build_central_widget(self) -> None:
        """
        Main layout: horizontal QSplitter with a left sidebar and a central
        canvas area.

        Sidebar (fixed ~280 px at start) holds three collapsible sections:
          • Sketch Input   — Phase 1: drag-and-drop sketch upload
          • References     — Phase 1: reference sheet thumbnails
          • Prompt         — Phase 1: text prompt for CLIP conditioning

        Canvas (fills remaining space):
          • Phase 1: displays the rendered frame returned by the AI pipeline
          • Phase 3: replaced by the full timeline + scrubber widget
        """
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        # Left sidebar
        sidebar = self._build_sidebar()
        splitter.addWidget(sidebar)

        # Central canvas
        canvas = self._build_canvas()
        splitter.addWidget(canvas)

        # Give sidebar ~280 px and let the canvas take the rest
        splitter.setSizes([280, self.DEFAULT_WIDTH - 280])
        splitter.setStretchFactor(0, 0)  # sidebar: don't stretch
        splitter.setStretchFactor(1, 1)  # canvas: stretches with window

        self.setCentralWidget(splitter)

    def _build_sidebar(self) -> QWidget:
        """
        Left panel containing the three input sections.
        Each section is a placeholder frame that will be replaced with a
        dedicated widget in Phase 1.
        """
        sidebar = QWidget()
        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(400)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # -- Sketch Input section --
        # Phase 1: replaced by a drag-and-drop zone that accepts PNG/JPEG/PSD.
        # The uploaded sketch is fed into ControlNet as the structure signal.
        layout.addWidget(self._section_frame(
            title="Sketch Input",
            body="Drop a line-art sketch here.\n(PNG / JPEG / PSD)",
        ))

        # -- References section --
        # Phase 1: replaced by a thumbnail grid for reference sheets.
        # Images are encoded by IP-Adapter to extract palette, style, identity.
        layout.addWidget(self._section_frame(
            title="References",
            body="Drop character / style reference\nimages here.",
        ))

        # -- Prompt section --
        # Phase 1: replaced by a QTextEdit + token counter.
        # Text is encoded by CLIP and passed as the third conditioning signal.
        layout.addWidget(self._section_frame(
            title="Prompt",
            body="Describe the scene, lighting,\nor style here.",
        ))

        # Push all sections to the top
        layout.addStretch()

        return sidebar

    def _build_canvas(self) -> QWidget:
        """
        Central area that will display the rendered output frame.
        Phase 1: replaced by a before/after comparison widget (QStackedWidget).
        Phase 3: replaced by the full timeline + scrubber.
        """
        canvas = QWidget()
        layout = QVBoxLayout(canvas)
        layout.setContentsMargins(0, 0, 0, 0)

        placeholder = QLabel("Your rendered frame will appear here")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        placeholder.setStyleSheet(
            "color: #888888; font-size: 16px; background-color: #1e1e1e;"
        )

        layout.addWidget(placeholder)
        return canvas

    # ------------------------------------------------------------------ #
    # Status bar                                                           #
    # ------------------------------------------------------------------ #

    def _build_status_bar(self) -> None:
        """
        Bottom status bar.
        Phase 1+: will show render progress, API status, and frame count.
        """
        bar = QStatusBar()
        bar.showMessage("Ready")
        self.setStatusBar(bar)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _section_frame(title: str, body: str) -> QFrame:
        """
        Returns a titled placeholder section for the sidebar.
        Each frame will be replaced by a proper widget in Phase 1.
        """
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title_label = QLabel(f"<b>{title}</b>")
        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        body_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(title_label)
        layout.addWidget(body_label)

        return frame
