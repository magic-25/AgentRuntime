from __future__ import annotations

from importlib import import_module
from typing import Any


def stable_public_api() -> dict[str, dict[str, str]]:
    return _resolve_all(
        {
            "agent_runtime.AgentRuntime": "stable",
            "agent_runtime.core.models.ToolDefinition": "stable",
            "agent_runtime.core.models.ToolCall": "stable",
            "agent_runtime.core.models.ToolResult": "stable",
            "agent_runtime.core.models.PolicyDecision": "stable",
            "agent_runtime.core.models.ApprovalRequest": "stable",
            "agent_runtime.core.models.ApprovalDecision": "stable",
            "agent_runtime.core.models.AuditEvent": "stable",
            "agent_runtime.core.registry.ToolRegistry": "stable",
            "agent_runtime.core.runtime.AgentRuntime": "stable",
            "agent_runtime.policy.engine.PolicyEngine": "stable",
            "agent_runtime.approval.base.ApprovalProvider": "stable",
            "agent_runtime.approval.base.CallbackApprovalProvider": "stable",
            "agent_runtime.audit.jsonl.JsonlAuditSink": "stable",
            "agent_runtime.audit.sqlite.SQLiteAuditSink": "stable",
            "agent_runtime.execution.sandbox.SandboxCommandSpec": "stable",
            "agent_runtime.execution.sandbox.SandboxExecutor": "stable",
            "agent_runtime.execution.sandbox.SandboxUnavailableError": "stable",
            "agent_runtime.observer.memory.InMemoryObserver": "stable",
            "agent_runtime.schema.policy_config.policy_config_schema": "stable",
        }
    )


def experimental_public_api() -> dict[str, dict[str, str]]:
    return _resolve_all(
        {
            "agent_runtime.adapters.openai_style.OpenAIStyleAdapter": "experimental",
            "agent_runtime.adapters.langgraph_style.LangGraphStyleAdapter": "experimental",
            "agent_runtime.adapters.mcp_style.MCPStyleAdapter": "experimental",
            "agent_runtime.pilot.records.ProductionPilotReport": "experimental",
            "agent_runtime.pilot.records.PilotScenarioRecord": "experimental",
        }
    )


def _resolve_all(entries: dict[str, str]) -> dict[str, dict[str, str]]:
    return {symbol: {"status": status, "resolved": str(_resolve(symbol))} for symbol, status in entries.items()}


def _resolve(symbol: str) -> Any:
    module_name, attribute = symbol.rsplit(".", 1)
    return getattr(import_module(module_name), attribute)
