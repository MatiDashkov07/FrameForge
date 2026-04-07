"""
bg_removal_worker.py — Background thread for local background removal.

Mirrors the structure of RenderWorker: emits signals only, never touches
Qt widgets directly.
"""

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from frameforge.utils.background_removal import remove_background


class BgRemovalWorker(QThread):
    """Runs remove_background() on a background thread.

    Signals
    -------
    result_ready(QImage)
        Emitted on success with the background-removed RGBA image.
    error(str)
        Emitted on failure with a human-readable error message.
    status(str)
        Emitted to update the status bar during processing.
    """

    result_ready = Signal(QImage)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, image: QImage, parent=None) -> None:
        super().__init__(parent)
        self._image = image

    def run(self) -> None:
        try:
            self.status.emit("Removing background…")
            result = remove_background(self._image)
            self.result_ready.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
