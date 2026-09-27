from typing import Callable, List, Optional, Tuple, Type

import numpy as np

from core.config_manager import ConfigManager
from core.detectors.face_detector import FaceDetector
from core.detectors.finger_snap_detector import FingerSnapDetector
from core.event_bus import EventBus
from core.handlers.console_handler import ConsoleLogActionHandler
from core.handlers.ui_banner_handler import UIBannerActionHandler
from core.interfaces import EVENT_TYPES, BaseActionHandler, BaseDetector, Event
from core.registry import ActionHandlerRegistry, DetectorRegistry


class VisionPipeline:
    """Runs configured detector strategies and routes their events to handlers."""

    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        config_path: str = "config/gestures.json",
        event_bus: Optional[EventBus] = None,
        detector_registry: Optional[DetectorRegistry] = None,
        handler_registry: Optional[ActionHandlerRegistry] = None,
        on_handler_created: Optional[Callable[[BaseActionHandler], None]] = None,
    ) -> None:
        self.config = config or ConfigManager(config_path)
        self.event_bus = event_bus or EventBus()
        self.detector_registry = detector_registry or DetectorRegistry()
        self.handler_registry = handler_registry or ActionHandlerRegistry()
        self.detectors: List[BaseDetector] = []
        self.action_handlers: List[BaseActionHandler] = []
        self._subscriptions: List[Tuple[Type[Event], Callable]] = []
        self._closed = False
        self._register_builtins()

        try:
            self._create_detectors()
            self._subscribe_handlers(on_handler_created)
        except Exception as error:
            try:
                self.close()
            except Exception as close_error:
                raise ExceptionGroup(
                    "Pipeline initialization and cleanup failed",
                    [error, close_error],
                ) from error
            raise

    def _register_builtins(self) -> None:
        built_in_detectors = {
            "FaceDetector": FaceDetector,
            "FingerSnapDetector": FingerSnapDetector,
        }
        for name, detector_type in built_in_detectors.items():
            if name not in self.detector_registry.registered_names():
                self.detector_registry.register(name, detector_type)

        built_in_handlers = {
            "ConsoleLogActionHandler": ConsoleLogActionHandler,
            "UIBannerActionHandler": UIBannerActionHandler,
        }
        for name, handler_type in built_in_handlers.items():
            if name not in self.handler_registry.registered_names():
                self.handler_registry.register(name, handler_type)

    def _create_detectors(self) -> None:
        for item in self.config.get_enabled_detectors():
            detector = self.detector_registry.create(
                item["type"],
                **item.get("params", {}),
            )
            self.detectors.append(detector)

    def _subscribe_handlers(
        self,
        on_handler_created: Optional[Callable[[BaseActionHandler], None]],
    ) -> None:
        actions = self.config.get_all_config()["actions"]
        event_names = dict.fromkeys(action["event_type"] for action in actions)
        for event_name in event_names:
            event_type = EVENT_TYPES[event_name]
            for handler_config in self.config.get_action_handlers_for_event(
                event_name
            ):
                handler = self.handler_registry.create(
                    handler_config["type"],
                    **handler_config.get("params", {}),
                )
                self.action_handlers.append(handler)
                self.event_bus.subscribe(event_type, handler.handle_event)
                self._subscriptions.append((event_type, handler.handle_event))
                if on_handler_created is not None:
                    on_handler_created(handler)

    def process_frame(self, frame: np.ndarray, timestamp: int) -> np.ndarray:
        for detector in self.detectors:
            result = detector.detect(frame, timestamp)
            frame = result.frame
            for event in result.events:
                self.event_bus.publish(event)
        return frame

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        errors = []
        for event_type, event_handler in self._subscriptions:
            self.event_bus.unsubscribe(event_type, event_handler)
        self._subscriptions.clear()
        for detector in self.detectors:
            try:
                detector.close()
            except Exception as error:
                errors.append(error)
        for handler in self.action_handlers:
            try:
                handler.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("Errors while closing the vision pipeline", errors)
