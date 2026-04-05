"""
render_worker.py — FrameForge background render thread.

Runs the blocking ComfyUI API call on a QThread so the UI stays
responsive during inference (which can take 30–90 seconds).

Signal flow:
    MainWindow._on_render_clicked()
        → RenderWorker.start()
            → RenderWorker.run()          [background thread]
                → render_frame()          [blocks until ComfyUI job completes]
                → downloads image bytes   [one more HTTP round-trip to /view]
                → emits result_ready(QImage)   [back to main thread via Qt queue]
             OR → emits error(str)              [on any exception]
        → MainWindow._on_result_ready()   [Qt delivers signal on main thread]

No pipeline logic lives here. This class only orchestrates the call and
converts the raw bytes into a QImage that the UI can display directly.
"""

import urllib.request
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from frameforge.pipeline.comfyui_client import render_frame, _USER_AGENT


class RenderWorker(QThread):
    """
    Background thread that runs one render cycle:
      1. Calls render_frame() to get the output URL from Replicate.
      2. Downloads the image bytes from that URL.
      3. Decodes bytes into a QImage and emits result_ready.

    Instantiate fresh for each render request — do not reuse.
    """

    # Emitted on success: delivers the decoded QImage to the main thread.
    result_ready = Signal(QImage)

    # Emitted on failure: delivers a human-readable error message.
    error = Signal(str)

    def __init__(
        self,
        sketch_path: Path,
        prompt: str,
        ip_adapter_strength: float = 1.0,
        controlnet_strength: float = 1.0,
        reference_paths: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._sketch_path = sketch_path
        self._prompt = prompt
        self._ip_adapter_strength = ip_adapter_strength
        self._controlnet_strength = controlnet_strength
        self._reference_paths: list[str] = reference_paths or []

    def run(self) -> None:
        """
        Entry point called by QThread.start() on a background thread.
        Must not touch Qt widgets directly — all UI updates go through signals.
        """
        try:
            # -- Step 1: submit to ComfyUI, wait for the output URL -----------
            # This call blocks for the duration of inference (typically 30–90 s).
            # Includes upload, queue, polling, and URL construction internally.
            image_url = render_frame(
                self._sketch_path,
                self._prompt,
                ip_adapter_strength=self._ip_adapter_strength,
                controlnet_strength=self._controlnet_strength,
                reference_paths=self._reference_paths,
            )

            # -- Step 2: download the rendered image ---------------------------
            # urllib.request is stdlib — no extra dependency needed.
            # The URL points to the ComfyUI /view endpoint on the server.
            # User-Agent header is required — RunPod's Cloudflare proxy
            # returns 403 Forbidden on requests without it.
            print(f"[DEBUG RenderWorker] image_url={image_url!r}")
            dl_req = urllib.request.Request(
                image_url, headers={"User-Agent": _USER_AGENT}
            )
            with urllib.request.urlopen(dl_req) as response:
                image_bytes: bytes = response.read()

            # -- Step 3: decode bytes → QImage ---------------------------------
            # QImage.loadFromData() understands PNG, JPEG, and other common
            # formats without needing to know which format it is.
            image = QImage()
            if not image.loadFromData(image_bytes):
                raise ValueError(
                    f"Failed to decode image returned by ComfyUI. "
                    f"URL was: {image_url}"
                )

            self.result_ready.emit(image)

        except Exception as exc:  # noqa: BLE001
            # Catch everything — we're on a background thread and an uncaught
            # exception here would silently kill the thread with no feedback.
            self.error.emit(str(exc))
