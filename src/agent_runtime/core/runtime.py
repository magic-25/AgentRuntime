from __future__ import annotations

import json
import subprocess
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from agent_runtime.approval.base import ApprovalProvider, StaticApprovalProvider
from agent_runtime.audit.jsonl import JsonlAuditSink
from agent_runtime.audit.sqlite import SQLiteAuditSink
from agent_runtime.core.agent_session import RegisteredAgent
from agent_runtime.core.models import (
    AgentMetadata,
    AgentRunRequest,
    AgentRunResult,
    ApprovalRequest,
    AuditEvent,
    RuntimeProfile,
    ToolCall,
    ToolResult,
    utc_now,
)
from agent_runtime.core.registry import ToolRegistry
from agent_runtime.execution.in_process import InProcessExecutor
from agent_runtime.execution.sandbox import (
    SandboxCommandSpec,
    SandboxExecutor,
    SandboxUnavailableError,
    SandboxViolationError,
    UnavailableSandboxExecutor,
)
from agent_runtime.execution.subprocess import SubprocessExecutor
from agent_runtime.guard.redaction import redact_secrets
from agent_runtime.policy.engine import PolicyEngine


class AgentRuntime:
    def __init__(
        self,
        config: dict[str, Any],
        approval_provider: ApprovalProvider | None = None,
        policy_hook: Any | None = None,
        observer: Any | None = None,
        sandbox_executor: SandboxExecutor | None = None,
    ) -> None:
        self.config = config
        self.registry = ToolRegistry()
        self.approval_provider = approval_provider or StaticApprovalProvider(
            approved=False,
            reason="approval_provider.missing",
        )
        self.policy_hook = policy_hook
        self.observer = observer
        audit_config = config.get("audit", {})
        audit_path = audit_config.get("path", ".agent-runtime/audit.jsonl")
        self.audit_sink = SQLiteAuditSink(audit_path) if audit_config.get("sink") == "sqlite" else JsonlAuditSink(audit_path)
        self.executor = InProcessExecutor()
        self.subprocess_executor = SubprocessExecutor()
        self.sandbox_executor = sandbox_executor or UnavailableSandboxExecutor()
        self._audit_event_types: list[str] = []
        self._audit_event_cursor = 0
        self._agent_trace_context: dict[str, Any] | None = None

    @classmethod
    def from_dict(
        cls,
        config: dict[str, Any],
        approval_provider: ApprovalProvider | None = None,
        policy_hook: Any | None = None,
        observer: Any | None = None,
        sandbox_executor: SandboxExecutor | None = None,
    ) -> "AgentRuntime":
        return cls(
            config=config,
            approval_provider=approval_provider,
            policy_hook=policy_hook,
            observer=observer,
            sandbox_executor=sandbox_executor,
        )

    @classmethod
    def from_config(
        cls,
        path: str | Path,
        approval_provider: ApprovalProvider | None = None,
        policy_hook: Any | None = None,
        observer: Any | None = None,
        sandbox_executor: SandboxExecutor | None = None,
    ) -> "AgentRuntime":
        config = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(
            config,
            approval_provider=approval_provider,
            policy_hook=policy_hook,
            observer=observer,
            sandbox_executor=sandbox_executor,
        )

    def tool(self, *args: Any, **kwargs: Any) -> Any:
        return self.registry.tool(*args, **kwargs)

    def register_agent(
        self,
        agent_id: str,
        agent: Any,
        actor: dict[str, Any],
        environment: str,
        metadata: AgentMetadata | dict[str, Any] | None = None,
    ) -> RegisteredAgent:
        normalized = self._normalize_agent_metadata(agent_id, metadata, environment)
        self._audit_event_cursor = len(self._audit_event_types)
        registration_audit_ok = self._audit_agent_event(
            "AgentRegistered",
            agent_id,
            {"actor": actor, "environment": environment, "metadata": normalized.to_dict()},
            environment=environment,
        )
        return RegisteredAgent(
            self,
            agent_id,
            agent,
            actor,
            environment,
            normalized,
            registration_audit_ok=registration_audit_ok,
        )

    def run_agent(
        self,
        agent_id: str,
        agent: Any,
        prompt: str | AgentRunRequest,
        actor: dict[str, Any],
        environment: str,
        metadata: AgentMetadata | dict[str, Any] | None = None,
    ) -> AgentRunResult:
        return self.register_agent(
            agent_id,
            agent,
            actor=actor,
            environment=environment,
            metadata=metadata,
        ).run_session(prompt)

    def _normalize_agent_metadata(
        self,
        agent_id: str,
        metadata: AgentMetadata | dict[str, Any] | None,
        environment: str,
    ) -> AgentMetadata:
        if isinstance(metadata, AgentMetadata):
            return metadata
        if isinstance(metadata, dict):
            runtime_profile = metadata.get("runtime_profile", RuntimeProfile(environment=environment))
            if isinstance(runtime_profile, dict):
                runtime_profile = RuntimeProfile(**runtime_profile)
            return AgentMetadata(
                agent_id=metadata.get("agent_id", agent_id),
                name=metadata.get("name", agent_id),
                provider=metadata.get("provider", "unknown"),
                framework=metadata.get("framework", "unknown"),
                version=metadata.get("version", ""),
                description=metadata.get("description", ""),
                capabilities=list(metadata.get("capabilities", [])),
                runtime_profile=runtime_profile,
                lifecycle_events=list(
                    metadata.get("lifecycle_events", ["AgentRegistered", "AgentRunStarted", "AgentRunFinished"])
                ),
            )
        return AgentMetadata(
            agent_id=agent_id,
            name=agent_id,
            provider=getattr(metadata, "provider", "unknown"),
            framework="unknown",
            runtime_profile=RuntimeProfile(environment=environment),
        )

    def command_tool(
        self,
        name: str,
        argv: list[str],
        cwd: str,
        env: dict[str, str] | None = None,
        env_allowlist: list[str] | None = None,
        timeout_ms: int = 30000,
        stdout_limit_bytes: int = 65536,
        stderr_limit_bytes: int = 65536,
        description: str = "",
        risk_level: str = "medium",
        capabilities_required: list[str] | None = None,
    ) -> None:
        self.registry.register_command(
            name=name,
            description=description,
            risk_level=risk_level,
            command={
                "argv": argv,
                "cwd": str(cwd),
                "env": env or {},
                "env_allowlist": env_allowlist or [],
                "timeout_ms": timeout_ms,
                "stdout_limit_bytes": stdout_limit_bytes,
                "stderr_limit_bytes": stderr_limit_bytes,
            },
            capabilities_required=capabilities_required or [f"tool.invoke:{name}", f"command.execute:{argv[0]}"],
        )

    def sandboxed_command_tool(
        self,
        name: str,
        argv: list[str],
        cwd: str,
        env: dict[str, str] | None = None,
        env_allowlist: list[str] | None = None,
        timeout_ms: int = 30000,
        stdout_limit_bytes: int = 65536,
        stderr_limit_bytes: int = 65536,
        description: str = "",
        risk_level: str = "medium",
        capabilities_required: list[str] | None = None,
        network_access: bool = False,
        read_paths: list[str] | None = None,
        write_paths: list[str] | None = None,
    ) -> None:
        self.registry.register_command(
            name=name,
            description=description,
            risk_level=risk_level,
            command={
                "argv": argv,
                "cwd": str(cwd),
                "env": env or {},
                "env_allowlist": env_allowlist or [],
                "timeout_ms": timeout_ms,
                "stdout_limit_bytes": stdout_limit_bytes,
                "stderr_limit_bytes": stderr_limit_bytes,
                "isolation_level": "strong",
                "network_access": network_access,
                "read_paths": read_paths or [],
                "write_paths": write_paths or [],
            },
            capabilities_required=capabilities_required or [f"tool.invoke:{name}", f"command.execute:{argv[0]}"],
            executor_kind="sandboxed_subprocess",
        )

    def call_tool(
        self,
        tool_name: str,
        input: dict[str, Any],
        actor: dict[str, Any],
        environment: str,
        adapter_source: str | None = None,
    ) -> ToolResult:
        call = ToolCall.create(
            tool_name=tool_name,
            input=self._redact(input),
            actor=actor,
            environment=environment,
            trace_id=self._agent_trace_context.get("trace_id") if self._agent_trace_context else None,
            agent_id=self._agent_trace_context.get("agent_id") if self._agent_trace_context else None,
        )
        metadata = {"adapter_source": adapter_source} if adapter_source else {}
        if self._agent_trace_context:
            metadata = {
                **metadata,
                "agent_id": self._agent_trace_context["agent_id"],
                "parent_span_id": self._agent_trace_context["agent_span_id"],
            }
        span_started_at = perf_counter()
        if not self._audit("ToolCallRequested", call, {"input": call.input, **metadata}, environment=environment):
            result = ToolResult(
                tool_call_id=call.tool_call_id,
                status="denied",
                error="audit.write_failed",
                run_id=call.run_id,
            )
            self._observe_result(result)
            return result
        if self._tracing_enabled():
            if not self._audit(
                "TraceSpanStarted",
                call,
                {
                    "span_kind": "tool_call",
                    "started_at": call.requested_at,
                    "status": "started",
                    **metadata,
                },
                environment=environment,
            ):
                result = self._audit_write_failed_result(call)
                self._observe_result(result)
                return result

        max_tool_calls_error = self._agent_max_tool_calls_error()
        if max_tool_calls_error is not None:
            return self._execution_error(
                call,
                max_tool_calls_error,
                max_tool_calls_error,
                span_started_at,
                metadata,
                status="denied",
            )

        engine = PolicyEngine(self.config, self.registry)
        policy_span_id = f"span_{uuid4().hex}"
        policy_started_at = perf_counter()
        if self._tracing_enabled():
            if not self._audit_trace_span_for_call(
                "TraceSpanStarted",
                call,
                policy_span_id,
                {
                    "span_kind": "policy_evaluation",
                    "parent_span_id": call.span_id,
                    "started_at": utc_now(),
                    "status": "started",
                    "policy_version": self.config.get("version", 1),
                    **metadata,
                },
                environment=environment,
            ):
                result = self._audit_write_failed_result(call)
                self._observe_result(result)
                return result
        decision = engine.evaluate(tool_name, environment, actor)
        if self.policy_hook is not None:
            try:
                self.policy_hook(
                    {
                        "tool_name": tool_name,
                        "input": call.input,
                        "actor": actor,
                        "environment": environment,
                        "policy_decision": decision,
                    }
                )
            except Exception as error:
                result = ToolResult(
                    tool_call_id=call.tool_call_id,
                    status="denied",
                    error="policy.hook_failed",
                    run_id=call.run_id,
                )
                if self._tracing_enabled():
                    if not self._finish_policy_trace_span(
                        call,
                        policy_span_id,
                        policy_started_at,
                        decision,
                        metadata,
                        status="denied",
                        error="policy.hook_failed",
                    ):
                        result = self._audit_write_failed_result(call)
                        self._observe_result(result)
                        return result
                if not self._audit(
                    "PolicyEvaluated",
                    call,
                    {
                        "decision": "deny",
                        "rule_id": decision.rule_id,
                        "capability": decision.capability,
                        "environment": environment,
                        "actor": actor,
                        "policy_version": self.config.get("version", 1),
                    },
                ):
                    result = self._audit_write_failed_result(call)
                    self._observe_result(result)
                    return result
                if not self._audit("RuntimeError", call, {"error": "policy.hook_failed", "message": str(error)}):
                    result = self._audit_write_failed_result(call)
                    self._observe_result(result)
                    return result
                self._finish_tool_trace_span(
                    call,
                    span_started_at,
                    metadata,
                    status=result.status,
                    decision="deny",
                    reason="policy.hook_failed",
                    error="policy.hook_failed",
                )
                self._observe_result(result)
                return result
        if self._tracing_enabled():
            if not self._finish_policy_trace_span(call, policy_span_id, policy_started_at, decision, metadata):
                result = self._audit_write_failed_result(call)
                self._observe_result(result)
                return result
        if not self._audit(
            "PolicyEvaluated",
            call,
            {
                "decision": decision.decision,
                "rule_id": decision.rule_id,
                "capability": decision.capability,
                "environment": decision.environment,
                "actor": decision.actor,
                "policy_version": self.config.get("version", 1),
            },
        ):
            result = self._audit_write_failed_result(call)
            self._observe_result(result)
            return result

        approval_requirement_error = (
            self._agent_approval_requirement_error(decision, self.registry.get(tool_name))
            if decision.decision == "allow"
            else None
        )
        if approval_requirement_error is not None:
            return self._execution_error(
                call,
                approval_requirement_error,
                approval_requirement_error,
                span_started_at,
                metadata,
                status="denied",
            )

        if decision.decision == "deny":
            result = ToolResult(tool_call_id=call.tool_call_id, status="denied", error=decision.reason, run_id=call.run_id)
            if not self._audit("RuntimeError", call, {"error": decision.reason}):
                result = self._audit_write_failed_result(call)
            self._finish_tool_trace_span(
                call,
                span_started_at,
                metadata,
                status=result.status,
                decision=decision.decision,
                reason=decision.reason,
                error=decision.reason,
            )
            self._observe_result(result)
            return result

        if decision.decision == "require_approval":
            self._observe_approval_requested()
            if not self._audit("ApprovalRequested", call, {"rule_id": decision.rule_id}):
                result = self._audit_write_failed_result(call)
                self._observe_result(result)
                return result
            approval_span_id = f"span_{uuid4().hex}"
            approval_started_at = perf_counter()
            approval_risk_level = self.registry.get(tool_name).risk_level
            if self._tracing_enabled():
                if not self._audit_trace_span_for_call(
                    "TraceSpanStarted",
                    call,
                    approval_span_id,
                    {
                        "span_kind": "approval_gate",
                        "parent_span_id": call.span_id,
                        "started_at": utc_now(),
                        "status": "started",
                        "rule_id": decision.rule_id,
                        "risk_level": approval_risk_level,
                        **metadata,
                    },
                    environment=environment,
                ):
                    result = self._audit_write_failed_result(call)
                    self._observe_result(result)
                    return result
            approval = self.approval_provider.request(
                ApprovalRequest(
                    approval_id=f"appr_{uuid4().hex}",
                    run_id=call.run_id,
                    tool_call_id=call.tool_call_id,
                    actor=actor,
                    environment=environment,
                    tool_name=tool_name,
                    reason=decision.reason,
                    input_summary=call.input,
                    policy_rule_id=decision.rule_id,
                    risk_level=approval_risk_level,
                )
            )
            approval_reason = "approval.timeout" if approval.timed_out else approval.reason
            if not self._audit("ApprovalResolved", call, {"approved": approval.approved, "reason": approval_reason}):
                result = self._audit_write_failed_result(call)
                self._observe_result(result)
                return result
            if self._tracing_enabled():
                approval_status = "timeout" if approval.timed_out else "approved" if approval.approved else "rejected"
                if not self._audit_trace_span_for_call(
                    "TraceSpanFinished",
                    call,
                    approval_span_id,
                    {
                        "span_kind": "approval_gate",
                        "parent_span_id": call.span_id,
                        "finished_at": utc_now(),
                        "duration_ms": int((perf_counter() - approval_started_at) * 1000),
                        "status": approval_status,
                        "approved": approval.approved,
                        "reason": approval_reason,
                        "timed_out": approval.timed_out,
                        "rule_id": decision.rule_id,
                        "risk_level": approval_risk_level,
                        **metadata,
                    },
                    environment=environment,
                ):
                    result = self._audit_write_failed_result(call)
                    self._observe_result(result)
                    return result
            if not approval.approved:
                error = "approval.timeout" if approval.timed_out else approval.reason or "approval_rejected"
                result = ToolResult(
                    tool_call_id=call.tool_call_id,
                    status="rejected",
                    error=error,
                    run_id=call.run_id,
                )
                self._finish_tool_trace_span(
                    call,
                    span_started_at,
                    metadata,
                    status=result.status,
                    decision=decision.decision,
                    reason=approval_reason,
                    error=error,
                )
                self._observe_result(result)
                return result

        try:
            definition = self.registry.get(tool_name)
            profile_error = self._agent_profile_requirement_error(definition)
            if profile_error is not None:
                return self._execution_error(call, profile_error, profile_error, span_started_at, metadata, status="denied")
            sandbox_error = self._sandbox_requirement_error(definition, call.environment)
            if sandbox_error is not None:
                return self._execution_error(call, sandbox_error, sandbox_error, span_started_at, metadata, status="denied")
            if not self._audit("ToolExecutionStarted", call, {}):
                result = self._audit_write_failed_result(call)
                self._observe_result(result)
                return result
            if definition.executor_kind == "sandboxed_subprocess":
                if not self._audit(
                    "SandboxEnforced",
                    call,
                    {
                        "isolation_level": "strong",
                        "backend": self.sandbox_executor.backend_name,
                        "available": self.sandbox_executor.available,
                    },
                    environment=environment,
                ):
                    result = self._audit_write_failed_result(call)
                    self._observe_result(result)
                    return result
                sandbox_span_id = f"span_{uuid4().hex}"
                sandbox_started_at = perf_counter()
                sandbox_payload = {
                    "span_kind": "sandbox_execution",
                    "parent_span_id": call.span_id,
                    "isolation_level": "strong",
                    "backend": self.sandbox_executor.backend_name,
                    "available": self.sandbox_executor.available,
                    **metadata,
                }
                if self._tracing_enabled():
                    if not self._audit_trace_span_for_call(
                        "TraceSpanStarted",
                        call,
                        sandbox_span_id,
                        {"started_at": utc_now(), "status": "started", **sandbox_payload},
                        environment=environment,
                    ):
                        result = self._audit_write_failed_result(call)
                        self._observe_result(result)
                        return result
                output = self._execute_sandboxed_command_tool(tool_name)
                if self._tracing_enabled():
                    if not self._audit_trace_span_for_call(
                        "TraceSpanFinished",
                        call,
                        sandbox_span_id,
                        {
                            "finished_at": utc_now(),
                            "duration_ms": int((perf_counter() - sandbox_started_at) * 1000),
                            "status": "success",
                            **sandbox_payload,
                        },
                        environment=environment,
                    ):
                        result = self._audit_write_failed_result(call)
                        self._observe_result(result)
                        return result
            elif definition.executor_kind == "subprocess":
                output = self._execute_command_tool(tool_name)
            else:
                output = self.executor.execute(self.registry.callable_for(tool_name), input)
        except subprocess.TimeoutExpired as error:
            return self._execution_error(call, "executor.timeout", str(error), span_started_at, metadata)
        except SandboxViolationError as error:
            return self._execution_error(
                call,
                _sandbox_violation_code(error),
                str(error),
                span_started_at,
                metadata,
                status="denied",
            )
        except SandboxUnavailableError as error:
            return self._execution_error(call, "sandbox.unavailable", str(error), span_started_at, metadata)
        except Exception as error:
            return self._execution_error(call, "tool.error", str(error), span_started_at, metadata)
        filtered_output = self._redact(output)
        result = ToolResult(tool_call_id=call.tool_call_id, output=filtered_output, status="success", run_id=call.run_id)
        if not self._audit("ToolExecutionFinished", call, {"status": result.status, "output": result.output}):
            result = self._audit_write_failed_after_execution_result(call, filtered_output)
            self._observe_result(result)
            return result
        if self._tracing_enabled():
            if not self._audit(
                "TraceSpanFinished",
                call,
                {
                    "span_kind": "tool_call",
                    "finished_at": utc_now(),
                    "duration_ms": int((perf_counter() - span_started_at) * 1000),
                    "status": result.status,
                    "decision": decision.decision,
                    "reason": decision.reason,
                    "audit_status": "committed",
                    **metadata,
                },
                environment=environment,
            ):
                result = self._audit_write_failed_after_execution_result(call, filtered_output)
                self._observe_result(result)
                return result
        self._observe_result(result)
        return result

    def _audit_write_failed_result(self, call: ToolCall) -> ToolResult:
        return ToolResult(
            tool_call_id=call.tool_call_id,
            status="denied",
            error="audit.write_failed",
            run_id=call.run_id,
        )

    def _audit_write_failed_after_execution_result(self, call: ToolCall, output: Any) -> ToolResult:
        return ToolResult(
            tool_call_id=call.tool_call_id,
            output=output,
            status="error",
            error="audit.write_failed_after_execution",
            run_id=call.run_id,
        )

    def _execution_error(
        self,
        call: ToolCall,
        error_code: str,
        message: str,
        span_started_at: float,
        metadata: dict[str, str],
        status: str = "error",
    ) -> ToolResult:
        result = ToolResult(tool_call_id=call.tool_call_id, status=status, error=error_code, run_id=call.run_id)
        self._audit("RuntimeError", call, {"error": error_code, "message": message})
        if self._tracing_enabled():
            self._audit(
                "TraceSpanFinished",
                call,
                {
                    "span_kind": "tool_call",
                    "finished_at": utc_now(),
                    "duration_ms": int((perf_counter() - span_started_at) * 1000),
                    "status": result.status,
                    "error": error_code,
                    "audit_status": "committed",
                    **metadata,
                },
                environment=call.environment,
            )
        self._observe_result(result)
        return result

    def _finish_tool_trace_span(
        self,
        call: ToolCall,
        span_started_at: float,
        metadata: dict[str, Any],
        status: str,
        decision: str | None = None,
        reason: str | None = None,
        error: str | None = None,
    ) -> bool:
        if not self._tracing_enabled():
            return True
        payload: dict[str, Any] = {
            "span_kind": "tool_call",
            "finished_at": utc_now(),
            "duration_ms": int((perf_counter() - span_started_at) * 1000),
            "status": status,
            "audit_status": "committed",
            **metadata,
        }
        if decision is not None:
            payload["decision"] = decision
        if reason is not None:
            payload["reason"] = reason
        if error is not None:
            payload["error"] = error
        return self._audit("TraceSpanFinished", call, payload, environment=call.environment)

    def _finish_policy_trace_span(
        self,
        call: ToolCall,
        policy_span_id: str,
        policy_started_at: float,
        decision: Any,
        metadata: dict[str, Any],
        status: str | None = None,
        error: str | None = None,
    ) -> bool:
        decision_value = "deny" if error is not None else decision.decision
        payload: dict[str, Any] = {
            "span_kind": "policy_evaluation",
            "parent_span_id": call.span_id,
            "finished_at": utc_now(),
            "duration_ms": int((perf_counter() - policy_started_at) * 1000),
            "status": status or decision.decision,
            "decision": decision_value,
            "reason": error or decision.reason,
            "rule_id": decision.rule_id,
            "capability": decision.capability,
            "environment": decision.environment,
            "policy_version": self.config.get("version", 1),
            **metadata,
        }
        if error is not None:
            payload["error"] = error
        return self._audit_trace_span_for_call(
            "TraceSpanFinished",
            call,
            policy_span_id,
            payload,
            environment=call.environment,
        )

    def _audit(
        self,
        event_type: str,
        call: ToolCall,
        payload: dict[str, Any],
        environment: str | None = None,
    ) -> bool:
        try:
            self.audit_sink.write(
                AuditEvent(
                    event_type=event_type,
                    run_id=call.run_id,
                    tool_call_id=call.tool_call_id,
                    trace_id=call.trace_id,
                    span_id=call.span_id,
                    tool_name=call.tool_name,
                    payload=payload,
                )
            )
            self._audit_event_types.append(event_type)
            return True
        except Exception:
            fail_closed = self._audit_failure_strategy(environment or call.environment) == "fail_closed"
            self._observe_audit_failure(fail_closed)
            return not fail_closed

    def _audit_trace_span_for_call(
        self,
        event_type: str,
        call: ToolCall,
        span_id: str,
        payload: dict[str, Any],
        environment: str | None = None,
    ) -> bool:
        try:
            self.audit_sink.write(
                AuditEvent(
                    event_type=event_type,
                    run_id=call.run_id,
                    tool_call_id=call.tool_call_id,
                    trace_id=call.trace_id,
                    span_id=span_id,
                    tool_name=call.tool_name,
                    payload=payload,
                )
            )
            self._audit_event_types.append(event_type)
            return True
        except Exception:
            fail_closed = self._audit_failure_strategy(environment or call.environment) == "fail_closed"
            self._observe_audit_failure(fail_closed)
            return not fail_closed

    def _audit_agent_event(
        self,
        event_type: str,
        agent_id: str,
        payload: dict[str, Any],
        environment: str | None = None,
    ) -> bool:
        try:
            self.audit_sink.write(
                AuditEvent(
                    event_type=event_type,
                    run_id=f"agent_{agent_id}",
                    payload=self._redact({"agent_id": agent_id, **payload}),
                )
            )
            self._audit_event_types.append(event_type)
            return True
        except Exception:
            fail_closed = self._audit_failure_strategy(environment or str(payload.get("environment", "prod"))) == "fail_closed"
            self._observe_audit_failure(fail_closed=fail_closed)
            return not fail_closed

    def _audit_agent_trace_span(
        self,
        event_type: str,
        agent_id: str,
        trace_id: str,
        span_id: str,
        payload: dict[str, Any],
        environment: str | None = None,
    ) -> bool:
        try:
            self.audit_sink.write(
                AuditEvent(
                    event_type=event_type,
                    run_id=f"agent_{agent_id}",
                    trace_id=trace_id,
                    span_id=span_id,
                    payload=self._redact({"agent_id": agent_id, **payload}),
                )
            )
            self._audit_event_types.append(event_type)
            return True
        except Exception:
            fail_closed = self._audit_failure_strategy(environment or str(payload.get("environment", "prod"))) == "fail_closed"
            self._observe_audit_failure(fail_closed=fail_closed)
            return not fail_closed

    def _audit_event_types_since_last_read(self) -> list[str]:
        return self._audit_event_types[self._audit_event_cursor :]

    def _audit_event_types_since(self, cursor: int) -> list[str]:
        return self._audit_event_types[cursor:]

    def _audit_failure_strategy(self, environment: str) -> str:
        return (
            self.config.get("audit", {})
            .get("on_write_failure", {})
            .get(environment, "warn" if environment == "dev" else "fail_closed")
        )

    def _tracing_enabled(self) -> bool:
        return bool(self.config.get("tracing", {}).get("enabled", False))

    def _redact(self, value: Any) -> Any:
        return redact_secrets(value, self.config.get("redaction", {}).get("sensitive_fields", []))

    def _observe_result(self, result: ToolResult) -> None:
        if self.observer is not None:
            self.observer.record_tool_result(result.status, result.error)

    def _observe_approval_requested(self) -> None:
        if self.observer is not None:
            self.observer.record_approval_requested()

    def _observe_audit_failure(self, fail_closed: bool) -> None:
        if self.observer is not None:
            self.observer.record_audit_failure(fail_closed)

    def _execute_command_tool(self, tool_name: str) -> dict[str, Any]:
        command = self.registry.get(tool_name).metadata["command"]
        result = self.subprocess_executor.execute(
            argv=command["argv"],
            cwd=command["cwd"],
            env=command["env"],
            env_allowlist=command["env_allowlist"],
            timeout_ms=command["timeout_ms"],
            stdout_limit_bytes=command["stdout_limit_bytes"],
            stderr_limit_bytes=command["stderr_limit_bytes"],
        )
        return {"exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr}

    def _execute_sandboxed_command_tool(self, tool_name: str) -> dict[str, Any]:
        command = self.registry.get(tool_name).metadata["command"]
        result = self.sandbox_executor.execute(
            SandboxCommandSpec(
                argv=command["argv"],
                cwd=command["cwd"],
                env=self._filtered_env(command["env"], command["env_allowlist"]),
                env_allowlist=command["env_allowlist"],
                timeout_ms=command["timeout_ms"],
                stdout_limit_bytes=command["stdout_limit_bytes"],
                stderr_limit_bytes=command["stderr_limit_bytes"],
                isolation_level=command["isolation_level"],
                network_access=command["network_access"],
                read_paths=command["read_paths"],
                write_paths=command["write_paths"],
            )
        )
        return {"exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr}

    def _filtered_env(self, env: dict[str, str], env_allowlist: list[str]) -> dict[str, str]:
        return {key: env[key] for key in env_allowlist if key in env}

    def _sandbox_requirement_error(self, definition: Any, environment: str) -> str | None:
        if environment == "prod" and definition.executor_kind == "subprocess" and definition.risk_level == "high":
            return "sandbox.required"
        return None

    def _agent_profile_requirement_error(self, definition: Any) -> str | None:
        if self._agent_trace_context is None:
            return None
        declared_capabilities = set(self._agent_trace_context.get("capabilities") or [])
        if declared_capabilities:
            missing_capabilities = [
                capability for capability in definition.capabilities_required if capability not in declared_capabilities
            ]
            if missing_capabilities:
                return "agent.capability_denied"

        runtime_profile = self._agent_trace_context.get("runtime_profile") or {}
        if (
            runtime_profile.get("sandbox_required")
            and _requires_strong_guard(definition)
            and definition.executor_kind == "subprocess"
        ):
            return "agent.sandbox_required"
        return None

    def _agent_max_tool_calls_error(self) -> str | None:
        if self._agent_trace_context is None:
            return None
        runtime_profile = self._agent_trace_context.get("runtime_profile") or {}
        max_tool_calls = runtime_profile.get("max_tool_calls")
        if max_tool_calls is None:
            return None
        tool_call_count = int(self._agent_trace_context.get("tool_call_count", 0))
        if tool_call_count >= int(max_tool_calls):
            return "agent.max_tool_calls_exceeded"
        self._agent_trace_context["tool_call_count"] = tool_call_count + 1
        return None

    def _agent_approval_requirement_error(self, decision: Any, definition: Any) -> str | None:
        if self._agent_trace_context is None:
            return None
        runtime_profile = self._agent_trace_context.get("runtime_profile") or {}
        if runtime_profile.get("approval_required") and _requires_strong_guard(definition) and decision.decision == "allow":
            return "agent.approval_required"
        return None


def _sandbox_violation_code(error: SandboxViolationError) -> str:
    return str(error).split(":", 1)[0] or "sandbox.violation"


def _requires_strong_guard(definition: Any) -> bool:
    return definition.risk_level in {"high", "critical"}
