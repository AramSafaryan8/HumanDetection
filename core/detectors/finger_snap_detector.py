from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np

from core.interfaces import BaseDetector, DetectionResult, FingerSnapEvent


Point = Tuple[float, float]
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)


@dataclass
class _HandState:
    snap_armed: bool = False
    pinch_started_at_ms: int = 0
    last_snap_at_ms: int = -1_000_000
    last_middle_relative: Optional[Point] = None
    last_timestamp_ms: Optional[int] = None
    peak_velocity: float = 0.0
    travel_toward_palm: float = 0.0


class FingerSnapDetector(BaseDetector):
    """Detects a thumb/middle-finger pinch followed by a fast release motion."""

    def __init__(
        self,
        model_path: str = "assets/hand_landmarker.task",
        contact_threshold: float = 0.25,
        release_threshold: float = 0.55,
        snap_velocity_threshold: float = 1.0,
        min_snap_travel: float = 0.08,
        max_snap_duration_seconds: float = 0.35,
        cooldown_seconds: float = 1.0,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        max_hands: int = 2,
    ) -> None:
        if contact_threshold <= 0 or release_threshold <= contact_threshold:
            raise ValueError("release_threshold must be greater than a positive contact_threshold")
        if snap_velocity_threshold <= 0 or min_snap_travel <= 0:
            raise ValueError("Snap velocity and travel thresholds must be positive")
        if max_snap_duration_seconds <= 0 or cooldown_seconds < 0:
            raise ValueError("Snap duration must be positive and cooldown cannot be negative")

        resolved_model_path = Path(model_path)
        if not resolved_model_path.is_absolute():
            resolved_model_path = Path(__file__).resolve().parents[2] / resolved_model_path
        if not resolved_model_path.is_file():
            raise FileNotFoundError(f"Hand landmark model not found: {resolved_model_path}")

        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=str(resolved_model_path)
            ),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self._contact_threshold = contact_threshold
        self._release_threshold = release_threshold
        self._snap_velocity_threshold = snap_velocity_threshold
        self._min_snap_travel = min_snap_travel
        self._max_snap_duration_ms = int(max_snap_duration_seconds * 1000)
        self._cooldown_ms = int(cooldown_seconds * 1000)
        self._states: Dict[str, _HandState] = {}

    def detect(self, frame: np.ndarray, timestamp: int) -> DetectionResult:
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        result = self._landmarker.detect_for_video(image, timestamp)
        height, width = frame.shape[:2]
        events = []

        for hand_index, landmarks in enumerate(result.hand_landmarks):
            hand = self._handedness(result, hand_index)
            state = self._states.setdefault(hand, _HandState())
            points = [
                (landmark.x, landmark.y)
                for landmark in landmarks
            ]
            self._draw_hand(frame, points, width, height)
            if self._update_state(landmarks, state, timestamp):
                events.append(
                    FingerSnapEvent(
                        hand=hand,
                        confidence=self._confidence(state),
                    )
                )
                state.last_snap_at_ms = timestamp

        return DetectionResult(
            frame=frame,
            events=events,
            metadata={"hand_count": len(result.hand_landmarks)},
        )

    @staticmethod
    def _handedness(result: object, hand_index: int) -> str:
        handedness = getattr(result, "handedness", [])
        if hand_index < len(handedness) and handedness[hand_index]:
            return handedness[hand_index][0].category_name
        return f"Hand {hand_index + 1}"

    def _update_state(self, landmarks: list, state: _HandState, timestamp: int) -> bool:
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        thumb_tip = landmarks[4]
        middle_tip = landmarks[12]

        palm_scale = float(np.hypot(middle_mcp.x - wrist.x, middle_mcp.y - wrist.y))
        if palm_scale <= 1e-6:
            return False

        pinch_distance = float(
            np.hypot(thumb_tip.x - middle_tip.x, thumb_tip.y - middle_tip.y)
        ) / palm_scale
        relative_middle = (
            (middle_tip.x - wrist.x) / palm_scale,
            (middle_tip.y - wrist.y) / palm_scale,
        )
        toward_palm = np.array(
            [wrist.x - middle_mcp.x, wrist.y - middle_mcp.y],
            dtype=np.float64,
        )
        toward_palm /= palm_scale

        velocity = 0.0
        travel = 0.0
        if state.last_middle_relative is not None and state.last_timestamp_ms is not None:
            elapsed_seconds = (timestamp - state.last_timestamp_ms) / 1000.0
            if elapsed_seconds > 0:
                movement = np.array(relative_middle) - np.array(state.last_middle_relative)
                travel = max(0.0, float(np.dot(movement, toward_palm)))
                velocity = travel / elapsed_seconds

        state.last_middle_relative = relative_middle
        state.last_timestamp_ms = timestamp
        is_pinched = pinch_distance <= self._contact_threshold

        if not state.snap_armed and is_pinched:
            state.snap_armed = True
            state.pinch_started_at_ms = timestamp
            state.peak_velocity = 0.0
            state.travel_toward_palm = 0.0

        if not state.snap_armed:
            return False

        elapsed_ms = timestamp - state.pinch_started_at_ms
        if elapsed_ms > self._max_snap_duration_ms:
            state.snap_armed = False
            return False

        state.peak_velocity = max(state.peak_velocity, velocity)
        state.travel_toward_palm += travel
        released = pinch_distance >= self._release_threshold
        if not released:
            return False

        state.snap_armed = False
        outside_cooldown = timestamp - state.last_snap_at_ms >= self._cooldown_ms
        return (
            outside_cooldown
            and state.peak_velocity >= self._snap_velocity_threshold
            and state.travel_toward_palm >= self._min_snap_travel
        )

    def _confidence(self, state: _HandState) -> float:
        velocity_score = state.peak_velocity / (2.0 * self._snap_velocity_threshold)
        travel_score = state.travel_toward_palm / (2.0 * self._min_snap_travel)
        return min(1.0, max(0.0, (velocity_score + travel_score) / 2.0))

    @staticmethod
    def _draw_hand(
        frame: np.ndarray,
        points: list[Point],
        width: int,
        height: int,
    ) -> None:
        pixels = [
            (
                min(max(int(x * width), 0), width - 1),
                min(max(int(y * height), 0), height - 1),
            )
            for x, y in points
        ]
        for start, end in HAND_CONNECTIONS:
            cv2.line(frame, pixels[start], pixels[end], (0, 200, 255), 2)
        for point in pixels:
            cv2.circle(frame, point, 3, (0, 255, 0), -1)

    def close(self) -> None:
        self._landmarker.close()
