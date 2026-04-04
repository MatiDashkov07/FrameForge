"""
replicate_client.py — FrameForge Phase 1 cloud inference client.

Single responsibility: submit a render request to Replicate and return
the output image URL. Downloading the bytes is the caller's job.

No Qt imports. This module must remain UI-agnostic so it can be called
from a background thread (RenderWorker) or from scripts / tests directly.
"""

import os
from pathlib import Path

import replicate
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

# Swap this constant to change the backend model without touching any other
# code. The version hash pins an exact model revision for reproducibility.
# Phase 2 exploration: try a Flux-based variant here once ControlNet support
# matures in that ecosystem.
MODEL_VERSION = (
    "usamaehsan/controlnet-x-ip-adapter-realistic-vision-v5:"
    "50ac06bb9bcf30e7b5dc66d3fe6e67262059a11ade572a35afa0ef686f55db82"
)

# IP-Adapter checkpoint to load. The "plus" variant increases style fidelity
# at the cost of slight identity rigidity. sd15 = Stable Diffusion 1.5 base,
# which matches the model version above.
_IP_ADAPTER_CKPT = "ip-adapter-plus_sd15.bin"

# ControlNet preprocessor applied to the sketch. "lineart" extracts clean
# edges and is the most faithful to hand-drawn input.
_SORTED_CONTROLNETS = "lineart"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_frame(
    sketch_path: Path,
    prompt: str,
    ip_adapter_strength: float = 1.0,
    controlnet_strength: float = 1.0,
    reference_paths: list[str] | None = None,
) -> str:
    """
    Submit a single-frame render request to Replicate.

    Parameters
    ----------
    sketch_path:
        Absolute path to the line-art sketch (PNG or JPEG). Opened as a
        binary file and streamed to the Replicate API.
    prompt:
        CLIP text prompt — describes scene context, lighting, or style.
        Complements the structural signal from ControlNet and the style
        signal from IP-Adapter.
    ip_adapter_strength:
        How strongly IP-Adapter's style/identity conditioning is applied.
        1.0 = full strength. Reduce toward 0.0 for looser style adherence.
    controlnet_strength:
        How strictly the output must follow the sketch's structure.
        1.0 = tight adherence. Reduce for softer, more creative results.
    reference_paths:
        Optional list of absolute paths to reference images (PNG or JPEG).
        The first path is passed to IP-Adapter as the style/identity source.
        When None or empty, IP-Adapter runs without an image input (same
        behaviour as Phase 1).

    Returns
    -------
    str
        The URL of the rendered output image hosted on Replicate's CDN.
        The caller is responsible for downloading the bytes.

    Raises
    ------
    EnvironmentError
        If REPLICATE_API_TOKEN is missing from the environment.
    replicate.exceptions.ReplicateError
        If the Replicate API returns an error (auth failure, model error, etc.)
    """
    _ensure_token()

    ref_list = reference_paths or []
    ref_file = open(ref_list[0], "rb") if ref_list else None  # noqa: SIM115

    try:
        payload: dict = {
            "prompt": prompt,
            "ip_adapter_ckpt": _IP_ADAPTER_CKPT,
            "sorted_controlnets": _SORTED_CONTROLNETS,
            "ip_adapter_strength": ip_adapter_strength,
            "controlnet_conditioning_scale": controlnet_strength,
        }
        if ref_file is not None:
            # IP-Adapter image: the model uses the first reference as the
            # style/identity conditioning source, replacing the Phase 1
            # behaviour where no image was passed to IP-Adapter at all.
            # TODO Phase 3: support multiple references via embedding averaging.
            # Currently only the first reference is passed to IP-Adapter.
            payload["ip_adapter_image"] = ref_file

        with open(sketch_path, "rb") as sketch_file:
            payload["scribble_image"] = sketch_file
            output = replicate.run(MODEL_VERSION, input=payload)
    finally:
        if ref_file is not None:
            ref_file.close()

    # The model returns either a single URL string or a list of URLs.
    # Normalise to a single str regardless so callers don't need to branch.
    if isinstance(output, list):
        return str(output[0])
    return str(output)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_token() -> None:
    """
    Load .env and verify REPLICATE_API_TOKEN is present.
    Called once per render_frame() invocation (load_dotenv is idempotent).
    """
    load_dotenv()
    if not os.environ.get("REPLICATE_API_TOKEN"):
        raise EnvironmentError(
            "REPLICATE_API_TOKEN not found. "
            "Add it to your .env file:  REPLICATE_API_TOKEN=r8_..."
        )
