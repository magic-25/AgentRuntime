from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_runtime.core.models import AuditEvent
from agent_runtime.audit.hash_chain import attach_event_hash
from agent_runtime.guard.redaction import redact_secrets


class JsonlAuditSink:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, event: AuditEvent | dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = event.to_dict() if isinstance(event, AuditEvent) else event
        redacted = redact_secrets(payload)
        redacted = attach_event_hash(redacted, self._last_event_hash())
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(redacted, ensure_ascii=False, sort_keys=True) + "\n")

    def _last_event_hash(self) -> str | None:
        if not self.path.exists():
            return None
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return None
        return json.loads(lines[-1]).get("event_hash")
