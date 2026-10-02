from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from virtual_tryon.config import AppConfig, GarmentCategory
from virtual_tryon.vton.base import GenerationCancelled, VTONEngine
from virtual_tryon.vton.factory import create_engine

LOGGER = logging.getLogger(__name__)


class TryOnSignals(QObject):
    model_state = Signal(str, str)
    generation_started = Signal(str)
    generation_finished = Signal(str, object, float)
    generation_failed = Signal(str, str)
    generation_cancelled = Signal(str)


class _LoadTask(QRunnable):
    def __init__(self, service: "TryOnService") -> None:
        super().__init__()
        self.service = service

    @Slot()
    def run(self) -> None:
        self.service.signals.model_state.emit("loading", "Loading model…")
        try:
            self.service._ensure_loaded()
            self.service.signals.model_state.emit("ready", self.service.engine.display_name)
        except Exception as error:
            LOGGER.exception("model_load_failed error_type=%s", type(error).__name__)
            self.service.signals.model_state.emit("error", str(error))


class _GenerateTask(QRunnable):
    def __init__(
        self,
        service: "TryOnService",
        request_id: str,
        person: Image.Image,
        garment: Image.Image,
        category: GarmentCategory,
        cancel_event: threading.Event,
    ) -> None:
        super().__init__()
        self.service = service
        self.request_id = request_id
        self.person = person
        self.garment = garment
        self.category = category
        self.cancel_event = cancel_event

    @Slot()
    def run(self) -> None:
        started = time.perf_counter()
        self.service.signals.generation_started.emit(self.request_id)
        LOGGER.info("inference_started request=%s category=%s", self.request_id, self.category.value)
        try:
            self.service._ensure_loaded()
            if self.cancel_event.is_set():
                raise GenerationCancelled("Generation was cancelled.")
            result = self.service.engine.generate(
                self.person,
                self.garment,
                self.category,
                self.cancel_event,
            )
            elapsed = time.perf_counter() - started
            if self.cancel_event.is_set():
                raise GenerationCancelled("Generation was cancelled.")
            LOGGER.info("inference_completed request=%s duration_seconds=%.3f", self.request_id, elapsed)
            self.service.signals.generation_finished.emit(self.request_id, result, elapsed)
        except GenerationCancelled:
            self.service.signals.generation_cancelled.emit(self.request_id)
        except Exception as error:
            LOGGER.exception("inference_failed request=%s error_type=%s", self.request_id, type(error).__name__)
            self.service.signals.generation_failed.emit(self.request_id, str(error))


class TryOnService:
    def __init__(self, config: AppConfig, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root
        self.signals = TryOnSignals()
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(1)
        self.engine: VTONEngine = create_engine(config, project_root)
        self._loaded = False
        self._load_lock = threading.Lock()
        self._cancel_events: dict[str, threading.Event] = {}

    def _ensure_loaded(self) -> None:
        with self._load_lock:
            if not self._loaded:
                self.engine.load()
                self._loaded = True

    def load_async(self) -> None:
        self.pool.start(_LoadTask(self))

    def generate_async(
        self,
        request_id: str,
        person: Image.Image,
        garment: Image.Image,
        category: GarmentCategory,
    ) -> None:
        event = threading.Event()
        self._cancel_events[request_id] = event
        self.pool.start(_GenerateTask(self, request_id, person.copy(), garment.copy(), category, event))

    def cancel(self, request_id: str | None) -> None:
        if request_id and request_id in self._cancel_events:
            self._cancel_events[request_id].set()

    def forget(self, request_id: str) -> None:
        self._cancel_events.pop(request_id, None)

    def replace_config(self, config: AppConfig) -> None:
        for event in self._cancel_events.values():
            event.set()
        self.pool.waitForDone()
        self.config = config
        self.engine = create_engine(config, self.project_root)
        self._loaded = False
        self._cancel_events.clear()
        self.load_async()
