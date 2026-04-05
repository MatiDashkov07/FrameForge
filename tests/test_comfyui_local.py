"""
test_comfyui_local.py — FrameForge Phase 2 smoke test for the ComfyUI client.

Validates the full render pipeline against a locally running ComfyUI instance.
Run this after starting ComfyUI and confirming all models are loaded.

Usage:
    python tests/test_comfyui_local.py

Requirements:
    - ComfyUI running at COMFYUI_URL (default: http://127.0.0.1:8188)
    - assets/test_sketch.png    — line-art sketch input
    - assets/test_reference.png — character reference image for IP-Adapter
    - All model files present in ComfyUI:
        animagine-xl-3.1.safetensors      (models/checkpoints/)
        control-lora-sketch-rank256.safetensors (models/controlnet/)
        ip-adapter-plus_sdxl_vit-h.safetensors (models/ipadapter/ or custom_nodes/)
        open_clip_model.safetensors        (models/clip_vision/)

Exit codes:
    0 — smoke test passed
    1 — smoke test failed
"""

import sys
import urllib.request
from pathlib import Path

# Resolve project root so this script runs from any working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from frameforge.pipeline.comfyui_client import render_frame, _ensure_url, _USER_AGENT  # noqa: E402

_SKETCH_PATH    = _PROJECT_ROOT / "assets" / "test_sketch.png"
_REFERENCE_PATH = _PROJECT_ROOT / "assets" / "test_reference.png"
_OUTPUT_PATH    = _PROJECT_ROOT / "assets" / "test_comfyui_output.png"


def main() -> None:
    print("=" * 60)
    print("FrameForge — ComfyUI local smoke test")
    print("=" * 60)

    # -- [1/4] Verify ComfyUI is reachable -----------------------------------
    print("\n[1/4] Checking ComfyUI server…")
    base_url = _ensure_url()
    print(f"      Target: {base_url}")
    try:
        req = urllib.request.Request(
            f"{base_url}/system_stats", headers={"User-Agent": _USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            stats = resp.read()
        print(f"      OK — server responded ({len(stats)} bytes)")
    except Exception as exc:
        print(f"\n  FAIL — cannot reach ComfyUI at {base_url}")
        print(f"         {exc}")
        print("\n  Make sure ComfyUI is running before running this test.")
        sys.exit(1)

    # -- [2/4] Verify asset files exist --------------------------------------
    print("\n[2/4] Checking asset files…")
    for label, path in [("Sketch", _SKETCH_PATH), ("Reference", _REFERENCE_PATH)]:
        if not path.exists():
            print(f"\n  FAIL — {label} not found: {path}")
            print(f"         Add a test image at {path} and re-run.")
            sys.exit(1)
        print(f"      {label}: {path.name} — OK")

    # -- [3/4] Call render_frame() -------------------------------------------
    print("\n[3/4] Submitting render request…")
    print("      (this may take 30–90 seconds depending on hardware)")
    try:
        result_url = render_frame(
            sketch_path=_SKETCH_PATH,
            prompt="anime character, 2d illustration, clean lineart, vibrant colors",
            ip_adapter_strength=0.7,
            controlnet_strength=0.8,
            reference_paths=[str(_REFERENCE_PATH)],
        )
    except Exception as exc:
        print(f"\n  FAIL — render_frame() raised an exception:")
        print(f"         {exc}")
        sys.exit(1)

    if "/view?filename=" not in result_url:
        print(f"\n  FAIL — unexpected return value from render_frame():")
        print(f"         {result_url!r}")
        print("         Expected a URL containing '/view?filename='")
        sys.exit(1)

    print(f"      Result URL: {result_url}")

    # -- [4/4] Download and save result --------------------------------------
    print(f"\n[4/4] Downloading result to {_OUTPUT_PATH.name}…")
    try:
        dl_req = urllib.request.Request(
            result_url, headers={"User-Agent": _USER_AGENT}
        )
        with urllib.request.urlopen(dl_req) as resp:
            image_bytes = resp.read()
        _OUTPUT_PATH.write_bytes(image_bytes)
        print(f"      Saved {len(image_bytes):,} bytes → {_OUTPUT_PATH}")
    except Exception as exc:
        print(f"\n  FAIL — could not download result image:")
        print(f"         {exc}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Smoke test PASSED.")
    print("=" * 60)


if __name__ == "__main__":
    main()
