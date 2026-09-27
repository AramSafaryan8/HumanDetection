import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Type


@dataclass
class Event:
    name: str
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FingerSnapEvent(Event):
    hand: str = "Unknown"
    confidence: float = 1.0

    def __init__(self, hand: str = "Unknown", confidence: float = 1.0):
        super().__init__(
            name="FingerSnap",
            data={"hand": hand, "confidence": confidence},
        )
        self.hand = hand
        self.confidence = confidence


@dataclass
class FaceDetectedEvent(Event):
    face_count: int = 0

    def __init__(self, face_count: int):
        super().__init__(
            name="FaceDetected",
            data={"face_count": face_count},
        )
        self.face_count = face_count


@dataclass
class FaceLostEvent(Event):
    def __init__(self):
        super().__init__(name="FaceLost")


@dataclass
class DetectionResult:
    frame: Any
    events: List[Event] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseDetector(ABC):
    @abstractmethod
    def detect(self, frame: Any, timestamp: int) -> DetectionResult:
        """Process an RGB NumPy frame and return its annotations and events."""

    def close(self) -> None:
        """Release resources held by this detector."""


class BaseActionHandler(ABC):
    @abstractmethod
    def handle_event(self, event: Event) -> None:
        """Perform the action associated with an event."""

    def close(self) -> None:
        """Release resources held by this handler."""


EVENT_TYPES: Dict[str, Type[Event]] = {
    "FingerSnap": FingerSnapEvent,
    "FaceDetected": FaceDetectedEvent,
    "FaceLost": FaceLostEvent,
}


def register_event_type(name: str, event_type: Type[Event]) -> None:
    if not name:
        raise ValueError("Event type name cannot be empty")
    if not issubclass(event_type, Event):
        raise TypeError("event_type must be an Event subclass")
    existing = EVENT_TYPES.get(name)
    if existing is not None and existing is not event_type:
        raise ValueError(f"Event type '{name}' is already registered")
    EVENT_TYPES[name] = event_type
