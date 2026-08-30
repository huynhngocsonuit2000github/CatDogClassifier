"""Download real cat/dog photos and pack them into versioned dataset archives.

Pulls images from The Cat API and The Dog API (public, key-less endpoints),
normalizes them (decode -> RGB -> 256px thumbnail -> JPEG), and writes a set of
zip archives under ``testing/data/``:

    dataset-01.zip ... dataset-10.zip     (each: cats/ + dogs/ folders)

Each archive is a valid version for the Data Management upload feature, so you
can upload them one after another to exercise DVC versioning.

Run from anywhere:

    python testing/download_real_data.py

Requires Pillow (reuse the service venv if needed).
"""
from __future__ import annotations

import concurrent.futures
import io
import json
import os
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
OUT = HERE / "data"

SETS = 10            # number of zip archives (dataset versions)
PER_CLASS = 3        # cats and dogs per archive (API caps unauth `limit` at 10)
SIZE = 256           # max thumbnail dimension
ALLOWED = {".jpg", ".jpeg", ".png"}
UA = {"User-Agent": "Mozilla/5.0 (pawsitive-mlops test data)"}

CAT_API = "https://api.thecatapi.com/v1/images/search"
DOG_API = "https://api.thedogapi.com/v1/images/search"


def fetch_json(url: str) -> list[dict]:
    query = f"?limit=100&mime_types=jpg,png&size=med"
    req = urllib.request.Request(url + query, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def image_urls(api: str, wanted: int) -> list[str]:
    urls: list[str] = []
    for _ in range(4):  # a few attempts until we have enough jpg/png URLs
        for item in fetch_json(api):
            url = item.get("url", "")
            ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
            if ext in ALLOWED and url not in urls:
                urls.append(url)
            if len(urls) >= wanted:
                return urls
    return urls


def download(url: str, tag: str) -> bytes | None:
    """Fetch, validate, and normalize one image to a small JPEG; None on failure."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        img = Image.open(io.BytesIO(data))
        img.thumbnail((SIZE, SIZE))
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {tag}: {exc.__class__.__name__} {url}")
        return None


def fetch_batch(urls: list[str], tag: str, wanted: int) -> list[bytes]:
    """Download in parallel, returning up to ``wanted`` successful images."""
    out: list[bytes] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for data in pool.map(lambda u: download(u, tag), urls):
            if data is not None:
                out.append(data)
            if len(out) >= wanted:
                break
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    needed = SETS * PER_CLASS
    print(f"Need {needed} cats + {needed} dogs for {SETS} archives.")

    print("Fetching cat image URLs…")
    cat_urls = image_urls(CAT_API, needed + 10)
    print(f"Fetching dog image URLs…")
    dog_urls = image_urls(DOG_API, needed + 10)
    print(f"  cats: {len(cat_urls)} urls, dogs: {len(dog_urls)} urls")

    print("Downloading cats…")
    cats = fetch_batch(cat_urls, "cat", needed)
    print(f"  {len(cats)} cat images")
    print("Downloading dogs…")
    dogs = fetch_batch(dog_urls, "dog", needed)
    print(f"  {len(dogs)} dog images")

    if len(cats) < needed or len(dogs) < needed:
        raise SystemExit(
            f"Not enough images downloaded (cats={len(cats)}, dogs={len(dogs)}). "
            "Please re-run; the API returns different images each call."
        )

    for i in range(SETS):
        path = OUT / f"dataset-{i + 1:02d}.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for j in range(PER_CLASS):
                zf.writestr(f"cats/cat_{j:04d}.jpg", cats[i * PER_CLASS + j])
                zf.writestr(f"dogs/dog_{j:04d}.jpg", dogs[i * PER_CLASS + j])
        print(f"  wrote {path.name} ({path.stat().st_size:,} bytes)")

    print(f"\nDone. {SETS} archives in {OUT}")


if __name__ == "__main__":
    main()