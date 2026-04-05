"""
comfyui_client.py — FrameForge Phase 2 ComfyUI inference client.

Single responsibility: submit a render request to a ComfyUI server and return
the output image URL. Downloading the bytes is the caller's job (RenderWorker).

Replaces replicate_client.py. The render_frame() signature is identical so
the swap in render_worker.py is a single import change, nothing else.

No Qt imports. This module must remain UI-agnostic so it can be called
from a background thread (RenderWorker) or from scripts / tests directly.

ComfyUI API lifecycle (all calls are plain HTTP, no extra dependencies):
  1. POST /upload/image  — upload sketch + reference images
  2. POST /prompt        — queue the workflow; receive a prompt_id
  3. GET  /history/{id}  — poll until the job is recorded as done
  4. GET  /view?filename=... — the ready-to-download output URL (returned to caller)
"""

import json
import os
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Workflow template
# ---------------------------------------------------------------------------

# Absolute path to the ComfyUI API-format workflow JSON.
# Loaded fresh on every render_frame() call — no shared mutable state.
# NOTE: filename has a typo ("worflow") — it is the real filename on disk.
_WORKFLOW_PATH = Path(__file__).parent / "worflow_api_v1.json"

# ---------------------------------------------------------------------------
# Node IDs that receive dynamic values each render.
# All other nodes in the workflow are static (model names, sampler, VAE, etc.)
# ---------------------------------------------------------------------------

