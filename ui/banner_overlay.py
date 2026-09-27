from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QLabel, QWidget


class BannerOverlay(QLabel):
    """Small transient banner widget that overlays its parent."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setMinimumWidth(280)
        self.setMaximumWidth(600)
        self.setMargin(12)
        self.setStyleSheet(
            "background-color: #286b45; color: white; border-radius: 8px; "
            "font-size: 16px; font-weight: bold;"
        )
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, message: str, duration_ms: int = 2500) -> None:
        self.setStyleSheet(
            "background-color: #286b45; color: white; border-radius: 8px; "
            "font-size: 16px; font-weight: bold;"
        )
        self._show_for(message, duration_ms)

    def show_error(self, message: str) -> None:
        self.setStyleSheet(
            "background-color: #a83232; color: white; border-radius: 8px; "
            "font-size: 15px; font-weight: bold;"
        )
        self._show_for(message, 6000)

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.move((parent.width() - self.width()) // 2, 16)

    def _show_for(self, message: str, duration_ms: int) -> None:
        self.setText(message)
        self.adjustSize()
        self.reposition()
        self.raise_()
        self.show()
        self._hide_timer.start(max(1, duration_ms))
