"""
background_removal.py — Local background removal via BRIA RMBG-2.0 (BiRefNet).

Runs entirely on the local machine; does not call any cloud API.
On the first call the model weights (~700 MB) are downloaded from HuggingFace.
The model is then cached in memory — subsequent calls within the same process
reuse it without reloading.

Prerequisites:
    pip install transformers torch torchvision timm kornia
    huggingface-cli login          # one-time auth for briaai/RMBG-2.0
"""

import io

import torch
from PIL import Image as PILImage
from torchvision import transforms
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

# ── Module-level model cache ────────────────────────────────────────────────────
# Loaded once per process on the first remove_background() call.
_model = None
_device: str | None = None

_TRANSFORM = transforms.Compose(
    [
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ]
)


def _load_model():
    """Load RMBG-2.0 and cache it at module level. Thread-safe via GIL for the
    assignment, but callers should only invoke this from one worker thread at a time
    (which BgRemovalWorker guarantees)."""
    global _model, _device

    if _model is not None:
        return _model, _device

    try:
        from transformers import AutoModelForImageSegmentation
    except ImportError as exc:
        raise RuntimeError(
            "transformers is not installed. Run:\n"
            "  pip install transformers torch torchvision timm kornia"
        ) from exc

    try:
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        torch.set_float32_matmul_precision("high")
        _model = AutoModelForImageSegmentation.from_pretrained(
            "briaai/RMBG-2.0", trust_remote_code=True
        )
        _model.to(_device)
        _model.eval()
    except Exception as exc:
        _model = None
        _device = None
        raise RuntimeError(
            f"Failed to load briaai/RMBG-2.0: {exc}\n\n"
            "If this is an authentication error, run the following in a terminal:\n"
            "  huggingface-cli login\n"
            "Enter your HuggingFace access token, then restart FrameForge."
        ) from exc

    return _model, _device


def remove_background(image: QImage) -> QImage:
    """Remove the background from *image*, returning an RGBA QImage.

    Uses BRIA RMBG-2.0 (BiRefNet) for clean edges on fine detail such as hair.
    The model is loaded and cached on the first call (~700 MB download).

    This function is blocking — always call it from a worker thread.
    """
    model, device = _load_model()

    # ── QImage → PIL Image (RGB) ──────────────────────────────────────────────
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    pil_image = PILImage.open(io.BytesIO(bytes(buf.data()))).convert("RGB")

    # ── Run RMBG-2.0 ─────────────────────────────────────────────────────────
    input_tensor = _TRANSFORM(pil_image).unsqueeze(0).to(device)
    with torch.no_grad():
        preds = model(input_tensor)[-1].sigmoid().cpu()

    # ── Build alpha matte at original resolution ──────────────────────────────
    mask = transforms.ToPILImage()(preds[0].squeeze()).resize(pil_image.size)

    # ── Apply mask as alpha channel ────────────────────────────────────────────
    result_pil = pil_image.copy().convert("RGBA")
    result_pil.putalpha(mask)

    # ── PIL RGBA → QImage ─────────────────────────────────────────────────────
    out_buf = io.BytesIO()
    result_pil.save(out_buf, format="PNG")
    result_q = QImage()
    if not result_q.loadFromData(out_buf.getvalue()):
        raise ValueError("Could not decode RMBG-2.0 result into a QImage.")
    return result_q
