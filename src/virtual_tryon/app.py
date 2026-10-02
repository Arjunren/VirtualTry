from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from virtual_tryon.config import AppConfig
from virtual_tryon.infrastructure.logging_config import configure_logging
from virtual_tryon.infrastructure.paths import AppPaths
from virtual_tryon.ui.main_window import MainWindow


def main() -> int:
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    paths = AppPaths.discover()
    paths.ensure_runtime_dirs()
    configure_logging(paths.log_dir)

    app = QApplication(sys.argv)
    app.setApplicationName("VirtualTry")
    app.setOrganizationName("Arjunren")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, False)
    config = AppConfig.load(paths.config_file)
    window = MainWindow(config=config, paths=paths)
    window.show()
    return app.exec()
