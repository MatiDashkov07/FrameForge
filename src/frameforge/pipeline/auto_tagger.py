"""
auto_tagger.py — FrameForge Auto-Tagger POC.

Two-stage LLM pipeline that converts a sketch image into a Danbooru tag
string ready for injection into the ComfyUI positive prompt field.

  Stage 1 (Vision):  sketch image → detailed English description
  Stage 2 (Tags):    description + optional user hint → Danbooru tag string

Both stages use Gemini 2.5 Flash — a single multimodal model handles vision
(Stage 1) and text-only synthesis (Stage 2).

The returned tag string targets Animagine XL 3.1 conventions: quality tags
first, then subject count, then character tags, then scene/environment tags.

No Qt imports. This module must remain UI-agnostic so it can be called
from a background thread or from scripts / tests directly.

Integration point (deferred — not wired yet):
    When Phase 2 Step 3 lands, auto_tag() will be called inside
    _on_render_clicked() in main_window.py, replacing the raw prompt text
    before it is passed to RenderWorker.
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

# Both stages use the same Gemini 2.5 Flash model.
# Stage 1 sends image + text; Stage 2 sends text only.
# Swap both constants together if a different model is needed per stage.
_VISION_MODEL = "gemini-2.5-flash"  # Stage 1: image → description
_TAG_MODEL = "gemini-2.5-flash"     # Stage 2: description → tags

# Maximum tokens each stage may generate. Description needs more room than
# tags — a Danbooru tag string is typically 80–150 tokens.
_VISION_MAX_TOKENS = 2048
_TAG_MAX_TOKENS = 4096

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_VISION_PROMPT = (
    "Describe this sketch image in exhaustive detail for a digital artist. "
    "Include: number of characters, each character's gender, hair color, hair "
    "length and style, eye color, clothing items, accessories, body framing "
    "(full body / upper body / portrait / close-up), pose, body language, "
    "facial expression, background elements or setting, art style "
    "(anime, cartoon, realistic, etc.), and lighting. "
    "Be specific and thorough. This description will be used to generate "
    "Danbooru tags for anime artwork generation."
)

_TAG_PROMPT_TEMPLATE = """\
Convert the following image description into a Danbooru tag string for Animagine XL 3.1.

Rules:
- Use only real, valid Danbooru tags (lowercase, underscored: long_hair, school_uniform)
- Order: quality tags first, then subject count, then character/subject tags, then scene/environment tags
- Always open with: masterpiece, best quality, highres
- Do not invent tags that do not exist on Danbooru
- Aim for 20-40 tags. Be thorough: include tags for hair, eyes, clothing, accessories, expression, pose, framing, background, and art style
- IMPORTANT: The user has provided additional scene context below. You MUST incorporate it as tags even if the image description does not mention these elements. The user context describes the DESIRED output, not what is currently in the sketch.
- Output ONLY the comma-separated tag string — no explanation, no markdown

Image description:
{description}

User's scene direction (MUST be reflected in tags):
{user_context}

