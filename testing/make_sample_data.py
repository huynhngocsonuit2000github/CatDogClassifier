"""Generate sample dataset archives for testing the Data Management upload feature.

Creates, under ``testing/data/``:

  - ``catsdogs-sample.zip``   valid: ``cats/`` + ``dogs/`` folders of healthy PNGs
  - ``missing-dogs.zip``      invalid: has ``cats/`` but no ``dogs/`` folder -> 422
  - ``corrupt-image.zip``     invalid: a truncated PNG in ``cats/``       -> 422

Run from anywhere (it resolves its own location):

    python testing/make_sample_data.py

Requires Pillow. Reuse the service venv if you don't have Pillow system-wide:

    py -3.11 -m venv .venv           # or use the existing service venv
    .venv/Scripts/python testing/make_sample_data.py
"""
from __future__ import annotations

import io
import random
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "data"

# class -> (base RGB, number of images)
SPEC = {
    "cats": ((214, 120, 40), 12),
    "dogs": ((58, 110, 200), 8),
}

random.seed(42)


def make_image(cls: str, idx: int) -> bytes:
    base = SPEC[cls][0]
    w = random.randint(72, 128)
    h = random.randint(72, 128)
    # Vary the shade so each image is distinct but recognizable per class.
    shade = random.randint(-30, 30)
    color = tuple(min(255, max(0, c + shade)) for c in base)

    img = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(img)
    draw.ellipse([w * 0.2, h * 0.2, w * 0.8, h * 0.8], outline=(255, 255, 255), width=3)
    draw.ellipse([w * 0.35, h * 0.35, w * 0.65, h * 0.65], fill=(255, 255, 255))
    draw.rectangle([w * 0.05, h * 0.05, w * 0.12, h * 0.12], fill=(255, 255, 255))
    draw.rectangle([w * 0.88, h * 0.05, w * 0.95, h * 0.12], fill=(255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def build_zip(path: Path, folders: dict[str, int]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for cls, count in folders.items():
            for i in range(count):
                zf.writestr(f"{cls}/{cls}_{i:04d}.png", make_image(cls, i))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    build_zip(OUT / "catsdogs-sample.zip", {"cats": 12, "dogs": 8})

    build_zip(OUT / "missing-dogs.zip", {"cats": 6})

    with zipfile.ZipFile(OUT / "corrupt-image.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("cats/broken.png", b"this is not a real png")
        zf.writestr("dogs/fine.png", make_image("dogs", 0))

    print("Wrote to", OUT)
    for p in sorted(OUT.glob("*.zip")):
        print(f"  {p.name:<22} {p.stat().st_size:>7} bytes")


if __name__ == "__main__":
    main()