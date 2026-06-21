from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from agent_runtime.core.models import AuditEvent
from agent_runtime.audit.hash_chain import attach_event_hash
from agent_runtime.guard.redaction import redact_secrets


class SQLiteAuditSink:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def write(self, event: AuditEvent | dict[str, Any]) -> None:
        payload = event.to_dict() if isinstance(event, AuditEvent) else event
        payload = redact_secrets(payload)
        with sqlite3.connect(self.path, isolation_level=None) as connection:
            connection.execute("begin immediate")
            try:
                payload = attach_event_hash(payload, self._last_event_hash(connection))
                connection.execute(
                    """
                    insert into audit_events(
                        event_type, run_id, tool_call_id, timestamp, trace_id, tool_name,
                        event_hash, previous_event_hash, payload_json
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload.get("event_type"),
                        payload.get("run_id"),
                        payload.get("tool_call_id"),
                        payload.get("timestamp"),
                        payload.get("trace_id"),
                        payload.get("tool_name"),
                        payload.get("event_hash"),
                        payload.get("previous_event_hash"),
                        json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def query(
        self,
        run_id: str | None = None,
        trace_id: str | None = None,
        tool_name: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "select payload_json from audit_events"
        filters = []
        params: list[Any] = []
        if run_id is not None:
            filters.append("run_id = ?")
            params.append(run_id)
        if trace_id is not None:
            filters.append("trace_id = ?")
            params.append(trace_id)
        if tool_name is not None:
            filters.append("tool_name = ?")
            params.append(tool_name)
        if filters:
            sql += " where " + " and ".join(filters)
        sql += " order by id asc"
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(sql, tuple(params)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def _init_schema(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                create table if not exists audit_events (
                    id integer primary key autoincrement,
                    event_type text not null,
                    run_id text,
                    tool_call_id text,
                    timestamp text,
                    trace_id text,
                    tool_name text,
                    event_hash text,
                    previous_event_hash text,
                    payload_json text not null
                )
                """
            )
            connection.execute("create index if not exists idx_audit_events_run_id on audit_events(run_id)")
            existing_columns = {
                row[1] for row in connection.execute("pragma table_info(audit_events)").fetchall()
            }
            if "trace_id" not in existing_columns:
                connection.execute("alter table audit_events add column trace_id text")
            if "tool_name" not in existing_columns:
                connection.execute("alter table audit_events add column tool_name text")
            if "event_hash" not in existing_columns:
                connection.execute("alter table audit_events add column event_hash text")
            if "previous_event_hash" not in existing_columns:
                connection.execute("alter table audit_events add column previous_event_hash text")
            connection.execute("create index if not exists idx_audit_events_trace_id on audit_events(trace_id)")
            connection.execute("create index if not exists idx_audit_events_tool_name on audit_events(tool_name)")
            connection.execute("create index if not exists idx_audit_events_event_hash on audit_events(event_hash)")

    def _last_event_hash(self, connection: sqlite3.Connection) -> str | None:
        row = connection.execute("select event_hash from audit_events order by id desc limit 1").fetchone()
        return row[0] if row else None
