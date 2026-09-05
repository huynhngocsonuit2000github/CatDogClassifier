"""Build sized real cat/dog datasets from The Cat API / The Dog API.

Creates, under ``testing/data/``:

    3 x 100-image datasets   (50 cats + 50 dogs each)
    3 x 1000-image datasets  (500 cats + 500 dogs each)

    6 archives total -> 1650 cats + 1650 dogs = 3300 images.

Each archive is a valid version for the Data Management upload feature
(``cats/`` + ``dogs/`` folders of JPEGs), so they can be uploaded one after
another to exercise DVC versioning / training / the promotion gate.

The key-less search API returns only 10 random images per call, so collecting
1650 *unique* images per species means ~170+ calls each. To survive the time
this takes (and any interruption), the script is resumable:

    * ``collect``   gathers unique {id: url} maps into ``data/_pool/{cats,dogs}.json``
                    (merges on re-run, so a re-run only tops up the shortfall).
    * ``download``  fetches + normalises each image to ``data/_pool/{cats,dogs}/{id}.jpg``
                    (skips files already on disk).
    * ``pack``      splits the pool into the 6 archives.

Running with no ``--phase`` does all three in sequence.

Usage (reuse the data-management venv, which has Pillow):

    .venv/Scripts/python testing/make_real_datasets.py [--phase collect|download|pack]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
OUT = HERE / "data"
POOL = OUT / "_pool"

CAT_API = "https://api.thecatapi.com/v1/images/search"
# Dog CEO serves the Stanford Dogs dataset (~20k unique JPGs, 50/call) — the
# key-less The Dog API search caps at ~1.25k unique images, too few for 3×1000.
DOG_API = "https://dog.ceo/api/breeds/image/random/50"

# Total unique images needed per species: 3*50 + 3*500 = 1650.
TARGET = 1650
# Collect a little extra so a few failed downloads don't leave us short.
COLLECT = 1750

SIZE = 256                    # max thumbnail dimension
ALLOWED = {".jpg", ".jpeg", ".png"}
UA = {"User-Agent": "Mozilla/5.0 (pawsitive-mlops test data)"}

# The 6 archives, each expressed as (name, cats, dogs).
ARCHIVES = [
    ("dataset-100-1", 50, 50),
    ("dataset-100-2", 50, 50),
    ("dataset-100-3", 50, 50),
    ("dataset-1000-1", 500, 500),
    ("dataset-1000-2", 500, 500),
    ("dataset-1000-3", 500, 500),
]


def pool_json(species: str) -> Path:
    return POOL / f"{species}.json"


def img_dir(species: str) -> Path:
    return POOL / species


def img_path(species: str, image_id: str) -> Path:
    return img_dir(species) / f"{image_id}.jpg"


def load_pool(species: str) -> dict[str, str]:
    path = pool_json(species)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_pool(species: str, pool: dict[str, str]) -> None:
    POOL.mkdir(parents=True, exist_ok=True)
    tmp = pool_json(species).with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(pool, fh, ensure_ascii=False)
    tmp.replace(pool_json(species))


def fetch_json(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_batch(species: str) -> list[tuple[str, str]]:
    """Return one batch of ``(key, url)`` pairs for the species.

    Cats come from The Cat API (10 random per call, keyed by image id); dogs
    come from Dog CEO / Stanford Dogs (50 random per call, keyed by the URL's
    unique basename). ``collect`` deduplicates by ``key`` — which is also the
    filename the image is later saved under.
    """
    for attempt in range(8):
        try:
            if species == "cats":
                data = fetch_json(CAT_API + "?limit=100&mime_types=jpg,png&size=med")
                out = []
                for item in data:
                    key = item.get("id")
                    url = item.get("url", "")
                    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
                    if key and ext in ALLOWED:
                        out.append((key, url))
                return out
            # dogs — Dog CEO
            data = fetch_json(DOG_API)
            out = []
            for url in data.get("message", []):
                ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
                if ext in ALLOWED:
                    key = os.path.basename(urllib.parse.urlparse(url).path).rsplit(".", 1)[0]
                    out.append((key, url))
            return out
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = 2 ** attempt
                print(f"  rate-limited (429), backing off {wait}s…")
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(1)
    return []


def collect(species: str) -> None:
    """Top up ``pool_json(species)`` to at least ``COLLECT`` unique keys."""
    pool = load_pool(species)
    if len(pool) >= COLLECT:
        print(f"{species}: already have {len(pool)} images, nothing to collect")
        return
    print(f"{species}: collecting unique images (have {len(pool)}, want {COLLECT})…")
    attempt = 0
    max_attempts = (COLLECT - len(pool)) * 4 + 500
    while len(pool) < COLLECT and attempt < max_attempts:
        attempt += 1
        for key, url in fetch_batch(species):
            if key not in pool:
                pool[key] = url
        if attempt % 25 == 0:
            save_pool(species, pool)
            print(f"  {species}: {len(pool)} unique after {attempt} calls")
        time.sleep(0.25)
    save_pool(species, pool)
    print(f"{species}: collection done — {len(pool)} unique images")


def _download_one(species: str, image_id: str, url: str) -> tuple[str, bool]:
    dest = img_path(species, image_id)
    if dest.exists():
        return image_id, False  # already done, not counted as new work
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        img = Image.open(io.BytesIO(data))
        img.thumbnail((SIZE, SIZE))
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fh:
            fh.write(buf.getvalue())
        return image_id, True
    except Exception:  # noqa: BLE001 — one bad image shouldn't stop the run
        return image_id, False


def download(species: str) -> None:
    """Download + normalise every pooled id (skips files already on disk)."""
    pool = load_pool(species)
    dest_dir = img_dir(species)
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing = {p.stem for p in dest_dir.glob("*.jpg")}
    todo = [(i, u) for i, u in pool.items() if i not in existing]
    print(f"{species}: {len(todo)} images to download "
          f"({len(pool) - len(todo)} already cached)")
    if not todo:
        return
    new = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool_ex:
        futures = [pool_ex.submit(_download_one, species, i, u) for i, u in todo]
        for fut in concurrent.futures.as_completed(futures):
            _id, added = fut.result()
            if added:
                new += 1
            if new % 100 == 0:
                print(f"  {species}: downloaded {new} new images")
    print(f"{species}: download done — {new} new, "
          f"{len(existing) + new} total on disk")


def _good_images(species: str) -> list[Path]:
    return sorted(img_dir(species).glob("*.jpg"))


def pack() -> None:
    """Assemble the 6 archives from the downloaded pool."""
    OUT.mkdir(parents=True, exist_ok=True)
    needed = {"cats": sum(a[1] for a in ARCHIVES),
              "dogs": sum(a[2] for a in ARCHIVES)}
    pools = {sp: _good_images(sp) for sp in ("cats", "dogs")}
    for sp in ("cats", "dogs"):
        have = len(pools[sp])
        print(f"{sp}: {have} good images on disk (need {needed[sp]})")
        if have < needed[sp]:
            raise SystemExit(
                f"Not enough {sp} images on disk ({have} < {needed[sp]}). "
                "Re-run with --phase download (and --phase collect first if the "
                "pool is short)."
            )

    off = {"cats": 0, "dogs": 0}
    for name, n_cats, n_dogs in ARCHIVES:
        path = OUT / f"{name}.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for sp, count in (("cats", n_cats), ("dogs", n_dogs)):
                src = pools[sp][off[sp]:off[sp] + count]
                for j, img in enumerate(src):
                    zf.write(img, arcname=f"{sp}/{sp}_{j:04d}.jpg")
                off[sp] += count
        print(f"  wrote {path.name} ({path.stat().st_size:,} bytes: "
              f"{n_cats} cats + {n_dogs} dogs)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["collect", "download", "pack", "all"],
                        default="all")
    args = parser.parse_args()

    if args.phase in ("collect", "all"):
        for sp in ("cats", "dogs"):
            collect(sp)
    if args.phase in ("download", "all"):
        for sp in ("cats", "dogs"):
            download(sp)
    if args.phase in ("pack", "all"):
        pack()

    if args.phase == "all":
        print("\nDone — 6 archives in", OUT)


if __name__ == "__main__":
    main()