Tags:"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_image(image_path: str) -> str:
    """
    Stage 1: send a sketch image to the vision model and return a detailed
    English description of everything visible.

    Parameters
    ----------
    image_path:
        Absolute or relative path to the sketch (PNG or JPEG). Read as bytes
        and sent to Gemini as inline image data.

    Returns
    -------
    str
        Multi-sentence English description suitable for use as Stage 2 input.

    Raises
    ------
    EnvironmentError
        If GEMINI_API_KEY is missing from the environment.
    FileNotFoundError
        If image_path does not point to an existing file.
    google.genai.errors.APIError
        If the Gemini API returns an error.
    """
    client = _get_client()

    print(f"[auto_tagger] Stage 1 — vision model: {_VISION_MODEL}")
    print(f"[auto_tagger] Image: {image_path}")

    suffix = Path(image_path).suffix.lower()
    mime_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    response = client.models.generate_content(
        model=_VISION_MODEL,
        contents=[
            _VISION_PROMPT,
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
        config=types.GenerateContentConfig(max_output_tokens=_VISION_MAX_TOKENS),
    )

    description = response.text.strip()
    print(f"[auto_tagger] Stage 1 complete — {len(description)} chars")
    return description


def generate_tags(description: str, user_prompt: str | None = None) -> str:
    """
    Stage 2: convert an image description (from Stage 1) plus an optional
    natural-language user hint into a Danbooru-format tag string.

    Parameters
    ----------
    description:
        Detailed English description of the image, typically from analyze_image().
    user_prompt:
        Optional free-form scene direction from the user, e.g.
        "sunset lighting, she looks sad". Folded into the tag synthesis prompt.
        Pass None or empty string to omit.

    Returns
    -------
    str
        Comma-separated Danbooru tag string beginning with quality tags
        (masterpiece, best quality, highres). Ready for injection into the
        ComfyUI positive prompt field (workflow node "145").

    Raises
    ------
    EnvironmentError
        If GEMINI_API_KEY is missing from the environment.
    google.genai.errors.APIError
        If the Gemini API returns an error.
    """
    client = _get_client()

    user_context = user_prompt.strip() if user_prompt else "(none)"
    prompt = _TAG_PROMPT_TEMPLATE.format(
        description=description,
        user_context=user_context,
    )

    print(f"[auto_tagger] Stage 2 — tag model: {_TAG_MODEL}")
    print(f"[auto_tagger] User context: {user_context}")

    response = client.models.generate_content(
        model=_TAG_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=_TAG_MAX_TOKENS),
    )

    tags = response.text.strip()
    # Strip any leading "Tags:" the model might echo back despite instructions.
    if tags.lower().startswith("tags:"):
        tags = tags[5:].strip()

    print(f"[auto_tagger] Stage 2 complete — {len(tags.split(','))} tags")
    return tags


def auto_tag(image_path: str, user_prompt: str | None = None) -> str:
    """
    Convenience wrapper: run Stage 1 then Stage 2 and return the final tag
    string. This is the function that will be called from the render pipeline.

    Parameters
    ----------
    image_path:
        Absolute or relative path to the sketch (PNG or JPEG).
    user_prompt:
        Optional natural-language scene direction from the user.

    Returns
    -------
    str
        Comma-separated Danbooru tag string ready for the positive prompt field.

    Raises
    ------
    EnvironmentError
        If GEMINI_API_KEY is missing from the environment.
    FileNotFoundError
        If image_path does not point to an existing file.
    google.genai.errors.APIError
        If the Gemini API returns an error at either stage.
    """
    description = analyze_image(image_path)
    print("[auto_tagger] Waiting 10s for rate limit...")
    # TODO: test without this delay — may not be needed for Gemini paid tier.
    time.sleep(10)
    return generate_tags(description, user_prompt)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client() -> genai.Client:
    """
    Load .env, verify GEMINI_API_KEY is present, and return a configured
    Gemini client. Called once per public function invocation.
    (load_dotenv is idempotent so repeated calls are safe.)
    """
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not found. "
            "Add it to your .env file:  GEMINI_API_KEY=AIza..."
        )
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="FrameForge Auto-Tagger POC — sketch → Danbooru tags"
    )
    parser.add_argument("--image", required=True, help="Path to sketch image (PNG or JPEG)")
    parser.add_argument(
        "--prompt",
        default=None,
        help='Optional natural language context, e.g. "sunset, forest background"',
    )
    args = parser.parse_args()

    print("[auto_tagger] Starting two-stage tag pipeline...")
    print()

    print("[auto_tagger] Stage 1: analyzing image...")
    description = analyze_image(args.image)
    print()
    print("=== Description ===")
    print(description)
    print()

    print("[auto_tagger] Stage 2: generating Danbooru tags...")
    tags = generate_tags(description, args.prompt)
    print()
    print("=== Tags ===")
    print(tags)
