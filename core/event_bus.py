import threading
from collections import defaultdict
from typing import Callable, DefaultDict, List, Type

from core.interfaces import Event


EventHandler = Callable[[Event], None]


class EventBus:
    """Thread-safe publisher/subscriber bus with base-event subscriptions."""

    def __init__(self) -> None:
        self._subscribers: DefaultDict[Type[Event], List[EventHandler]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: Type[Event], handler: EventHandler) -> None:
        if not isinstance(event_type, type) or not issubclass(event_type, Event):
            raise TypeError("event_type must be an Event subclass")
        with self._lock:
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[Event], handler: EventHandler) -> None:
        with self._lock:
            if handler in self._subscribers.get(event_type, []):
                self._subscribers[event_type].remove(handler)

    def publish(self, event: Event) -> None:
        if not isinstance(event, Event):
            raise TypeError("Only Event instances can be published")

        with self._lock:
            handlers = list(self._subscribers.get(Event, []))
            for event_type, subscribers in self._subscribers.items():
                if event_type is not Event and isinstance(event, event_type):
                    handlers.extend(subscribers)

        for handler in dict.fromkeys(handlers):
            handler(event)
