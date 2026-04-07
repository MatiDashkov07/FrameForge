"""
main_window.py — FrameForge main application window.

Phase 1, Step 6: Prompt QTextEdit and strength sliders replace placeholders.
"""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QFrame,
    QMainWindow,
    QMenu,
    QMenuBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QAction, QColor, QImage, QPainter, QPixmap

from frameforge.ui.sketch_drop_zone import SketchDropZone
from frameforge.ui.reference_drop_zone import ReferenceDropZone
from frameforge.ui.render_worker import RenderWorker
from frameforge.ui.bg_removal_worker import BgRemovalWorker

# Canvas page indices — used with self._canvas_stack.setCurrentIndex()
_PAGE_PLACEHOLDER = 0
_PAGE_LOADING = 1
_PAGE_RESULT = 2
_PAGE_REFERENCES = 3  # full-canvas reference management view (Phase 2)

# Stylesheet fragments for the Sketch/Render toggle buttons
_TOGGLE_ACTIVE_STYLE = (
    "QPushButton { background-color: #3a3a3a; border: 1px solid #4a9eff;"
    " border-radius: 3px; padding: 4px 12px; color: #ffffff; }"
)
_TOGGLE_INACTIVE_STYLE = (
    "QPushButton { background-color: transparent; border: 1px solid #555555;"
    " border-radius: 3px; padding: 4px 12px; color: #aaaaaa; }"
)


