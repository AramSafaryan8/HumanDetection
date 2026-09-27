import copy
import json
from pathlib import Path
from typing import Any, Dict, List

from core.interfaces import EVENT_TYPES


class ConfigManager:
    """Loads and validates detector and event-handler configuration."""

    def __init__(self, config_path: str = "config/gestures.json") -> None:
        path = Path(config_path)
        if not path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent
            path = project_root / path
        try:
            with path.open("r", encoding="utf-8") as config_file:
                config = json.load(config_file)
        except FileNotFoundError as error:
            raise FileNotFoundError(f"Configuration file not found: {path}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON in configuration file {path}: {error}") from error

        self._validate(config)
        self._config: Dict[str, Any] = config

    @staticmethod
    def _validate(config: Any) -> None:
        if not isinstance(config, dict):
            raise ValueError("Configuration root must be a JSON object")

        detectors = config.get("detectors")
        actions = config.get("actions")
        if not isinstance(detectors, list) or not isinstance(actions, list):
            raise ValueError("'detectors' and 'actions' must be JSON arrays")

        detector_ids = set()
        for index, detector in enumerate(detectors):
            location = f"detectors[{index}]"
            if not isinstance(detector, dict):
                raise ValueError(f"{location} must be an object")
            if not isinstance(detector.get("id"), str) or not detector["id"]:
                raise ValueError(f"{location}.id must be a non-empty string")
            if detector["id"] in detector_ids:
                raise ValueError(f"Duplicate detector id: {detector['id']}")
            detector_ids.add(detector["id"])
            if not isinstance(detector.get("type"), str) or not detector["type"]:
                raise ValueError(f"{location}.type must be a non-empty string")
            if not isinstance(detector.get("enabled", True), bool):
                raise ValueError(f"{location}.enabled must be a boolean")
            if not isinstance(detector.get("params", {}), dict):
                raise ValueError(f"{location}.params must be an object")

        for index, action in enumerate(actions):
            location = f"actions[{index}]"
            if not isinstance(action, dict):
                raise ValueError(f"{location} must be an object")
            event_name = action.get("event_type")
            if not isinstance(event_name, str) or event_name not in EVENT_TYPES:
                raise ValueError(
                    f"{location}.event_type must be one of {sorted(EVENT_TYPES)}"
                )
            handlers = action.get("handlers")
            if not isinstance(handlers, list) or not all(
                (
                    isinstance(handler, str)
                    and bool(handler)
                )
                or (
                    isinstance(handler, dict)
                    and isinstance(handler.get("type"), str)
                    and bool(handler["type"])
                    and isinstance(handler.get("params", {}), dict)
                )
                for handler in handlers
            ):
                raise ValueError(
                    f"{location}.handlers must contain names or "
                    "objects with a type and optional params object"
                )

    def get_enabled_detectors(self) -> List[Dict[str, Any]]:
        return [
            copy.deepcopy(detector)
            for detector in self._config["detectors"]
            if detector.get("enabled", True)
        ]

    def get_action_handlers_for_event(self, event_name: str) -> List[Dict[str, Any]]:
        handlers: List[Dict[str, Any]] = []
        for action in self._config["actions"]:
            if action["event_type"] == event_name:
                for handler in action["handlers"]:
                    if isinstance(handler, str):
                        handlers.append({"type": handler, "params": {}})
                    else:
                        handlers.append(copy.deepcopy(handler))
        return handlers

    def get_all_config(self) -> Dict[str, Any]:
        return copy.deepcopy(self._config)
