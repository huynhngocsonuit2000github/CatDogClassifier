"""Dataset upload validation: ZIP extraction with schema + class-balance checks.

A valid dataset archive is a ZIP containing images organised under ``cats/`` and
``dogs/`` folders (either at the top level or nested one level deep). Each image
is verified for integrity, and the cat/dog counts are used for the class-balance
summary.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
CLASS_DIRS = ("cats", "dogs")


@dataclass
class ValidationReport:
    images: int = 0
    cats: int = 0
    dogs: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def cat_pct(self) -> float:
        if self.images == 0:
            return 0.0
        return round(self.cats / self.images * 100, 1)

    @property
    def ok(self) -> bool:
        return self.images > 0 and self.cats > 0 and self.dogs > 0


def validate_archive(archive_bytes: bytes, dest: Path) -> ValidationReport:
    """Extract and validate ``archive_bytes`` into ``dest``.

    Raises ``ValueError`` for a structurally invalid archive (not a ZIP, unsafe
    paths, or missing class folders). Returns a :class:`ValidationReport` with
    image counts and any non-fatal warnings.
    """
    if not zipfile.is_zipfile(io.BytesIO(archive_bytes)):
        raise ValueError("Uploaded file is not a valid ZIP archive.")

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        for m in members:
            _assert_safe(m.filename)
        if not _contains_class_dirs(members):
            raise ValueError(
                "Archive must contain image folders named 'cats' and 'dogs'."
            )
        dest.mkdir(parents=True, exist_ok=True)
        zf.extractall(dest)

    report = ValidationReport()
    for class_dir in CLASS_DIRS:
        root = _find_dir(dest, class_dir)
        if root is None:
            # _contains_class_dirs already guaranteed these exist, but guard anyway.
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(dest).as_posix()
            if path.suffix.lower() not in ALLOWED_EXTS:
                report.warnings.append(f"unsupported type (skipped): {rel}")
                continue
            if not _is_valid_image(path):
                report.warnings.append(f"corrupt image (skipped): {rel}")
                continue
            report.images += 1
            if class_dir == "cats":
                report.cats += 1
            else:
                report.dogs += 1
    return report


def _assert_safe(name: str) -> None:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe path in archive: {name!r}")


def _contains_class_dirs(members: list[zipfile.ZipInfo]) -> bool:
    files = {m.filename for m in members}
    for class_dir in CLASS_DIRS:
        if not any(name.startswith(f"{class_dir}/") for name in files):
            return False
    return True


def _find_dir(root: Path, name: str) -> Path | None:
    """Return the first directory named ``name`` at any depth."""
    for path in root.rglob(name):
        if path.is_dir():
            return path
    return None


def _is_valid_image(path: Path) -> bool:
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:  # noqa: BLE001 - any PIL/decode error means "invalid"
        return False