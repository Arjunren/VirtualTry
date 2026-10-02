from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from virtual_tryon.config import AppConfig


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent: object | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setWindowTitle("VirtualTry Settings")
        self.setMinimumWidth(580)
        self._source = config

        self.engine = QComboBox()
        self.engine.addItem("Mock preview (no model)", "mock")
        self.engine.addItem("CatVTON (local, non-commercial)", "catvton")
        self.engine.setCurrentIndex(max(0, self.engine.findData(config.engine)))

        self.repo = QLineEdit(config.catvton_repo_path)
        self.checkpoint = QLineEdit(config.catvton_checkpoint_path)
        self.base_model = QLineEdit(config.catvton_base_model_path)
        self.resolution = QComboBox()
        self.resolution.addItem("384 × 512 (lower VRAM)", (384, 512))
        self.resolution.addItem("768 × 1024 (recommended quality)", (768, 1024))
        self.resolution.setCurrentIndex(max(0, self.resolution.findData((config.output_width, config.output_height))))
        self.steps = QSpinBox()
        self.steps.setRange(10, 100)
        self.steps.setValue(config.inference_steps)
        self.guidance = QDoubleSpinBox()
        self.guidance.setRange(0.0, 7.5)
        self.guidance.setSingleStep(0.5)
        self.guidance.setValue(config.guidance_scale)
        self.device = QComboBox()
        for label, value in (("Automatic", "auto"), ("NVIDIA CUDA", "cuda"), ("CPU (very slow)", "cpu")):
            self.device.addItem(label, value)
        self.device.setCurrentIndex(max(0, self.device.findData(config.device)))
        self.precision = QComboBox()
        for value in ("auto", "fp16", "bf16", "fp32"):
            self.precision.addItem(value, value)
        self.precision.setCurrentIndex(max(0, self.precision.findData(config.precision)))
        self.auto_generate = QCheckBox()
        self.auto_generate.setChecked(config.automatic_generation)
        self.remote_images = QCheckBox()
        self.remote_images.setChecked(config.allow_remote_images)

        form = QFormLayout()
        form.addRow("Engine", self.engine)
        form.addRow("CatVTON source checkout", self.repo)
        form.addRow("CatVTON checkpoints", self.checkpoint)
        form.addRow("SD inpainting base", self.base_model)
        form.addRow("Output resolution", self.resolution)
        form.addRow("Inference steps", self.steps)
        form.addRow("Guidance scale", self.guidance)
        form.addRow("Device", self.device)
        form.addRow("Precision", self.precision)
        form.addRow("Generate after garment drop", self.auto_generate)
        form.addRow("Allow secure HTTPS image fetch", self.remote_images)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def config(self) -> AppConfig:
        width, height = self.resolution.currentData()
        value = replace(
            self._source,
            engine=self.engine.currentData(),
            catvton_repo_path=self.repo.text().strip(),
            catvton_checkpoint_path=self.checkpoint.text().strip(),
            catvton_base_model_path=self.base_model.text().strip(),
            output_width=width,
            output_height=height,
            inference_steps=self.steps.value(),
            guidance_scale=self.guidance.value(),
            device=self.device.currentData(),
            precision=self.precision.currentData(),
            automatic_generation=self.auto_generate.isChecked(),
            allow_remote_images=self.remote_images.isChecked(),
        )
        value.validate()
        return value
