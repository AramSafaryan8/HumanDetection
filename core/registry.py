from typing import Any, Dict, Type, TypeVar

from core.interfaces import BaseActionHandler, BaseDetector


ComponentType = TypeVar("ComponentType")


class _Registry:
    def __init__(self, base_type: Type[ComponentType], component_name: str) -> None:
        self._base_type = base_type
        self._component_name = component_name
        self._components: Dict[str, Type[ComponentType]] = {}

    def register(self, name: str, component_class: Type[ComponentType]) -> None:
        if not name:
            raise ValueError(f"{self._component_name} name cannot be empty")
        if not issubclass(component_class, self._base_type):
            raise TypeError(
                f"{self._component_name} must extend "
                f"{self._base_type.__name__}"
            )
        existing = self._components.get(name)
        if existing is not None and existing is not component_class:
            raise ValueError(f"{self._component_name} '{name}' is already registered")
        self._components[name] = component_class

    def create(self, name: str, **kwargs: Any) -> ComponentType:
        try:
            component_class = self._components[name]
        except KeyError as error:
            raise ValueError(
                f"Unknown {self._component_name.lower()} '{name}'. "
                f"Registered names: {sorted(self._components)}"
            ) from error
        return component_class(**kwargs)

    def registered_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._components))


class DetectorRegistry(_Registry):
    def __init__(self) -> None:
        super().__init__(BaseDetector, "Detector")


class ActionHandlerRegistry(_Registry):
    def __init__(self) -> None:
        super().__init__(BaseActionHandler, "Action handler")
