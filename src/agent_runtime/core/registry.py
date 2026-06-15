from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_runtime.core.models import ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._callables: dict[str, Callable[..., Any]] = {}

    def tool(
        self,
        name: str,
        description: str = "",
        risk_level: str = "low",
        executor_kind: str = "in_process",
        capabilities_required: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.register(
                ToolDefinition(
                    name=name,
                    description=description,
                    risk_level=risk_level,
                    executor_kind=executor_kind,
                    capabilities_required=capabilities_required or [f"tool.invoke:{name}"],
                    metadata=metadata or {},
                ),
                func,
            )
            return func

        return decorator

    def register(self, definition: ToolDefinition, func: Callable[..., Any]) -> None:
        self._definitions[definition.name] = definition
        self._callables[definition.name] = func

    def register_command(
        self,
        name: str,
        command: dict[str, Any],
        description: str = "",
        risk_level: str = "medium",
        capabilities_required: list[str] | None = None,
        executor_kind: str = "subprocess",
    ) -> None:
        self._definitions[name] = ToolDefinition(
            name=name,
            description=description,
            risk_level=risk_level,
            executor_kind=executor_kind,
            capabilities_required=capabilities_required or [f"tool.invoke:{name}"],
            metadata={"command": command},
        )

    def get(self, name: str) -> ToolDefinition:
        return self._definitions[name]

    def has(self, name: str) -> bool:
        return name in self._definitions

    def callable_for(self, name: str) -> Callable[..., Any]:
        return self._callables[name]

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._definitions.values())
