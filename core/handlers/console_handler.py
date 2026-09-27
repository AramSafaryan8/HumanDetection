import logging

from core.interfaces import BaseActionHandler, Event


class ConsoleLogActionHandler(BaseActionHandler):
    """Writes event summaries through Python's configurable logging system."""

    def __init__(self, logger_name: str = "human_detection.events") -> None:
        self._logger = logging.getLogger(logger_name)

    def handle_event(self, event: Event) -> None:
        self._logger.info("%s event: %s", event.name, event.data)
