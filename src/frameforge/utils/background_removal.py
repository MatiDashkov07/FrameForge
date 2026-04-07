"""
background_removal.py — Local background removal via rembg (U²-Net).

Runs entirely on the local machine; does not call any cloud API.
On the first call, rembg will download the model weights (~170 MB).
Subsequent calls use the cached weights.

This module is intentionally free of Qt GUI code so it can be tested
independently. It does use PySide6.QtCore for QBuffer/QIODevice byte I/O.
"""

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage


def remove_background(image: QImage) -> QImage:
    """Remove the background from *image*, returning an RGBA QImage.

    This function is blocking — always call it from a worker thread.
    """
    import rembg  # deferred: heavy import + potential model download on first use

    # ── QImage → PNG bytes ────────────────────────────────────────────────
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    png_bytes = bytes(buf.data())

    # ── Remove background (returns RGBA PNG bytes) ────────────────────────
    result_bytes: bytes = rembg.remove(png_bytes)

    # ── PNG bytes → QImage ────────────────────────────────────────────────
    result = QImage()
    if not result.loadFromData(result_bytes):
        raise ValueError("rembg returned data that could not be decoded as an image.")
    return result
