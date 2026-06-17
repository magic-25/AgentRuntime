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
from agent_runtime.core.models import AgentMetadata, ApprovalRequest, AuditEvent, RuntimeProfile, ToolCall, ToolResult, utc_now
from agent_runtime.core.registry import ToolRegistry
from agent_runtime.execution.in_process import InProcessExecutor
from agent_runtime.execution.sandbox import SandboxCommandSpec, SandboxExecutor, SandboxUnavailableError, UnavailableSandboxExecutor
from agent_runtime.execution.subprocess import SubprocessExecutor
from agent_runtime.guard.redaction import redact_secrets
from agent_runtime.policy.engine import PolicyEngine


class RegisteredAgent:
    def __init__(
        self,
        runtime: "AgentRuntime",
        agent_id: str,
        agent: Any,
        actor: dict[str, Any],
        environment: str,
        metadata: AgentMetadata,
        direct_tools: dict[str, Any] | None = None,
    ) -> None:
        self.runtime = runtime
        self.agent_id = agent_id
        self.agent = agent
        self.actor = actor
        self.environment = environment
        self.metadata = metadata
        self.direct_tools = direct_tools or {}

    def run(self, prompt: str) -> Any:
        self.runtime._audit_agent_event(
            "AgentRunStarted",
            self.agent_id,
            {"actor": self.actor, "environment": self.environment, "metadata": self.metadata.to_dict()},
        )
        self.agent.runtime = self.runtime
        self.agent.actor = self.actor
        self.agent.environment = self.environment
        transcript = self.agent.run(prompt)
        object.__setattr__(transcript, "registration", "registered")
        object.__setattr__(transcript, "agent_id", self.agent_id)
        object.__setattr__(transcript, "agent_metadata", self.metadata.to_dict())
        self.runtime._audit_agent_event(
            "AgentRunFinished",
            self.agent_id,
            {"status": transcript.status, "tool_count": len(transcript.tool_results)},
        )
        object.__setattr__(transcript, "audit_events", self.runtime._audit_event_types_since_last_read())
        return transcript


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
        self.approval_provider = approval_provider or StaticApprovalProvider(approved=True)
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
        direct_tools: dict[str, Any] | None = None,
    ) -> RegisteredAgent:
        normalized = self._normalize_agent_metadata(agent_id, metadata, environment)
        self._audit_event_cursor = len(self._audit_event_types)
        self._audit_agent_event(
            "AgentRegistered",
            agent_id,
            {"actor": actor, "environment": environment, "metadata": normalized.to_dict()},
        )
        return RegisteredAgent(self, agent_id, agent, actor, environment, normalized, direct_tools=direct_tools)

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
        )
        metadata = {"adapter_source": adapter_source} if adapter_source else {}
        if not self._audit("ToolCallRequested", call, {"input": call.input, **metadata}, environment=environment):
            result = ToolResult(
                tool_call_id=call.tool_call_id,
                status="denied",
                error="audit.write_failed",
                run_id=call.run_id,
            )
            self._observe_result(result)
            return result

        engine = PolicyEngine(self.config, self.registry)
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

        if decision.decision == "deny":
            result = ToolResult(tool_call_id=call.tool_call_id, status="denied", error=decision.reason, run_id=call.run_id)
            if not self._audit("RuntimeError", call, {"error": decision.reason}):
                result = self._audit_write_failed_result(call)
            self._observe_result(result)
            return result

        if decision.decision == "require_approval":
            self._observe_approval_requested()
            if not self._audit("ApprovalRequested", call, {"rule_id": decision.rule_id}):
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
                    risk_level=self.registry.get(tool_name).risk_level,
                )
            )
            approval_reason = "approval.timeout" if approval.timed_out else approval.reason
            if not self._audit("ApprovalResolved", call, {"approved": approval.approved, "reason": approval_reason}):
                result = self._audit_write_failed_result(call)
                self._observe_result(result)
                return result
            if not approval.approved:
                error = "approval.timeout" if approval.timed_out else "approval_rejected"
                result = ToolResult(
                    tool_call_id=call.tool_call_id,
                    status="rejected",
                    error=error,
                    run_id=call.run_id,
                )
                self._observe_result(result)
                return result

        span_started_at = perf_counter()
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

        if not self._audit("ToolExecutionStarted", call, {}):
            result = self._audit_write_failed_result(call)
            self._observe_result(result)
            return result
        try:
            definition = self.registry.get(tool_name)
            sandbox_error = self._sandbox_requirement_error(definition, call.environment)
            if sandbox_error is not None:
                return self._execution_error(call, sandbox_error, sandbox_error, span_started_at, metadata, status="denied")
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
                output = self._execute_sandboxed_command_tool(tool_name)
            elif definition.executor_kind == "subprocess":
                output = self._execute_command_tool(tool_name)
            else:
                output = self.executor.execute(self.registry.callable_for(tool_name), input)
        except subprocess.TimeoutExpired as error:
            return self._execution_error(call, "executor.timeout", str(error), span_started_at, metadata)
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
                    **metadata,
                },
                environment=call.environment,
            )
        self._observe_result(result)
        return result

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

    def _audit_agent_event(self, event_type: str, agent_id: str, payload: dict[str, Any]) -> bool:
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
            self._observe_audit_failure(fail_closed=False)
            return True

    def _audit_event_types_since_last_read(self) -> list[str]:
        return self._audit_event_types[self._audit_event_cursor :]

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
                env=command["env"],
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

    def _sandbox_requirement_error(self, definition: Any, environment: str) -> str | None:
        if environment == "prod" and definition.executor_kind == "subprocess" and definition.risk_level == "high":
            return "sandbox.required"
        return None
