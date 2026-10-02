from __future__ import annotations

from PIL import Image

from virtual_tryon.config import AppConfig
from virtual_tryon.infrastructure.paths import AppPaths
from virtual_tryon.ui.main_window import MainWindow


def paths_for(tmp_path):
    return AppPaths(
        project_root=tmp_path,
        runtime_root=tmp_path / "runtime",
        config_file=tmp_path / "runtime" / "config.json",
        log_dir=tmp_path / "runtime" / "logs",
        output_dir=tmp_path / "output",
        cache_dir=tmp_path / "runtime" / "cache",
    )


def test_successful_result_display(qtbot, tmp_path) -> None:
    paths = paths_for(tmp_path)
    paths.ensure_runtime_dirs()
    window = MainWindow(AppConfig(), paths)
    qtbot.addWidget(window)
    window.active_request_id = "active"
    window._busy = True
    result = Image.new("RGB", (100, 150), "green")
    window._on_generation_finished("active", result, 1.25)
    assert window.result_image is result
    assert "complete" in window.status_label.text().lower()


def test_stale_result_is_discarded(qtbot, tmp_path) -> None:
    paths = paths_for(tmp_path)
    paths.ensure_runtime_dirs()
    window = MainWindow(AppConfig(), paths)
    qtbot.addWidget(window)
    window.active_request_id = "new-request"
    window._busy = True
    window._on_generation_finished("old-request", Image.new("RGB", (10, 10)), 1.0)
    assert window.result_image is None
    assert window.active_request_id == "new-request"


def test_inference_failure_restores_controls(qtbot, tmp_path, monkeypatch) -> None:
    paths = paths_for(tmp_path)
    paths.ensure_runtime_dirs()
    window = MainWindow(AppConfig(), paths)
    qtbot.addWidget(window)
    messages = []
    monkeypatch.setattr(window, "_show_error", lambda title, message: messages.append((title, message)))
    window.active_request_id = "active"
    window._busy = True
    window._on_generation_failed("active", "synthetic failure")
    assert not window._busy
    assert messages == [("Generation failed", "synthetic failure")]
