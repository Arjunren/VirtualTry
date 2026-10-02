from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    project_root: Path
    runtime_root: Path
    config_file: Path
    log_dir: Path
    output_dir: Path
    cache_dir: Path

    @classmethod
    def discover(cls) -> "AppPaths":
        if getattr(sys, "frozen", False):
            project_root = Path(sys.executable).resolve().parent
        else:
            project_root = Path(__file__).resolve().parents[3]
        local_app_data = Path(os.environ.get("LOCALAPPDATA", project_root / "data"))
        runtime_root = local_app_data / "VirtualTry"
        return cls(
            project_root=project_root,
            runtime_root=runtime_root,
            config_file=runtime_root / "config.json",
            log_dir=runtime_root / "logs",
            output_dir=project_root / "data" / "output",
            cache_dir=runtime_root / "cache",
        )

    def ensure_runtime_dirs(self) -> None:
        for directory in (self.runtime_root, self.log_dir, self.output_dir, self.cache_dir):
            directory.mkdir(parents=True, exist_ok=True)
