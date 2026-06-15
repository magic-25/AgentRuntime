from __future__ import annotations

from typing import Any


def policy_config_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Agent Runtime Policy Config",
        "type": "object",
        "additionalProperties": True,
        "required": ["version", "default_decision", "rules"],
        "properties": {
            "version": {"const": 1},
            "default_decision": {"type": "string", "enum": ["allow", "deny"]},
            "rules": {
                "type": "array",
                "items": {"$ref": "#/$defs/rule"},
            },
            "tools": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "capabilities_required": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "audit": {
                "type": "object",
                "properties": {
                    "sink": {"type": "string", "enum": ["jsonl", "sqlite"]},
                    "path": {"type": "string"},
                    "on_write_failure": {
                        "type": "object",
                        "additionalProperties": {"type": "string", "enum": ["warn", "fail_closed"]},
                    },
                },
            },
            "tracing": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                },
            },
            "redaction": {
                "type": "object",
                "properties": {
                    "sensitive_fields": {"type": "array", "items": {"type": "string"}},
                },
            },
            "retention": {
                "type": "object",
                "properties": {
                    "audit_days": {"type": "integer", "minimum": 1},
                    "payload_storage": {"type": "string", "enum": ["redacted", "digest_only", "disabled"]},
                },
            },
        },
        "$defs": {
            "rule": {
                "type": "object",
                "additionalProperties": True,
                "required": ["id", "environment", "effect"],
                "properties": {
                    "id": {"type": "string"},
                    "environment": {"type": "string"},
                    "effect": {"type": "string", "enum": ["allow", "deny", "require_approval"]},
                    "tool": {"type": "string"},
                    "capabilities": {"type": "array", "items": {"type": "string"}},
                },
                "anyOf": [{"required": ["tool"]}, {"required": ["capabilities"]}],
            }
        },
    }
