from __future__ import annotations

from pathlib import Path

from virtual_tryon.config import AppConfig, EngineKind
from virtual_tryon.vton.base import VTONEngine
from virtual_tryon.vton.catvton import CatVTONEngine
from virtual_tryon.vton.mock import MockVTONEngine


def create_engine(config: AppConfig, project_root: Path) -> VTONEngine:
    config.validate()
    if config.engine == EngineKind.CATVTON.value:
        return CatVTONEngine(config, project_root)
    return MockVTONEngine(config.output_width, config.output_height)