class MainWindow(QMainWindow):
    """Top-level application window for FrameForge."""

    WINDOW_TITLE = "FrameForge"
    DEFAULT_WIDTH = 1280
    DEFAULT_HEIGHT = 800

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)

        # ── Application state ──────────────────────────────────────────
        # MainWindow is the single source of truth for loaded data.
        # Widgets report here via signals; they don't talk to each other.
        self.sketch_path: Path | None = None        # set by _on_sketch_loaded
        self.reference_paths: list[str] = []        # set by _on_references_changed
        self._last_render: QImage | None = None     # set by _on_result_ready
        self._clear_png: QImage | None = None        # set by _on_bg_result_ready
        self._render_worker: RenderWorker | None = None  # alive during render
        self._bg_worker: BgRemovalWorker | None = None   # alive during bg removal

        self._build_menu_bar()
        self._build_central_widget()
        self._build_status_bar()

    # ------------------------------------------------------------------ #
    # Menu bar                                                             #
    # ------------------------------------------------------------------ #

    def _build_menu_bar(self) -> None:
        menu_bar: QMenuBar = self.menuBar()

        file_menu: QMenu = menu_bar.addMenu("&File")
        file_menu.addAction(QAction("Open Sketch…", self))
        file_menu.addAction(QAction("Open Reference Sheet…", self))
        file_menu.addSeparator()
        file_menu.addAction(QAction("Export Frame…", self))
        file_menu.addSeparator()
        file_menu.addAction(QAction("Exit", self))

        help_menu: QMenu = menu_bar.addMenu("&Help")
        help_menu.addAction(QAction("About FrameForge", self))
        help_menu.addAction(QAction("Documentation", self))

    # ------------------------------------------------------------------ #
    # Central widget                                                        #
    # ------------------------------------------------------------------ #

    def _build_central_widget(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_canvas())

        splitter.setSizes([280, self.DEFAULT_WIDTH - 280])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    # ------------------------------------------------------------------ #
    # Sidebar                                                              #
    # ------------------------------------------------------------------ #

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(400)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # ── Canvas-mode tab buttons ────────────────────────────────────
        # These switch what is shown in the main canvas area.
        # [Sketch Input] → shows the sketch/render stack (pages 0–2).
        # [References]   → shows the full-canvas ReferenceDropZone (page 3).
        layout.addWidget(self._build_sidebar_tabs())

        # ── Sketch Input ───────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Sketch Input</b>"))
        self._sketch_zone = SketchDropZone()
        self._sketch_zone.sketch_loaded.connect(self._on_sketch_loaded)
        layout.addWidget(self._sketch_zone)

        # ── Strength sliders ───────────────────────────────────────────
        # IP-Adapter controls how strongly the style/identity conditioning
        # from reference images is applied (0.0 = ignore, 1.0 = full).
        # ControlNet controls how tightly the output follows the sketch
        # structure (0.0 = loose, 1.0 = strict).
        # Values are stored as integers 0–100 and divided by 100 on read.
        layout.addWidget(self._build_sliders_section())

        # ── Scene direction ────────────────────────────────────────────
        # Natural-language scene context passed to the auto-tagger as user_context.
        # The auto-tagger converts this (plus the sketch) into Danbooru tags.
        # Leave blank to let the auto-tagger decide everything from the sketch alone.
        layout.addWidget(QLabel("<b>Scene Direction</b>"))
        self._prompt_edit = QTextEdit()
        self._prompt_edit.setAcceptRichText(False)
        self._prompt_edit.setFixedHeight(80)
        self._prompt_edit.setPlaceholderText(
            "Scene direction (optional) — e.g. sunset, forest background"
        )
        layout.addWidget(self._prompt_edit)

        layout.addStretch()

        # ── Render button ──────────────────────────────────────────────
        # Disabled until a sketch is loaded. Disabled again during render.
        self._render_btn = QPushButton("Render")
        self._render_btn.setEnabled(False)
        self._render_btn.setMinimumHeight(36)
        self._render_btn.clicked.connect(self._on_render_clicked)
        layout.addWidget(self._render_btn)

        # ── Generate Clear PNG button ──────────────────────────────────
        # Enabled after a render result exists; resets on new render.
        self._generate_clear_btn = QPushButton("Generate Clear PNG")
        self._generate_clear_btn.setEnabled(False)
        self._generate_clear_btn.setMinimumHeight(36)
        self._generate_clear_btn.clicked.connect(self._on_generate_clear_png_clicked)
        layout.addWidget(self._generate_clear_btn)

        # ── Export PNG button ──────────────────────────────────────────
        # Disabled until a render result exists (enabled in _on_result_ready).
        self._export_btn = QPushButton("Export PNG")
        self._export_btn.setEnabled(False)
        self._export_btn.setMinimumHeight(36)
        self._export_btn.clicked.connect(self._on_export_clicked)
        layout.addWidget(self._export_btn)

        # ── Export Clear PNG button ────────────────────────────────────
        # Disabled until background removal succeeds.
        self._export_clear_btn = QPushButton("Export Clear PNG")
        self._export_clear_btn.setEnabled(False)
        self._export_clear_btn.setMinimumHeight(36)
        self._export_clear_btn.clicked.connect(self._on_export_clear_png_clicked)
        layout.addWidget(self._export_clear_btn)

        return sidebar

    # ------------------------------------------------------------------ #
    # Canvas — QStackedWidget with three pages                            #
    # ------------------------------------------------------------------ #

    def _build_canvas(self) -> QWidget:
        """
        Factory for the central canvas area.

        Page layout:
          0 — PLACEHOLDER  Shown on launch and after a render error.
          1 — LOADING       Shown while RenderWorker is running.
          2 — RESULT        Shown when a render completes; has toggle buttons.

        Phase 3: the entire stack will be replaced by the timeline widget.
        """
        self._canvas_stack = QStackedWidget()
        self._canvas_stack.addWidget(self._build_placeholder_page())   # 0
        self._canvas_stack.addWidget(self._build_loading_page())        # 1
        self._canvas_stack.addWidget(self._build_result_page())         # 2
        self._canvas_stack.addWidget(self._build_references_page())     # 3
        self._canvas_stack.setCurrentIndex(_PAGE_PLACEHOLDER)
        return self._canvas_stack

    def _build_placeholder_page(self) -> QWidget:
        """Page 0: shown before any sketch is loaded, and after errors."""
        label = QLabel("Your rendered frame will appear here")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        label.setStyleSheet(
            "color: #888888; font-size: 16px; background-color: #1e1e1e;"
        )
        # Wrap in a plain widget so all pages have the same container type.
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label)
        return page

    def _build_loading_page(self) -> QWidget:
        """
        Page 1: shown while RenderWorker is running.
        A simple text label is sufficient — no animated spinner needed yet.
        Phase 2: replace with a QProgressBar once async polling is wired up.
        """
        label = QLabel("Rendering…  please wait")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        label.setStyleSheet(
            "color: #cccccc; font-size: 18px; background-color: #1e1e1e;"
        )
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label)
        return page

    def _build_result_page(self) -> QWidget:
        """
        Page 2: shown after a successful render.

        Layout:
          ┌─ toggle bar ──────────────────────────────┐
          │  [Sketch]  [Render]                        │
          └───────────────────────────────────────────┘
          ┌─ image display ───────────────────────────┐
          │  (expands to fill remaining space)         │
          └───────────────────────────────────────────┘

        Both toggle buttons are disabled until _last_render is set.
        """
        page = QWidget()
        page.setStyleSheet("background-color: #1e1e1e;")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # -- Toggle bar ------------------------------------------------
        toggle_bar = QWidget()
        toggle_bar.setFixedHeight(40)
        toggle_bar.setStyleSheet("background-color: #252525;")
        bar_layout = QHBoxLayout(toggle_bar)
        bar_layout.setContentsMargins(8, 4, 8, 4)
        bar_layout.setSpacing(6)

        self._toggle_sketch_btn = QPushButton("Sketch")
        self._toggle_sketch_btn.setEnabled(False)
        self._toggle_sketch_btn.setStyleSheet(_TOGGLE_INACTIVE_STYLE)
        self._toggle_sketch_btn.clicked.connect(self._show_sketch)

        self._toggle_render_btn = QPushButton("Render")
        self._toggle_render_btn.setEnabled(False)
        self._toggle_render_btn.setStyleSheet(_TOGGLE_INACTIVE_STYLE)
        self._toggle_render_btn.clicked.connect(self._show_render)

        self._toggle_clear_btn = QPushButton("Clear PNG")
        self._toggle_clear_btn.setEnabled(False)
        self._toggle_clear_btn.setStyleSheet(_TOGGLE_INACTIVE_STYLE)
        self._toggle_clear_btn.clicked.connect(self._show_clear)

        bar_layout.addWidget(self._toggle_sketch_btn)
        bar_layout.addWidget(self._toggle_render_btn)
        bar_layout.addWidget(self._toggle_clear_btn)
        bar_layout.addStretch()
        outer.addWidget(toggle_bar)

        # -- Image display label ---------------------------------------
        # Reused by both _show_sketch() and _show_render() — we just swap
        # the pixmap to switch between the two views.
        self._result_img_label = QLabel()
        self._result_img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_img_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        outer.addWidget(self._result_img_label)

        return page

    def _build_references_page(self) -> QWidget:
        """
        Page 3: full-canvas reference image management.

        The ReferenceDropZone fills the entire canvas so the user has
        a large drop target and can clearly see all loaded thumbnails.
        Activated by the [References] sidebar tab button.
        """
        page = QWidget()
        page.setStyleSheet("background-color: #1e1e1e;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)

        self._reference_zone = ReferenceDropZone()
        self._reference_zone.references_changed.connect(self._on_references_changed)
        layout.addWidget(self._reference_zone)

        return page

    # ------------------------------------------------------------------ #
    # Status bar                                                           #
    # ------------------------------------------------------------------ #

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        bar.showMessage("Ready")
        self.setStatusBar(bar)

    # ------------------------------------------------------------------ #
    # Signal handlers — all state transitions live here                   #
    # ------------------------------------------------------------------ #

    def _on_sketch_loaded(self, path_str: str) -> None:
        """SketchDropZone → MainWindow: a sketch file was accepted."""
        self.sketch_path = Path(path_str)
        self.statusBar().showMessage(f"Sketch loaded: {self.sketch_path.name}")
        self._render_btn.setEnabled(True)
        # Canvas stays on placeholder until the user explicitly renders.

    def _on_references_changed(self, paths: list[str]) -> None:
        """ReferenceDropZone → MainWindow: the loaded reference set changed."""
        self.reference_paths = paths
        count = len(paths)
        if count:
            self.statusBar().showMessage(
                f"{count} reference image{'s' if count != 1 else ''} loaded."
            )
        else:
            self.statusBar().showMessage("References cleared.")

    def _on_render_clicked(self) -> None:
        """User clicked Render: start a background worker, show loading page."""
        if self.sketch_path is None:
            return  # guard — button should be disabled, but be safe

        # Stop any in-progress background removal and reset clear PNG state.
        if self._bg_worker is not None:
            self._bg_worker.quit()
            self._bg_worker = None
        self._clear_png = None
        self._toggle_clear_btn.setEnabled(False)
        self._generate_clear_btn.setEnabled(False)
        self._export_clear_btn.setEnabled(False)

        # If the user was viewing references, switch back to the sketch canvas
        # so they can watch the loading state and result.
        self._activate_sketch_tab()

        self._render_btn.setEnabled(False)
        self._canvas_stack.setCurrentIndex(_PAGE_LOADING)
        self.statusBar().showMessage("Analyzing sketch...")

        scene_direction = self._prompt_edit.toPlainText().strip()

        ip_strength = self._ip_strength_slider.value() / 100
        cn_strength = self._cn_strength_slider.value() / 100

        self._render_worker = RenderWorker(
            self.sketch_path,
            scene_direction,
            ip_adapter_strength=ip_strength,
            controlnet_strength=cn_strength,
            reference_paths=self.reference_paths,
        )
        self._render_worker.status.connect(self.statusBar().showMessage)
        self._render_worker.result_ready.connect(self._on_result_ready)
        self._render_worker.error.connect(self._on_render_error)
        self._render_worker.finished.connect(self._on_worker_finished)
        self._render_worker.start()

    def _on_result_ready(self, image: QImage) -> None:
        """RenderWorker succeeded: store result, switch to result page, show render."""
        self._last_render = image

        # Enable toggle buttons and export now that a result exists.
        self._toggle_sketch_btn.setEnabled(True)
        self._toggle_render_btn.setEnabled(True)
        self._export_btn.setEnabled(True)
        self._generate_clear_btn.setEnabled(True)

        # Default view after a render: show the AI result.
        self._show_render()
        self._canvas_stack.setCurrentIndex(_PAGE_RESULT)
        self.statusBar().showMessage("Render complete.")

    def _on_render_error(self, message: str) -> None:
        """RenderWorker failed: return to placeholder, surface error."""
        self._canvas_stack.setCurrentIndex(_PAGE_PLACEHOLDER)
        self.statusBar().showMessage(f"Render failed: {message}")

    def _on_worker_finished(self) -> None:
        """QThread finished (fired after result_ready or error): clean up."""
        self._render_btn.setEnabled(True)
        self._render_worker = None  # allow GC

    # ------------------------------------------------------------------ #
    # Export handler                                                       #
    # ------------------------------------------------------------------ #

    def _on_export_clicked(self) -> None:
        """Save self._last_render as a PNG chosen by the user."""
        if self._last_render is None:
            return  # guard — button should be disabled, but be safe

        from PySide6.QtWidgets import QFileDialog  # local import: only needed here

        default_name = datetime.now().strftime("frameforge_%Y%m%d_%H%M%S.png")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Rendered Frame",
            default_name,
            "PNG Image (*.png)",
        )
        if not path:
            return  # user cancelled

        if self._last_render.save(path):
            self.statusBar().showMessage(f"Exported: {Path(path).name}")
        else:
            self.statusBar().showMessage("Export failed.")

    # ------------------------------------------------------------------ #
    # Toggle handlers (Page 2 only)                                       #
    # ------------------------------------------------------------------ #

    def _show_sketch(self) -> None:
        """Load and display the original sketch in the result image label."""
        if self.sketch_path is None:
            return
        pixmap = QPixmap(str(self.sketch_path))
        self._display_pixmap(pixmap)
        self._set_toggle_active("sketch")

    def _show_render(self) -> None:
        """Display the last render result in the result image label."""
        if self._last_render is None:
            return
        pixmap = QPixmap.fromImage(self._last_render)
        self._display_pixmap(pixmap)
        self._set_toggle_active("render")

    def _show_clear(self) -> None:
        """Display the background-removed image with a checkerboard backdrop."""
        if self._clear_png is None:
            return
        composite = self._make_checkerboard_pixmap(self._clear_png)
        self._result_img_label.setPixmap(composite)
        self._set_toggle_active("clear")

    def _display_pixmap(self, pixmap: QPixmap) -> None:
        """Scale pixmap to fit the image label, preserving aspect ratio."""
        scaled = pixmap.scaled(
            self._result_img_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._result_img_label.setPixmap(scaled)

    def _set_toggle_active(self, mode: str) -> None:
        """Apply active/inactive styles to the three canvas toggle buttons.

        *mode* must be one of ``"sketch"``, ``"render"``, or ``"clear"``.
        """
        self._toggle_sketch_btn.setStyleSheet(
            _TOGGLE_ACTIVE_STYLE if mode == "sketch" else _TOGGLE_INACTIVE_STYLE
        )
        self._toggle_render_btn.setStyleSheet(
            _TOGGLE_ACTIVE_STYLE if mode == "render" else _TOGGLE_INACTIVE_STYLE
        )
        self._toggle_clear_btn.setStyleSheet(
            _TOGGLE_ACTIVE_STYLE if mode == "clear" else _TOGGLE_INACTIVE_STYLE
        )

    def _make_checkerboard_pixmap(self, rgba_image: QImage) -> QPixmap:
        """Return a pixmap with a gray checkerboard background and *rgba_image*
        composited on top at the current label size."""
        display_size = self._result_img_label.size()
        scaled_pixmap = QPixmap.fromImage(rgba_image).scaled(
            display_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        w, h = scaled_pixmap.width(), scaled_pixmap.height()
        checker = QPixmap(w, h)
        painter = QPainter(checker)
        tile = 10
        light = QColor(200, 200, 200)
        dark = QColor(150, 150, 150)
        for row in range(h // tile + 1):
            for col in range(w // tile + 1):
                color = light if (row + col) % 2 == 0 else dark
                painter.fillRect(col * tile, row * tile, tile, tile, color)
        painter.drawPixmap(0, 0, scaled_pixmap)
        painter.end()

        return checker

    # ------------------------------------------------------------------ #
    # Background removal slots                                             #
    # ------------------------------------------------------------------ #

    def _on_generate_clear_png_clicked(self) -> None:
        """User clicked Generate Clear PNG: run background removal in a worker."""
        if self._last_render is None:
            return

        self._generate_clear_btn.setEnabled(False)
        self.statusBar().showMessage("Removing background…")

        self._bg_worker = BgRemovalWorker(self._last_render)
        self._bg_worker.status.connect(self.statusBar().showMessage)
        self._bg_worker.result_ready.connect(self._on_bg_result_ready)
        self._bg_worker.error.connect(self._on_bg_error)
        self._bg_worker.finished.connect(self._on_bg_worker_finished)
        self._bg_worker.start()

    def _on_bg_result_ready(self, image: QImage) -> None:
        """BgRemovalWorker succeeded: store result, enable Clear PNG tab."""
        self._clear_png = image
        self._toggle_clear_btn.setEnabled(True)
        self._export_clear_btn.setEnabled(True)
        self._canvas_stack.setCurrentIndex(_PAGE_RESULT)
        self._show_clear()
        self.statusBar().showMessage("Background removed.")

    def _on_bg_error(self, message: str) -> None:
        """BgRemovalWorker failed: surface error and re-enable button."""
        self.statusBar().showMessage(f"Background removal failed: {message}")
        self._generate_clear_btn.setEnabled(True)

    def _on_bg_worker_finished(self) -> None:
        """QThread finished: clean up worker reference."""
        self._bg_worker = None

    def _on_export_clear_png_clicked(self) -> None:
        """Save self._clear_png as a PNG with alpha channel."""
        if self._clear_png is None:
            return

        from PySide6.QtWidgets import QFileDialog  # local import: only needed here

        default_name = datetime.now().strftime("frameforge_%Y%m%d_%H%M%S_clear.png")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Clear PNG",
            default_name,
            "PNG Image (*.png)",
        )
        if not path:
            return

        if self._clear_png.save(path):
            self.statusBar().showMessage(f"Exported: {Path(path).name}")
        else:
            self.statusBar().showMessage("Export failed.")

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _build_sidebar_tabs(self) -> QWidget:
        """
        Two tab buttons that control which canvas page is visible.

          [Sketch Input]  — canvas pages 0/1/2 (placeholder / loading / result)
          [References]    — canvas page 3 (ReferenceDropZone full-canvas)

        Styled identically to the Sketch/Render toggle buttons on the result page.
        [Sketch Input] is active on launch.
        """
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(4)

        self._tab_sketch_btn = QPushButton("Sketch Input")
        self._tab_sketch_btn.setStyleSheet(_TOGGLE_ACTIVE_STYLE)
        self._tab_sketch_btn.clicked.connect(self._activate_sketch_tab)

        self._tab_refs_btn = QPushButton("References")
        self._tab_refs_btn.setStyleSheet(_TOGGLE_INACTIVE_STYLE)
        self._tab_refs_btn.clicked.connect(self._activate_references_tab)

        bar_layout.addWidget(self._tab_sketch_btn)
        bar_layout.addWidget(self._tab_refs_btn)
        bar_layout.addStretch()
        return bar

    def _activate_sketch_tab(self) -> None:
        """Switch canvas to the sketch/render stack; mark [Sketch Input] active."""
        self._tab_sketch_btn.setStyleSheet(_TOGGLE_ACTIVE_STYLE)
        self._tab_refs_btn.setStyleSheet(_TOGGLE_INACTIVE_STYLE)
        # Restore whichever sketch page is contextually correct.
        if self._render_worker is not None:
            self._canvas_stack.setCurrentIndex(_PAGE_LOADING)
        elif self._last_render is not None:
            self._canvas_stack.setCurrentIndex(_PAGE_RESULT)
        else:
            self._canvas_stack.setCurrentIndex(_PAGE_PLACEHOLDER)

    def _activate_references_tab(self) -> None:
        """Switch canvas to page 3 (ReferenceDropZone); mark [References] active."""
        self._tab_refs_btn.setStyleSheet(_TOGGLE_ACTIVE_STYLE)
        self._tab_sketch_btn.setStyleSheet(_TOGGLE_INACTIVE_STYLE)
        self._canvas_stack.setCurrentIndex(_PAGE_REFERENCES)

    def _build_sliders_section(self) -> QWidget:
        """
        Builds the strength sliders section for the sidebar.

        Returns a QWidget containing:
          • IP-Adapter Strength slider (default 0.75)
          • ControlNet Strength slider (default 1.00)

        Each slider row: header label + value label on one line, slider below.
        Slider range is 0–100 (integer); display and pipeline use value / 100.
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        def _make_slider(
            label_text: str,
            default: int,
        ) -> tuple[QSlider, QLabel]:
            # Header row: name on the left, live value on the right
            header = QWidget()
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(0, 0, 0, 0)
            name_lbl = QLabel(label_text)
            name_lbl.setStyleSheet("font-size: 11px;")
            val_lbl = QLabel(f"{default / 100:.2f}")
            val_lbl.setStyleSheet("font-size: 11px; color: #aaaaaa;")
            header_layout.addWidget(name_lbl)
            header_layout.addStretch()
            header_layout.addWidget(val_lbl)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(default)
            slider.valueChanged.connect(
                lambda v, lbl=val_lbl: lbl.setText(f"{v / 100:.2f}")
            )

            layout.addWidget(header)
            layout.addWidget(slider)
            return slider, val_lbl

        self._ip_strength_slider, _ = _make_slider("IP-Adapter Strength", 75)
        self._cn_strength_slider, _ = _make_slider("ControlNet Strength", 100)

        return container

    @staticmethod
    def _section_frame(title: str, body: str) -> QFrame:
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
