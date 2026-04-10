"""
test_rmbg2.py — RMBG-2.0 background removal test script.

Compares BRIA's RMBG-2.0 (BiRefNet) against rembg (U²-Net).
First run will download the model (~700MB).

Prerequisites:
    pip install transformers torch torchvision pillow

    You also need to accept the license on HuggingFace:
    https://huggingface.co/briaai/RMBG-2.0

Usage:
    python tests/test_rmbg2.py assets/my_image.png
"""

import sys
import time
from pathlib import Path

import torch
import numpy as np
from PIL import Image
from torchvision import transforms
from transformers import AutoModelForImageSegmentation


def remove_background_rmbg2(image: Image.Image, device: str) -> Image.Image:
    """Remove background using RMBG-2.0 model."""
    model = AutoModelForImageSegmentation.from_pretrained(
        "briaai/RMBG-2.0", trust_remote_code=True
    )
    torch.set_float32_matmul_precision("high")
    model.to(device)
    model.eval()

    transform = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    input_tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        preds = model(input_tensor)[-1].sigmoid().cpu()

    pred = preds[0].squeeze()
    mask = transforms.ToPILImage()(pred).resize(image.size)

    # Apply alpha mask
    result = image.copy().convert("RGBA")
    result.putalpha(mask)
    return result


def remove_background_rembg(image: Image.Image) -> Image.Image:
    """Remove background using rembg (U²-Net) for comparison."""
    from rembg import remove
    return remove(image)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tests/test_rmbg2.py <image_path>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)

    image = Image.open(input_path).convert("RGB")

    # Pick device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    print(f"Input:  {input_path}")
    print()

    # --- RMBG-2.0 ---
    rmbg2_output = input_path.with_name(f"{input_path.stem}_rmbg2{input_path.suffix}")
    print("Running RMBG-2.0 (first run downloads ~700MB model)...")
    t0 = time.time()
    result_rmbg2 = remove_background_rmbg2(image, device)
    t1 = time.time()
    result_rmbg2.save(rmbg2_output)
    print(f"  Done in {t1 - t0:.1f}s → {rmbg2_output}")
    print()

    # --- rembg (U²-Net) ---
    rembg_output = input_path.with_name(f"{input_path.stem}_rembg{input_path.suffix}")
    print("Running rembg (U²-Net)...")
    t0 = time.time()
    result_rembg = remove_background_rembg(image)
    t1 = time.time()
    result_rembg.save(rembg_output)
    print(f"  Done in {t1 - t0:.1f}s → {rembg_output}")
    print()

    print("Compare the two outputs side by side:")
    print(f"  RMBG-2.0: {rmbg2_output}")
    print(f"  rembg:    {rembg_output}")


if __name__ == "__main__":
    main()