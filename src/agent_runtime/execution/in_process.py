from __future__ import annotations

from collections.abc import Callable
from typing import Any


class InProcessExecutor:
    def execute(self, func: Callable[..., Any], input: dict[str, Any]) -> Any:
        return func(**input)
