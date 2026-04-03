"""
tests/test_api.py — Phase 0 smoke test: Replicate API connection.

NOT a test suite. Run directly:
    python tests/test_api.py

What this proves:
  1. REPLICATE_API_TOKEN loads correctly from .env
  2. The replicate client can authenticate and submit a prediction
  3. The ControlNet + IP-Adapter model pipeline returns an image URL
  4. We can download and save the result locally

Model: usamaehsan/controlnet-x-ip-adapter-realistic-vision-v5
  Combines ControlNet (structure from sketch) with IP-Adapter (style/identity
  from reference images). This is the core of FrameForge's Phase 1 pipeline.
"""

import os
import pathlib
import urllib.request

import replicate
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL_VERSION = (
    "usamaehsan/controlnet-x-ip-adapter-realistic-vision-v5:"
    "50ac06bb9bcf30e7b5dc66d3fe6e67262059a11ade572a35afa0ef686f55db82"
)

# A simple line-art scribble hosted on Replicate's CDN — used as the
# ControlNet structure input. Phase 1 will replace this with user-uploaded
# sketches loaded from disk.
SCRIBBLE_IMAGE_URL = "https://replicate.delivery/pbxt/IJCoOCCMtGGGPJBpTDhGHJOCOHyJOXbJXJRpxRiXivWRWuIA/ComfyUI_00001_.png"

# Minimal prompt — CLIP encodes this as the third conditioning signal alongside
# ControlNet (structure) and IP-Adapter (style/identity).
PROMPT = "anime character, 2d illustration, clean lineart, vibrant colors"

# IP-Adapter checkpoint: the "plus" variant gives stronger style adherence.
# sd15 = Stable Diffusion 1.5 base (matched to this model version).
IP_ADAPTER_CKPT = "ip-adapter-plus_sd15.bin"

# ControlNet preprocessor: "lineart" extracts clean edges from the scribble.
SORTED_CONTROLNETS = "lineart"

OUTPUT_PATH = pathlib.Path("assets/test_output.png")


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

def run_smoke_test() -> None:
    # -- 1. Load API token from .env ----------------------------------------
    load_dotenv()
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise EnvironmentError(
            "REPLICATE_API_TOKEN not found. "
            "Add it to your .env file: REPLICATE_API_TOKEN=r8_..."
        )
    print(f"[1/4] API token loaded ({token[:6]}...{token[-4:]})")

    # -- 2. Submit prediction --------------------------------------------------
    # replicate.run() blocks until the prediction completes (or fails).
    # Phase 1 will switch to replicate.predictions.create() for async polling
    # so the UI can show a progress indicator.
    print("[2/4] Submitting prediction to Replicate…")
    with open("assets/test_sketch.png", "rb") as f:
        output = replicate.run(
            MODEL_VERSION,
            input={
                "prompt": PROMPT,
                "scribble_image": f,
                "ip_adapter_ckpt": IP_ADAPTER_CKPT,
                "sorted_controlnets": SORTED_CONTROLNETS,
            },
        )

    # -- 3. Extract output URL -------------------------------------------------
    # The model returns either a single URL string or a list of URLs.
    # Normalise to a single URL regardless.
    if isinstance(output, list):
        image_url = output[0]
    else:
        image_url = str(output)

    print(f"[3/4] Output image URL: {image_url}")

    # -- 4. Download and save --------------------------------------------------
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(image_url, OUTPUT_PATH)
    print(f"[4/4] Saved to {OUTPUT_PATH.resolve()}")
    print("\nSmoke test PASSED.")


if __name__ == "__main__":
    run_smoke_test()
