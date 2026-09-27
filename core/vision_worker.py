import logging
import time
from typing import Optional

import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from core.vision_pipeline import VisionPipeline
from core.event_bus import EventBus
from core.registry import ActionHandlerRegistry, DetectorRegistry

logger = logging.getLogger(__name__)

class VisionWorker(QThread):
    frame_signal = pyqtSignal(QImage)
    error_signal = pyqtSignal(str)
    notification_signal = pyqtSignal(str, int)

    def __init__(
        self,
        camera_id: int = 0,
        config_path: str = "config/gestures.json",
        event_bus: Optional[EventBus] = None,
        detector_registry: Optional[DetectorRegistry] = None,
        handler_registry: Optional[ActionHandlerRegistry] = None,
    ) -> None:
        super().__init__()
        self.camera_id = camera_id
        self.config_path = config_path
        self.event_bus = event_bus
        self.detector_registry = detector_registry
        self.handler_registry = handler_registry
        self._is_running = True

    def run(self) -> None:
        capture = cv2.VideoCapture(self.camera_id)
        pipeline = None
        try:
            if not capture.isOpened():
                raise RuntimeError(f"Could not open video source {self.camera_id}")

            fps = capture.get(cv2.CAP_PROP_FPS)
            if not 0 < fps <= 120:
                fps = 30.0
            frame_period_ms = max(1, int(1000 / fps))
            pipeline = VisionPipeline(
                config_path=self.config_path,
                event_bus=self.event_bus,
                detector_registry=self.detector_registry,
                handler_registry=self.handler_registry,
                on_handler_created=self._connect_action_handler,
            )

            clock_started_ns = time.monotonic_ns()
            last_timestamp = -1
            consecutive_read_failures = 0
            while self._is_running:
                frame_started_ns = time.monotonic_ns()
                success, frame = capture.read()
                if not success:
                    consecutive_read_failures += 1
                    if consecutive_read_failures == 1 or consecutive_read_failures % 50 == 0:
                        logger.warning(
                            "Failed to read a frame from video source %s "
                            "(consecutive failures: %s)",
                            self.camera_id,
                            consecutive_read_failures,
                        )
                    self.msleep(100)
                    continue

                consecutive_read_failures = 0
                frame = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
                elapsed_ms = (time.monotonic_ns() - clock_started_ns) // 1_000_000
                timestamp = max(last_timestamp + 1, int(elapsed_ms))
                frame = pipeline.process_frame(frame, timestamp)
                height, width, channels = frame.shape
                image = QImage(
                    frame.data,
                    width,
                    height,
                    channels * width,
                    QImage.Format.Format_RGB888,
                ).copy()
                self.frame_signal.emit(image)
                last_timestamp = timestamp

                spent_ms = (time.monotonic_ns() - frame_started_ns) // 1_000_000
                remaining_ms = frame_period_ms - int(spent_ms)
                if remaining_ms > 0:
                    self.msleep(remaining_ms)
        except Exception as error:
            logger.exception("Vision worker failed")
            self.error_signal.emit(str(error))
        finally:
            capture.release()
            if pipeline is not None:
                try:
                    pipeline.close()
                except Exception as error:
                    logger.exception("Failed to close vision pipeline")
                    self.error_signal.emit(str(error))

    def stop(self) -> None:
        self._is_running = False
        if self.isRunning():
            self.wait()

    def _connect_action_handler(self, handler: object) -> None:
        notification_requested = getattr(handler, "notification_requested", None)
        if notification_requested is not None:
            notification_requested.connect(self.notification_signal.emit)
