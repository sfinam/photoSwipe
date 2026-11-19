from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ..media import PreviewService
from ..models import PhotoGroup
from ..session import SessionManager
from ..config import Source


class PreviewSignals(QObject):
    finished = Signal(
        str, int, str, str, int, int
    )  # group id, variant, path, error, width, height


class PreviewWorker(QRunnable):
    def __init__(
        self,
        service: PreviewService,
        group: PhotoGroup,
        variant_index: int,
        max_side: int,
        full_raw: bool,
    ) -> None:
        super().__init__()
        self.service = service
        self.group = group
        self.variant_index = variant_index
        self.max_side = max_side
        self.full_raw = full_raw
        self.signals = PreviewSignals()
        self.cancelled = threading.Event()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self.cancelled.set()

    @Slot()
    def run(self) -> None:
        if self.cancelled.is_set():
            return
        try:
            result = self.service.preview(
                self.group,
                self.variant_index,
                max_side=self.max_side,
                full_raw_decode=self.full_raw,
            )
            if self.cancelled.is_set():
                return
            self.signals.finished.emit(
                self.group.id,
                self.variant_index,
                result.path,
                "",
                result.width,
                result.height,
            )
        except Exception as error:  # noqa: BLE001 - shown to the user
            if self.cancelled.is_set():
                return
            self.signals.finished.emit(
                self.group.id, self.variant_index, "", str(error), 0, 0
            )


class ScanSignals(QObject):
    progress = Signal(str, int, int)
    finished = Signal(object)  # SortSession
    failed = Signal(str)


class ScanWorker(QRunnable):
    def __init__(self, manager: SessionManager, source: Source) -> None:
        super().__init__()
        self.manager = manager
        self.source = source
        self.signals = ScanSignals()
        self.cancelled = threading.Event()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self.cancelled.set()

    @Slot()
    def run(self) -> None:
        try:
            session = self.manager.open(self.source, progress=self._progress)
            if self.cancelled.is_set():
                return
            self.signals.finished.emit(session)
        except Exception as error:  # noqa: BLE001
            if self.cancelled.is_set():
                return
            self.signals.failed.emit(str(error))

    def _progress(self, stage: str, current: int, total: int) -> None:
        if self.cancelled.is_set():
            raise RuntimeError("Сканирование отменено")
        self.signals.progress.emit(stage, current, total)
