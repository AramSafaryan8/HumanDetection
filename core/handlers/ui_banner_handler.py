from PyQt6.QtCore import QObject, pyqtSignal

from core.interfaces import BaseActionHandler, Event, FingerSnapEvent


class _NotificationSignals(QObject):
    notification_requested = pyqtSignal(str, int)


class UIBannerActionHandler(BaseActionHandler):
    """Requests a UI banner without owning or depending on a UI widget."""

    def __init__(self, duration_ms: int = 2500) -> None:
        if duration_ms <= 0:
            raise ValueError("duration_ms must be positive")
        self._duration_ms = duration_ms
        self._signals = _NotificationSignals()

    @property
    def notification_requested(self):
        return self._signals.notification_requested

    def handle_event(self, event: Event) -> None:
        if isinstance(event, FingerSnapEvent):
            message = f"Finger snap detected ({event.hand} hand)"
        else:
            message = f"{event.name} detected"
        self._signals.notification_requested.emit(message, self._duration_ms)