_SKETCH_NODE           = "152"  # LoadImage              → inputs.image
_REFERENCE_NODE        = "155"  # LoadImage              → inputs.image
_POSITIVE_PROMPT_NODE  = "145"  # CLIPTextEncode         → inputs.text
_CONTROLNET_NODE       = "154"  # ControlNetApplyAdvanced → inputs.strength
_IP_ADAPTER_NODE       = "159"  # IPAdapterAdvanced      → inputs.weight
_SAVE_IMAGE_NODE       = "151"  # SaveImage              → read for output filename


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
    Submit a single-frame render request to a ComfyUI server.

    Parameters
    ----------
    sketch_path:
        Absolute path to the line-art sketch (PNG or JPEG). Uploaded to
        ComfyUI and routed to the ControlNet node.
    prompt:
        CLIP text prompt — scene context, style tags, character description.
        Injected into the positive CLIPTextEncode node.
    ip_adapter_strength:
        IP-Adapter conditioning weight (0.0–1.0). Controls how strongly the
        reference image's style/identity is applied.
    controlnet_strength:
        ControlNet conditioning scale (0.0–1.0). Controls how strictly the
        output follows the sketch's structure.
    reference_paths:
        Optional list of absolute paths to reference images (PNG or JPEG).
        The first path is uploaded and used as the IP-Adapter image source.
        When None or empty, the sketch is reused as the reference (same
        behaviour as Phase 1 — not ideal, but functional as a fallback).

    Returns
    -------
    str
        A URL of the form ``http://<host>/view?filename=...&type=output&subfolder=``.
        The caller (RenderWorker) downloads the bytes from this URL.

    Raises
    ------
    EnvironmentError
        If COMFYUI_URL cannot be determined (default is used, so this is only
        raised if .env explicitly sets an empty value).
    TimeoutError
        If ComfyUI does not complete the job within 120 seconds.
    urllib.error.URLError
        If the ComfyUI server is unreachable.
    """
    base_url = _ensure_url()

    ref_list = reference_paths or []
    ref_path = Path(ref_list[0]) if ref_list else sketch_path  # fallback = sketch

    # -- Step 1: upload images -----------------------------------------------
    sketch_fn = _upload_image(base_url, sketch_path)
    ref_fn    = _upload_image(base_url, ref_path)

    # -- Step 2: build populated workflow ------------------------------------
    workflow = _build_workflow(sketch_fn, ref_fn, prompt,
                               ip_adapter_strength, controlnet_strength)

    # -- Step 3: queue the prompt --------------------------------------------
    prompt_id = _queue_prompt(base_url, workflow)

    # -- Step 4: poll until done ---------------------------------------------
    job = _poll_until_done(base_url, prompt_id)

    # -- Step 5: extract output filename from SaveImage node -----------------
    try:
        image_info = job["outputs"][_SAVE_IMAGE_NODE]["images"][0]
        filename   = image_info["filename"]
        subfolder  = image_info.get("subfolder", "")
    except (KeyError, IndexError) as exc:
        raise RuntimeError(
            f"ComfyUI job {prompt_id} completed but produced no output images. "
            f"Check that all model files are present (especially "
            f"open_clip_model.safetensors in models/clip_vision/). "
            f"Raw job outputs: {job.get('outputs', {})}"
        ) from exc

    return f"{base_url}/view?filename={filename}&type=output&subfolder={subfolder}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_url() -> str:
    """
    Load .env and return the ComfyUI base URL.
    Defaults to http://127.0.0.1:8188 if COMFYUI_URL is not set.
    Called once per render_frame() invocation (load_dotenv is idempotent).
    """
    load_dotenv()
    url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
    return url


def _upload_image(base_url: str, image_path: Path) -> str:
    """
    Upload an image file to ComfyUI via POST /upload/image.

    ComfyUI expects multipart/form-data with a field named "image".
    Returns the server-assigned filename (used to reference the image
    inside the workflow JSON).
    """
    boundary = "FrameForgeUpload"
    with open(image_path, "rb") as f:
        file_bytes = f.read()

    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"

    # Build multipart/form-data body manually — no external dependency needed.
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'
        f"Content-Type: {mime}\r\n"
        f"\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{base_url}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    # ComfyUI returns: {"name": "filename.png", "subfolder": "", "type": "input"}
    return result["name"]


def _build_workflow(
    sketch_fn: str,
    ref_fn: str,
    prompt: str,
    ip_strength: float,
    cn_strength: float,
) -> dict:
    """
    Load the workflow JSON template and inject per-render values.

    json.load() produces a fresh dict on every call, so no deepcopy needed.
    The template file on disk is never modified.
    """
    with open(_WORKFLOW_PATH, encoding="utf-8") as f:
        wf = json.load(f)

    wf[_SKETCH_NODE][         "inputs"]["image"]    = sketch_fn
    wf[_REFERENCE_NODE][      "inputs"]["image"]    = ref_fn
    wf[_POSITIVE_PROMPT_NODE]["inputs"]["text"]     = prompt
    wf[_CONTROLNET_NODE][     "inputs"]["strength"] = cn_strength
    wf[_IP_ADAPTER_NODE][     "inputs"]["weight"]   = ip_strength

    return wf


def _queue_prompt(base_url: str, workflow: dict) -> str:
    """
    POST the workflow to ComfyUI's /prompt endpoint.
    Returns the prompt_id string assigned by ComfyUI.
    """
    body = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/prompt",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    # ComfyUI returns: {"prompt_id": "...", "number": N, "node_errors": {}}
    return result["prompt_id"]


def _poll_until_done(
    base_url: str,
    prompt_id: str,
    interval: float = 1.0,
    timeout: float = 120.0,
) -> dict:
    """
    Poll GET /history/{prompt_id} until the job appears in the response.

    ComfyUI returns {} while the job is still queued or running.
    The prompt_id key appears in the response only when the job is complete
    (regardless of success or failure).

    Returns the history entry dict for the completed job.
    Raises TimeoutError if the job does not complete within `timeout` seconds.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with urllib.request.urlopen(
            f"{base_url}/history/{prompt_id}"
        ) as resp:
            history = json.loads(resp.read())

        if prompt_id in history:
            return history[prompt_id]

        time.sleep(interval)

    raise TimeoutError(
        f"ComfyUI render timed out after {timeout}s (prompt_id={prompt_id}). "
        f"Check that ComfyUI is running and the workflow has no errors."
    )
