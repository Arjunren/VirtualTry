from __future__ import annotations

from datetime import datetime
from pathlib import Path


def safe_output_filename(now: datetime | None = None, suffix: str = ".png") -> str:
    moment = now or datetime.now()
    normalized = suffix.lower()
    if normalized not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("unsupported output format")
    return f"tryon_{moment:%Y-%m-%d_%H%M%S}{normalized}"


def unique_output_path(directory: Path, filename: str) -> Path:
    destination = directory / filename
    counter = 1
    while destination.exists():
        destination = directory / f"{Path(filename).stem}_{counter}{Path(filename).suffix}"
        counter += 1
    return destination
