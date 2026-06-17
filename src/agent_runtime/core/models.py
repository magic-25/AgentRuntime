from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"
    executor_kind: str = "in_process"
    capabilities_required: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeProfile:
    environment: str
    execution_mode: str = "runtime_tools"
    max_tool_calls: int = 1
    network_access: bool = False
    sandbox_required: bool = False
    approval_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentMetadata:
    agent_id: str
    name: str
    provider: str
    framework: str
    version: str = ""
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    runtime_profile: RuntimeProfile = field(default_factory=lambda: RuntimeProfile(environment="dev"))
    lifecycle_events: list[str] = field(
        default_factory=lambda: ["AgentRegistered", "AgentRunStarted", "AgentRunFinished"]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolCall:
    tool_call_id: str
    run_id: str
    tool_name: str
    input: dict[str, Any]
    actor: dict[str, Any]
    environment: str
    trace_id: str | None = None
    span_id: str | None = None
    agent_id: str | None = None
    requested_at: str = field(default_factory=utc_now)
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        tool_name: str,
        input: dict[str, Any],
        actor: dict[str, Any],
        environment: str,
        run_id: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        agent_id: str | None = None,
    ) -> "ToolCall":
        return cls(
            tool_call_id=f"tc_{uuid4().hex}",
            run_id=run_id or f"run_{uuid4().hex}",
            trace_id=trace_id or f"trace_{uuid4().hex}",
            span_id=span_id or f"span_{uuid4().hex}",
            agent_id=agent_id,
            tool_name=tool_name,
            input=input,
            actor=actor,
            environment=environment,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reason: str
    rule_id: str | None = None
    capability: str | None = None
    environment: str | None = None
    actor: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    run_id: str
    tool_call_id: str
    actor: dict[str, Any]
    environment: str
    tool_name: str
    reason: str
    input_summary: dict[str, Any]
    policy_rule_id: str | None = None
    risk_level: str = "medium"


@dataclass(frozen=True)
class ApprovalDecision:
    approved: bool
    reason: str = ""
    timed_out: bool = False


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    output: Any = None
    status: str = "success"
    error: str | None = None
    run_id: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    run_id: str
    tool_call_id: str | None = None
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    trace_id: str | None = None
    span_id: str | None = None
    tool_name: str | None = None
    timestamp: str = field(default_factory=utc_now)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
