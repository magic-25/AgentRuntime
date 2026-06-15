from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from agent_runtime.audit.hash_chain import event_hash


@dataclass(frozen=True)
class AuditVerificationResult:
    valid: bool
    checked_events: int
    error: str | None = None
    index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_audit_chain(path: str | Path, sink: Literal["jsonl", "sqlite"]) -> AuditVerificationResult:
    events = _read_jsonl(path) if sink == "jsonl" else _read_sqlite(path)
    previous_hash = None
    for index, event in enumerate(events):
        if event.get("previous_event_hash") != previous_hash:
            return AuditVerificationResult(
                valid=False,
                checked_events=index + 1,
                error="previous_event_hash_mismatch",
                index=index,
            )
        if event.get("event_hash") != event_hash(event):
            return AuditVerificationResult(
                valid=False,
                checked_events=index + 1,
                error="event_hash_mismatch",
                index=index,
            )
        previous_hash = event.get("event_hash")
    return AuditVerificationResult(valid=True, checked_events=len(events))


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    if not input_path.exists():
        return []
    return [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_sqlite(path: str | Path) -> list[dict[str, Any]]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute("select payload_json from audit_events order by id asc").fetchall()
    return [json.loads(row[0]) for row in rows]
