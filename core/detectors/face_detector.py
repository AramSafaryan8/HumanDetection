from pathlib import Path
from typing import Any, List

import cv2
import mediapipe as mp
import numpy as np

from core.interfaces import (
    BaseDetector,
    DetectionResult,
    FaceDetectedEvent,
    FaceLostEvent,
)


class FaceDetector(BaseDetector):
    """MediaPipe face-landmark strategy that emits face-presence transitions."""

    def __init__(
        self,
        model_path: str = "assets/face_landmarker.task",
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        max_faces: int = 2,
    ) -> None:
        resolved_model_path = Path(model_path)
        if not resolved_model_path.is_absolute():
            resolved_model_path = Path(__file__).resolve().parents[2] / resolved_model_path
        if not resolved_model_path.is_file():
            raise FileNotFoundError(f"Face landmark model not found: {resolved_model_path}")

        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=str(resolved_model_path)
            ),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=max_faces,
            min_face_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        self._last_face_count = 0

    def detect(self, frame: np.ndarray, timestamp: int) -> DetectionResult:
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        result = self._landmarker.detect_for_video(image, timestamp)
        faces: List[Any] = result.face_landmarks
        face_count = len(faces)
        height, width = frame.shape[:2]

        for face in faces:
            for landmark in face:
                x = min(max(int(landmark.x * width), 0), width - 1)
                y = min(max(int(landmark.y * height), 0), height - 1)
                cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)

        events = []
        if self._last_face_count == 0 and face_count > 0:
            events.append(FaceDetectedEvent(face_count))
        elif self._last_face_count > 0 and face_count == 0:
            events.append(FaceLostEvent())
        elif face_count > 0 and face_count != self._last_face_count:
            events.append(FaceDetectedEvent(face_count))
        self._last_face_count = face_count

        return DetectionResult(
            frame=frame,
            events=events,
            metadata={"face_count": face_count},
        )

    def close(self) -> None:
        self._landmarker.close()
