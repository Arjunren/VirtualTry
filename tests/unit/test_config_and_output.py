from __future__ import annotations

from datetime import datetime

import pytest

from virtual_tryon.config import AppConfig
from virtual_tryon.imaging.output import safe_output_filename, unique_output_path


def test_config_round_trip(tmp_path) -> None:
    path = tmp_path / "config.json"
    config = AppConfig(automatic_generation=True, output_width=768, output_height=1024)
    config.save(path)
    assert AppConfig.load(path) == config


@pytest.mark.parametrize(
    ("field", "value"),
    [("engine", "unknown"), ("device", "metal"), ("precision", "int8"), ("inference_steps", 2)],
)
def test_config_validation(field: str, value: object) -> None:
    config = AppConfig()
    setattr(config, field, value)
    with pytest.raises(ValueError):
        config.validate()


def test_safe_filename_is_deterministic() -> None:
    moment = datetime(2026, 10, 2, 17, 30, 15)
    assert safe_output_filename(moment) == "tryon_2026-10-02_173015.png"


def test_unique_path_does_not_overwrite(tmp_path) -> None:
    original = tmp_path / "tryon.png"
    original.write_bytes(b"x")
    assert unique_output_path(tmp_path, "tryon.png").name == "tryon_1.png"
