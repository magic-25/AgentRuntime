from __future__ import annotations

import hashlib
import json
from typing import Any


HASH_FIELDS = {"event_hash"}


def attach_event_hash(payload: dict[str, Any], previous_event_hash: str | None) -> dict[str, Any]:
    chained = dict(payload)
    chained["previous_event_hash"] = previous_event_hash
    chained["event_hash"] = event_hash(chained)
    return chained


def event_hash(payload: dict[str, Any]) -> str:
    canonical_payload = {key: value for key, value in payload.items() if key not in HASH_FIELDS}
    canonical = json.dumps(canonical_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
