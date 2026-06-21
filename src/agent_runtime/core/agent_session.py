from __future__ import annotations

from dataclasses import fields, is_dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from agent_runtime.core.models import AgentMetadata, AgentRunRequest, AgentRunResult, utc_now

if TYPE_CHECKING:
    from agent_runtime.core.runtime import AgentRuntime


class RegisteredAgent:
    def __init__(
        self,
        runtime: "AgentRuntime",
        agent_id: str,
        agent: Any,
        actor: dict[str, Any],
        environment: str,
        metadata: AgentMetadata,
        registration_audit_ok: bool = True,
        registration_audit_events: list[str] | None = None,
    ) -> None:
        self.runtime = runtime
        self.agent_id = agent_id
        self.agent = agent
        self.actor = actor
        self.environment = environment
        self.metadata = metadata
        self.registration_audit_ok = registration_audit_ok
        self.registration_audit_events = list(registration_audit_events or [])

    def run(self, prompt: str) -> Any:
        if not self.registration_audit_ok:
            raise RuntimeError("audit.write_failed")
        trace_id = f"trace_{uuid4().hex}"
        span_id = f"span_{uuid4().hex}"
        span_started_at = perf_counter()
        token = self.runtime._set_agent_trace_context(
            {
                "agent_id": self.agent_id,
                "trace_id": trace_id,
                "agent_span_id": span_id,
                "capabilities": list(self.metadata.capabilities),
                "runtime_profile": self.metadata.runtime_profile.to_dict(),
                "tool_call_count": 0,
                "audit_event_types": list(self.registration_audit_events),
            }
        )
        try:
            if not self.runtime._audit_agent_event(
                "AgentRunStarted",
                self.agent_id,
                {"actor": self.actor, "environment": self.environment, "metadata": self.metadata.to_dict()},
                environment=self.environment,
            ):
                raise RuntimeError("audit.write_failed")
            if self.runtime._tracing_enabled():
                if not self.runtime._audit_agent_trace_span(
                    "TraceSpanStarted",
                    self.agent_id,
                    trace_id,
                    span_id,
                    {
                        "span_kind": "agent_run",
                        "started_at": utc_now(),
                        "status": "started",
                        "metadata": self.metadata.to_dict(),
                    },
                    environment=self.environment,
                ):
                    raise RuntimeError("audit.write_failed")
            self.agent.runtime = self.runtime
            self.agent.actor = self.actor
            self.agent.environment = self.environment
            transcript = self.agent.run(prompt)
            object.__setattr__(transcript, "registration", "registered")
            object.__setattr__(transcript, "agent_id", self.agent_id)
            object.__setattr__(transcript, "agent_metadata", self.metadata.to_dict())
            object.__setattr__(transcript, "trace_id", trace_id)
            object.__setattr__(transcript, "agent_span_id", span_id)
            if not self.runtime._audit_agent_event(
                "AgentRunFinished",
                self.agent_id,
                {"status": transcript.status, "tool_count": len(transcript.tool_results)},
                environment=self.environment,
            ):
                raise RuntimeError("audit.write_failed_after_execution")
            if self.runtime._tracing_enabled():
                if not self.runtime._audit_agent_trace_span(
                    "TraceSpanFinished",
                    self.agent_id,
                    trace_id,
                    span_id,
                    {
                        "span_kind": "agent_run",
                        "finished_at": utc_now(),
                        "duration_ms": int((perf_counter() - span_started_at) * 1000),
                        "status": transcript.status,
                        "metadata": self.metadata.to_dict(),
                    },
                    environment=self.environment,
                ):
                    raise RuntimeError("audit.write_failed_after_execution")
            object.__setattr__(transcript, "audit_events", self.runtime._current_agent_audit_events())
            return transcript
        except Exception as error:
            if str(error) in {"audit.write_failed", "audit.write_failed_after_execution"}:
                raise
            error_type = error.__class__.__name__
            self.runtime._audit_agent_event(
                "AgentRunFinished",
                self.agent_id,
                {"status": "failed", "error": error_type, "tool_count": 0},
                environment=self.environment,
            )
            if self.runtime._tracing_enabled():
                self.runtime._audit_agent_trace_span(
                    "TraceSpanFinished",
                    self.agent_id,
                    trace_id,
                    span_id,
                    {
                        "span_kind": "agent_run",
                        "finished_at": utc_now(),
                        "duration_ms": int((perf_counter() - span_started_at) * 1000),
                        "status": "failed",
                        "error": error_type,
                        "metadata": self.metadata.to_dict(),
                    },
                    environment=self.environment,
                )
            raise
        finally:
            self.runtime._reset_agent_trace_context(token)

    def run_session(self, prompt: str | AgentRunRequest) -> AgentRunResult:
        request = prompt if isinstance(prompt, AgentRunRequest) else AgentRunRequest(prompt=prompt)
        audit_cursor = self.runtime._audit_event_cursor
        trace_id = f"trace_{uuid4().hex}"
        span_id = f"span_{uuid4().hex}"
        if not self.registration_audit_ok:
            return self._audit_write_failed_result(request, trace_id, span_id, audit_cursor)
        span_started_at = perf_counter()
        token = self.runtime._set_agent_trace_context(
            {
                "agent_id": self.agent_id,
                "trace_id": trace_id,
                "agent_span_id": span_id,
                "capabilities": list(self.metadata.capabilities),
                "runtime_profile": self.metadata.runtime_profile.to_dict(),
                "tool_call_count": 0,
                "audit_event_types": list(self.registration_audit_events),
            }
        )
        try:
            if not self.runtime._audit_agent_event(
                "AgentRunStarted",
                self.agent_id,
                {
                    "actor": self.actor,
                    "environment": self.environment,
                    "metadata": self.metadata.to_dict(),
                    "context": request.context,
                },
                environment=self.environment,
            ):
                return self._audit_write_failed_result(request, trace_id, span_id, audit_cursor)
            if self.runtime._tracing_enabled():
                if not self.runtime._audit_agent_trace_span(
                    "TraceSpanStarted",
                    self.agent_id,
                    trace_id,
                    span_id,
                    {
                        "span_kind": "agent_run",
                        "started_at": utc_now(),
                        "status": "started",
                        "metadata": self.metadata.to_dict(),
                        "context": request.context,
                    },
                    environment=self.environment,
                ):
                    return self._audit_write_failed_result(request, trace_id, span_id, audit_cursor)
            self.agent.runtime = self.runtime
            self.agent.actor = self.actor
            self.agent.environment = self.environment
            try:
                output = self.agent.run(request.prompt)
            except Exception as error:
                error_type = error.__class__.__name__
                self.runtime._audit_agent_event(
                    "AgentRunFinished",
                    self.agent_id,
                    {"status": "failed", "error": error_type, "tool_count": 0},
                    environment=self.environment,
                )
                if self.runtime._tracing_enabled():
                    self.runtime._audit_agent_trace_span(
                        "TraceSpanFinished",
                        self.agent_id,
                        trace_id,
                        span_id,
                        {
                            "span_kind": "agent_run",
                            "finished_at": utc_now(),
                            "duration_ms": int((perf_counter() - span_started_at) * 1000),
                            "status": "failed",
                            "error": error_type,
                            "metadata": self.metadata.to_dict(),
                        },
                        environment=self.environment,
                    )
                result = AgentRunResult(
                    agent_id=self.agent_id,
                    status="failed",
                    request=request,
                    trace_id=trace_id,
                    agent_span_id=span_id,
                    agent_metadata=self.metadata.to_dict(),
                    audit_events=self.runtime._current_agent_audit_events(),
                    error=error_type,
                )
                self.runtime._audit_event_cursor = len(self.runtime._audit_event_types)
                return result

            status = str(getattr(output, "status", "completed"))
            tool_results = list(getattr(output, "tool_results", []))
            public_output = self.runtime._redact(_agent_output_to_public_value(output))
            if not self.runtime._audit_agent_event(
                "AgentRunFinished",
                self.agent_id,
                {"status": status, "tool_count": len(tool_results)},
                environment=self.environment,
            ):
                return self._audit_write_failed_result(
                    request,
                    trace_id,
                    span_id,
                    audit_cursor,
                    status="error",
                    error="audit.write_failed_after_execution",
                    output=public_output,
                    tool_results=tool_results,
                )
            if self.runtime._tracing_enabled():
                if not self.runtime._audit_agent_trace_span(
                    "TraceSpanFinished",
                    self.agent_id,
                    trace_id,
                    span_id,
                    {
                        "span_kind": "agent_run",
                        "finished_at": utc_now(),
                        "duration_ms": int((perf_counter() - span_started_at) * 1000),
                        "status": status,
                        "metadata": self.metadata.to_dict(),
                    },
                    environment=self.environment,
                ):
                    return self._audit_write_failed_result(
                        request,
                        trace_id,
                        span_id,
                        audit_cursor,
                        status="error",
                        error="audit.write_failed_after_execution",
                        output=public_output,
                        tool_results=tool_results,
                    )
            result = AgentRunResult(
                agent_id=self.agent_id,
                status=status,
                request=request,
                output=public_output,
                trace_id=trace_id,
                agent_span_id=span_id,
                agent_metadata=self.metadata.to_dict(),
                tool_results=tool_results,
                audit_events=self.runtime._current_agent_audit_events(),
            )
            self.runtime._audit_event_cursor = len(self.runtime._audit_event_types)
            return result
        finally:
            self.runtime._reset_agent_trace_context(token)

    def _audit_write_failed_result(
        self,
        request: AgentRunRequest,
        trace_id: str,
        span_id: str,
        audit_cursor: int,
        status: str = "failed",
        error: str = "audit.write_failed",
        output: Any = None,
        tool_results: list[Any] | None = None,
    ) -> AgentRunResult:
        result = AgentRunResult(
            agent_id=self.agent_id,
            status=status,
            request=request,
            output=output,
            trace_id=trace_id,
            agent_span_id=span_id,
            agent_metadata=self.metadata.to_dict(),
            tool_results=tool_results or [],
            audit_events=self.runtime._audit_event_types_since(audit_cursor),
            error=error,
        )
        self.runtime._audit_event_cursor = len(self.runtime._audit_event_types)
        return result



def _agent_output_to_public_value(output: Any) -> Any:
    if not isinstance(output, type) and is_dataclass(output):
        return {field.name: _agent_output_to_public_value(getattr(output, field.name)) for field in fields(output)}
    if isinstance(output, dict):
        return {key: _agent_output_to_public_value(value) for key, value in output.items()}
    if isinstance(output, list):
        return [_agent_output_to_public_value(item) for item in output]
    if hasattr(output, "to_dict") and callable(output.to_dict):
        return _agent_output_to_public_value(output.to_dict())
    if isinstance(output, (str, int, float, bool)) or output is None:
        return output
    return repr(output)
