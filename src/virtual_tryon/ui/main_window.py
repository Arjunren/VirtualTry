from __future__ import annotations

import logging
import uuid
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QMimeData, Qt, QThreadPool, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from virtual_tryon.application.image_tasks import ImageLoadTask
from virtual_tryon.application.tryon_service import TryOnService
from virtual_tryon.config import AppConfig, GarmentCategory
from virtual_tryon.imaging.drop_parser import DropCandidate, DropKind, parse_mime_data
from virtual_tryon.imaging.image_validator import ImageLimits
from virtual_tryon.imaging.output import safe_output_filename
from virtual_tryon.infrastructure.hardware import detect_hardware
from virtual_tryon.infrastructure.paths import AppPaths
from virtual_tryon.ui.drop_zone import DropZone
from virtual_tryon.ui.image_viewer import ImageViewer
from virtual_tryon.ui.settings_dialog import SettingsDialog

LOGGER = logging.getLogger(__name__)


STYLE = """
QMainWindow, QWidget { background: #111116; color: #f0eef8; font-size: 13px; }
QFrame#panel { background: #191820; border: 1px solid #2d2a38; border-radius: 12px; }
QLabel#heading { color: #aaa3bb; font-weight: 700; letter-spacing: 1px; }
QLabel#imageViewer {
    background: #14131a; border: 2px dashed #393548; border-radius: 10px;
    color: #8f899d; padding: 12px;
}
DropZone[dragActive="true"] QLabel#imageViewer { border-color: #8d6cff; background: #211d31; }
QPushButton { background: #292633; border: 1px solid #3c374a; border-radius: 7px; padding: 8px 13px; }
QPushButton:hover { background: #373244; }
QPushButton#primary { background: #7357e8; border-color: #8d74f1; font-weight: 700; }
QPushButton#primary:hover { background: #8268ee; }
QPushButton:disabled { color: #6e6978; background: #211f28; }
QComboBox { background: #211f28; border: 1px solid #3c374a; border-radius: 6px; padding: 6px; }
QProgressBar { border: 0; background: #211f28; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: #8063ee; border-radius: 3px; }
QTabWidget::pane { border: 1px solid #2d2a38; }
"""


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, paths: AppPaths) -> None:
        super().__init__()
        self.config = config
        self.paths = paths
        self.person_image: Image.Image | None = None
        self.garment_image: Image.Image | None = None
        self.result_image: Image.Image | None = None
        self.active_request_id: str | None = None
        self._busy = False
        self._model_loading = True
        self._model_ready = False
        self._elapsed_seconds = 0
        self._image_pool = QThreadPool(self)
        self._image_pool.setMaxThreadCount(2)
        self._image_tasks: set[ImageLoadTask] = set()
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.setInterval(500)
        self._auto_timer.timeout.connect(self.start_generation)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self.service = TryOnService(config, paths.project_root)
        self.service.signals.model_state.connect(self._on_model_state)
        self.service.signals.generation_started.connect(self._on_generation_started)
        self.service.signals.generation_finished.connect(self._on_generation_finished)
        self.service.signals.generation_failed.connect(self._on_generation_failed)
        self.service.signals.generation_cancelled.connect(self._on_generation_cancelled)

        self.setWindowTitle("VirtualTry · Local AI Virtual Try-On")
        self.resize(1240, 860)
        self.setMinimumSize(980, 700)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._update_actions()
        hardware = detect_hardware()
        self.device_label.setText(hardware.label)
        LOGGER.info("startup device=%s", hardware.device)
        self.service.load_async()

    def _build_ui(self) -> None:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("AI VIRTUAL TRY-ON")
        title.setStyleSheet("font-size: 21px; font-weight: 800;")
        self.model_label = QLabel("Model: not loaded")
        self.device_label = QLabel("Detecting hardware…")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.model_label)
        title_row.addWidget(QLabel("·"))
        title_row.addWidget(self.device_label)
        outer.addLayout(title_row)

        inputs = QSplitter(Qt.Orientation.Horizontal)
        self.person_zone = DropZone("Drop a person image\nJPG · PNG · WebP")
        self.garment_zone = DropZone("Drop clothing from Explorer or a browser\nJPG · PNG · WebP")
        self.person_zone.dropped.connect(lambda items: self._load_candidates("person", items))
        self.garment_zone.dropped.connect(lambda items: self._load_candidates("garment", items))
        self.person_zone.clicked.connect(lambda: self._choose_image("person"))
        self.garment_zone.clicked.connect(lambda: self._choose_image("garment"))
        inputs.addWidget(self._input_panel("PERSON", self.person_zone, "person"))
        inputs.addWidget(self._input_panel("GARMENT", self.garment_zone, "garment"))
        inputs.setSizes([600, 600])
        outer.addWidget(inputs, 4)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Garment type"))
        self.category = QComboBox()
        self.category.addItem("Upper body · shirt / jacket / sweater", GarmentCategory.UPPER.value)
        self.category.addItem("Lower body · pants / skirt", GarmentCategory.LOWER.value)
        self.category.addItem("Overall · dress", GarmentCategory.OVERALL.value)
        controls.addWidget(self.category)
        controls.addStretch()
        self.generate_button = QPushButton("Generate Try-On")
        self.generate_button.setObjectName("primary")
        self.generate_button.clicked.connect(self.start_generation)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_generation)
        controls.addWidget(self.generate_button)
        controls.addWidget(self.cancel_button)
        outer.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        outer.addWidget(self.progress)

        self.tabs = QTabWidget()
        self.result_viewer = ImageViewer("Your generated result appears here")
        self.tabs.addTab(self.result_viewer, "Result")
        comparison = QSplitter(Qt.Orientation.Horizontal)
        self.before_viewer = ImageViewer("Person image")
        self.after_viewer = ImageViewer("Generated result")
        comparison.addWidget(self.before_viewer)
        comparison.addWidget(self.after_viewer)
        self.tabs.addTab(comparison, "Before / After")
        outer.addWidget(self.tabs, 5)

        footer = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.elapsed_label = QLabel("")
        footer.addWidget(self.status_label)
        footer.addWidget(self.elapsed_label)
        footer.addStretch()
        self.save_button = QPushButton("Save Result")
        self.save_button.clicked.connect(self.save_result)
        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset)
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.open_settings)
        footer.addWidget(self.save_button)
        footer.addWidget(reset)
        footer.addWidget(self.settings_button)
        outer.addLayout(footer)
        self.setCentralWidget(root)

    def _input_panel(self, heading: str, zone: DropZone, target: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        label = QLabel(heading)
        label.setObjectName("heading")
        layout.addWidget(label)
        layout.addWidget(zone, 1)
        row = QHBoxLayout()
        choose = QPushButton(f"Choose {heading.title()}")
        choose.clicked.connect(lambda: self._choose_image(target))
        paste = QPushButton("Paste")
        paste.clicked.connect(lambda: self._paste(target))
        row.addWidget(choose)
        row.addWidget(paste)
        layout.addLayout(row)
        return panel

    def _limits(self) -> ImageLimits:
        return ImageLimits(
            max_file_bytes=self.config.max_file_bytes,
            max_width=self.config.max_width,
            max_height=self.config.max_height,
            max_pixels=self.config.max_pixels,
        )

    def _choose_image(self, target: str) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Choose an image", "", "Images (*.jpg *.jpeg *.png *.webp)")
        if filename:
            self._load_candidates(target, [DropCandidate(DropKind.LOCAL_FILE, filename)])

    def _paste(self, target: str) -> None:
        mime: QMimeData = QApplication.clipboard().mimeData()
        candidates = parse_mime_data(mime)
        if not candidates:
            self._show_error("Clipboard", "The clipboard does not contain a supported image.")
            return
        self._load_candidates(target, candidates)

    def _load_candidates(self, target: str, candidates: list[DropCandidate]) -> None:
        if not candidates:
            self._show_error("Image", "No supported image data was found in the drop.")
            return
        task = ImageLoadTask(target, candidates, self._limits(), self.config.allow_remote_images)
        self._image_tasks.add(task)
        task.signals.loaded.connect(self._on_image_loaded)
        task.signals.failed.connect(self._on_image_failed)
        task.signals.loaded.connect(lambda _target, _image, current=task: self._image_tasks.discard(current))
        task.signals.failed.connect(lambda _target, _message, current=task: self._image_tasks.discard(current))
        self.status_label.setText("Validating image…")
        self._image_pool.start(task)

    def _on_image_loaded(self, target: str, image: Image.Image) -> None:
        self._invalidate_active_generation()
        if target == "person":
            self.person_image = image
            self.person_zone.set_image(image)
            self.before_viewer.set_image(image)
            self.status_label.setText("Person image ready")
        else:
            self.garment_image = image
            self.garment_zone.set_image(image)
            self.status_label.setText("Garment image ready")
        self._update_actions()
        should_auto_generate = (
            target == "garment"
            and self.config.automatic_generation
            and self.person_image is not None
            and not self._busy
        )
        if should_auto_generate:
            self._auto_timer.start()

    def _on_image_failed(self, target: str, message: str) -> None:
        self.status_label.setText("Image rejected")
        self._show_error("Image rejected", message)

    def _invalidate_active_generation(self) -> None:
        if self.active_request_id:
            self.service.cancel(self.active_request_id)
            self.active_request_id = None
            self.status_label.setText("Cancelling stale generation…")

    def start_generation(self) -> None:
        if self._busy or self.person_image is None or self.garment_image is None:
            return
        self.result_image = None
        self.result_viewer.clear("Generating…")
        self.after_viewer.clear("Generating…")
        request_id = str(uuid.uuid4())
        self.active_request_id = request_id
        self._busy = True
        self._elapsed_seconds = 0
        self._elapsed_timer.start(1000)
        self.progress.setRange(0, 0)
        self.status_label.setText("Queued for generation…")
        self._update_actions()
        category = GarmentCategory(self.category.currentData())
        self.service.generate_async(request_id, self.person_image, self.garment_image, category)

    def cancel_generation(self) -> None:
        if self.active_request_id:
            self.service.cancel(self.active_request_id)
            self.status_label.setText("Cancellation requested…")
            self.cancel_button.setEnabled(False)

    def _on_model_state(self, state: str, detail: str) -> None:
        self.model_label.setText(f"Model: {detail}")
        self._model_loading = state == "loading"
        self._model_ready = state == "ready"
        if state == "error":
            self.status_label.setText("Model unavailable · open Settings or see README")
        self._update_actions()

    def _on_generation_started(self, request_id: str) -> None:
        if request_id == self.active_request_id:
            self.status_label.setText("Generating locally…")

    def _on_generation_finished(self, request_id: str, result: Image.Image, elapsed: float) -> None:
        self.service.forget(request_id)
        if request_id != self.active_request_id:
            if self.active_request_id is None:
                self._finish_busy()
            return
        self.result_image = result
        self.result_viewer.set_image(result)
        self.after_viewer.set_image(result)
        self.status_label.setText("Generation complete")
        self.elapsed_label.setText(f"{elapsed:.1f} s")
        self.active_request_id = None
        self._finish_busy()

    def _on_generation_failed(self, request_id: str, message: str) -> None:
        self.service.forget(request_id)
        if request_id != self.active_request_id:
            if self.active_request_id is None:
                self._finish_busy()
            return
        self.active_request_id = None
        self.status_label.setText("Generation failed")
        self._finish_busy()
        self._show_error("Generation failed", message)

    def _on_generation_cancelled(self, request_id: str) -> None:
        self.service.forget(request_id)
        if request_id == self.active_request_id:
            self.active_request_id = None
        if self.active_request_id is None:
            self.status_label.setText("Generation cancelled")
            self._finish_busy()

    def _finish_busy(self) -> None:
        self._busy = False
        self._elapsed_timer.stop()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self._update_actions()

    def _tick_elapsed(self) -> None:
        self._elapsed_seconds += 1
        self.elapsed_label.setText(f"{self._elapsed_seconds} s")

    def _update_actions(self) -> None:
        self.generate_button.setEnabled(
            bool(self.person_image and self.garment_image and not self._busy and self._model_ready)
        )
        self.cancel_button.setEnabled(self._busy and self.active_request_id is not None)
        self.save_button.setEnabled(self.result_image is not None)
        self.settings_button.setEnabled(not self._busy and not self._model_loading)

    def save_result(self) -> None:
        if self.result_image is None:
            return
        suggested = str(self.paths.output_dir / safe_output_filename())
        filename, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save try-on result",
            suggested,
            "PNG image (*.png);;JPEG image (*.jpg *.jpeg)",
        )
        if not filename:
            return
        destination = Path(filename)
        if destination.exists():
            answer = QMessageBox.question(
                self,
                "Replace existing file?",
                "That file already exists. Replace it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            wants_jpeg = destination.suffix.lower() in {".jpg", ".jpeg"} or "JPEG" in selected_filter
            image_format = "JPEG" if wants_jpeg else "PNG"
            self.result_image.save(destination, format=image_format, quality=95)
            self.status_label.setText("Result saved")
        except OSError as error:
            LOGGER.exception("result_save_failed error_type=%s", type(error).__name__)
            self._show_error("Save failed", "The result could not be written to that location.")

    def reset(self) -> None:
        self._invalidate_active_generation()
        self.person_image = None
        self.garment_image = None
        self.result_image = None
        self.person_zone.clear("Drop a person image\nJPG · PNG · WebP")
        self.garment_zone.clear("Drop clothing from Explorer or a browser\nJPG · PNG · WebP")
        self.result_viewer.clear("Your generated result appears here")
        self.before_viewer.clear("Person image")
        self.after_viewer.clear("Generated result")
        self.status_label.setText("Reset")
        self._update_actions()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            updated = dialog.config()
            updated.save(self.paths.config_file)
        except (OSError, ValueError) as error:
            self._show_error("Settings", str(error))
            return
        self._invalidate_active_generation()
        self.config = updated
        self._model_loading = True
        self._model_ready = False
        self.service.replace_config(updated)
        self.status_label.setText("Settings saved; loading selected model…")
        self._update_actions()

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def closeEvent(self, event: object) -> None:
        self._auto_timer.stop()
        self._invalidate_active_generation()
        event.accept()  # type: ignore[attr-defined]
