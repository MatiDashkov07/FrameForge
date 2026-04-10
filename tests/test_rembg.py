"""
test_rembg.py — Quick background removal test script.

Usage:
    python tests/test_rembg.py assets/my_image.png

Outputs:
    assets/my_image_clear.png (with background removed)
"""

import sys
from pathlib import Path

from rembg import remove
from PIL import Image


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tests/test_rembg.py <image_path>")
        print("Example: python tests/test_rembg.py assets/reference.png")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)

    # Build output path: same folder, same name + _clear suffix
    output_path = input_path.with_name(f"{input_path.stem}_clear{input_path.suffix}")

    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print("Running rembg (U²-Net)...")

    img = Image.open(input_path)
    result = remove(img)
    result.save(output_path)

    print(f"Done! Saved to {output_path}")


if __name__ == "__main__":
    main()