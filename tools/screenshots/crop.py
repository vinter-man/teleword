"""Crops a rendered frame at the first row painted with the crop key colour (#ff00ff)."""

import sys

from PIL import Image

KEY = (255, 0, 255)


def main(source: str, target: str) -> None:
    image = Image.open(source).convert("RGB")
    width, height = image.size
    bottom = next((y for y in range(height) if image.getpixel((0, y)) == KEY), height)
    cropped = image.crop((0, 0, width, bottom))
    if target.endswith(".jpg"):
        cropped.save(target, quality=92)
    else:
        cropped.save(target, optimize=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
