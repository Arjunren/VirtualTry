from __future__ import annotations

from PIL import Image

from virtual_tryon.application.tryon_service import TryOnService
from virtual_tryon.config import AppConfig, GarmentCategory


def test_worker_lifecycle_and_mock_generation(qtbot, tmp_path) -> None:
    service = TryOnService(AppConfig(), tmp_path)
    with qtbot.waitSignal(service.signals.model_state, timeout=2000) as ready:
        service.load_async()
    assert ready.args[0] in {"loading", "ready"}

    person = Image.new("RGB", (80, 120), "navy")
    garment = Image.new("RGB", (60, 60), "red")
    with qtbot.waitSignal(service.signals.generation_finished, timeout=3000) as completed:
        service.generate_async("request-1", person, garment, GarmentCategory.UPPER)
    assert completed.args[0] == "request-1"
    assert completed.args[1].size == (384, 512)


def test_cancelled_queued_job_does_not_emit_result(qtbot, tmp_path) -> None:
    service = TryOnService(AppConfig(), tmp_path)
    person = Image.new("RGB", (80, 120), "navy")
    garment = Image.new("RGB", (60, 60), "red")
    with qtbot.waitSignal(service.signals.generation_cancelled, timeout=3000) as cancelled:
        service.generate_async("request-cancel", person, garment, GarmentCategory.UPPER)
        service.cancel("request-cancel")
    assert cancelled.args == ["request-cancel"]
