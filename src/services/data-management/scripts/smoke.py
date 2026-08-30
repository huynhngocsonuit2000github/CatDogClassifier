"""End-to-end smoke test for the Data Management service (local mode).

Usage (with the server running in local mode):
    python scripts/smoke.py

Expects the service at http://127.0.0.1:8000. It generates a tiny cat/dog ZIP,
uploads it, and prints the resulting version list.
"""
from __future__ import annotations

import io
import sys
import zipfile

import requests
from PIL import Image

BASE = "http://127.0.0.1:8000"


def make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for cls, count, color in [("cats", 3, (200, 80, 80)), ("dogs", 2, (80, 80, 200))]:
            for i in range(count):
                stream = io.BytesIO()
                Image.new("RGB", (32, 32), color).save(stream, "PNG")
                zf.writestr(f"{cls}/{cls}_{i}.png", stream.getvalue())
    return buf.getvalue()


def main() -> int:
    health = requests.get(f"{BASE}/health", timeout=5)
    print("health:", health.status_code, health.json())

    payload = make_zip()
    resp = requests.post(
        f"{BASE}/datasets",
        files={"file": ("smoke.zip", payload, "application/zip")},
        data={"name": "smoke test"},
        timeout=30,
    )
    print("post:", resp.status_code, resp.json())

    listing = requests.get(f"{BASE}/datasets", timeout=5)
    print("list:", listing.status_code, listing.json())
    return 0


if __name__ == "__main__":
    sys.exit(main())