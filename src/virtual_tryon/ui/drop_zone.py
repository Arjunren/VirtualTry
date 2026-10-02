from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent

from virtual_tryon.imaging.drop_parser import parse_mime_data
from virtual_tryon.ui.image_viewer import ImageViewer


class DropZone(ImageViewer):
    dropped = Signal(object)
    clicked = Signal()

    def __init__(self, empty_text: str, parent: object | None = None) -> None:
        super().__init__(empty_text, parent)  # type: ignore[arg-type]
        self.setAcceptDrops(True)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if parse_mime_data(event.mimeData()):
            event.acceptProposedAction()
            self.setProperty("dragActive", True)
            self.style().polish(self)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: object) -> None:
        self.setProperty("dragActive", False)
        self.style().polish(self)
        super().dragLeaveEvent(event)  # type: ignore[arg-type]

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("dragActive", False)
        self.style().polish(self)
        candidates = parse_mime_data(event.mimeData())
        if candidates:
            event.acceptProposedAction()
            self.dropped.emit(candidates)
        else:
            event.ignore()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)
