import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.config_manager import ConfigManager
from core.detectors.finger_snap_detector import FingerSnapDetector, _HandState
from core.event_bus import EventBus
from core.interfaces import (
    BaseActionHandler,
    BaseDetector,
    DetectionResult,
    Event,
    FaceDetectedEvent,
    FingerSnapEvent,
)
from core.registry import ActionHandlerRegistry, DetectorRegistry
from core.vision_pipeline import VisionPipeline


class _FakeDetector(BaseDetector):
    def detect(self, frame, timestamp):
        return DetectionResult(frame)


class _FakeHandler(BaseActionHandler):
    def handle_event(self, event):
        pass


class FrameworkTests(unittest.TestCase):
    def test_event_bus_routes_subclasses_and_unsubscribes(self):
        bus = EventBus()
        received = []
        base_handler = received.append
        snap_handler = received.append
        bus.subscribe(Event, base_handler)
        bus.subscribe(FingerSnapEvent, snap_handler)

        event = FingerSnapEvent(hand="Left")
        bus.publish(event)
        self.assertEqual(received, [event])

        bus.unsubscribe(FingerSnapEvent, snap_handler)
        bus.publish(FaceDetectedEvent(face_count=1))
        self.assertEqual(len(received), 2)

    def test_configuration_loads_handler_parameters_and_rejects_invalid_data(self):
        config = ConfigManager()
        handlers = config.get_action_handlers_for_event("FingerSnap")
        self.assertEqual(handlers[0]["type"], "UIBannerActionHandler")
        self.assertEqual(handlers[0]["params"]["duration_ms"], 2500)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps({"detectors": [], "actions": "invalid"}))
            with self.assertRaisesRegex(ValueError, "'detectors' and 'actions'"):
                ConfigManager(str(path))

    def test_registry_creates_registered_components(self):
        detectors = DetectorRegistry()
        detectors.register("fake", _FakeDetector)
        self.assertIsInstance(detectors.create("fake"), _FakeDetector)

        handlers = ActionHandlerRegistry()
        handlers.register("fake", _FakeHandler)
        self.assertIsInstance(handlers.create("fake"), _FakeHandler)
        with self.assertRaisesRegex(ValueError, "Unknown detector"):
            detectors.create("missing")

    def test_pipeline_combines_repeated_event_action_mappings(self):
        config_data = {
            "detectors": [],
            "actions": [
                {"event_type": "FingerSnap", "handlers": ["fake"]},
                {"event_type": "FingerSnap", "handlers": ["fake"]},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config_data))
            handler_registry = ActionHandlerRegistry()
            handler_registry.register("fake", _FakeHandler)
            pipeline = VisionPipeline(
                config=ConfigManager(str(path)),
                detector_registry=DetectorRegistry(),
                handler_registry=handler_registry,
            )
            self.assertEqual(len(pipeline.action_handlers), 2)
            pipeline.close()

    def test_snap_state_requires_pinch_release_and_fast_palmward_motion(self):
        detector = object.__new__(FingerSnapDetector)
        detector._contact_threshold = 0.25
        detector._release_threshold = 0.55
        detector._snap_velocity_threshold = 1.0
        detector._min_snap_travel = 0.08
        detector._max_snap_duration_ms = 350
        detector._cooldown_ms = 1000
        state = _HandState()

        self.assertFalse(detector._update_state(self._landmarks(0.40, 0.40), state, 0))
        self.assertFalse(detector._update_state(self._landmarks(0.42, 0.421), state, 40))
        self.assertFalse(detector._update_state(self._landmarks(0.50, 0.421), state, 80))
        self.assertTrue(detector._update_state(self._landmarks(0.54, 0.421), state, 120))
        self.assertFalse(detector._update_state(self._landmarks(0.54, 0.421), state, 160))

    @staticmethod
    def _landmarks(middle_tip_y, thumb_tip_y):
        landmarks = [
            SimpleNamespace(x=0.5, y=0.8)
            for _ in range(21)
        ]
        landmarks[4] = SimpleNamespace(x=0.5, y=thumb_tip_y)
        landmarks[9] = SimpleNamespace(x=0.5, y=0.6)
        landmarks[12] = SimpleNamespace(x=0.5, y=middle_tip_y)
        return landmarks


if __name__ == "__main__":
    unittest.main()
