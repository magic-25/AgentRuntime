from __future__ import annotations

from dataclasses import dataclass, field

from agent_runtime import AgentRunRequest, AgentRunResult
from agent_runtime.core.models import AgentMetadata, RuntimeProfile, ToolResult
from agent_runtime.core.runtime import AgentRuntime


def _runtime(tmp_path, allow_echo: bool = True) -> AgentRuntime:
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(tmp_path / "agent-session-audit.jsonl")},
            "tracing": {"enabled": True},
            "redaction": {"sensitive_fields": ["api_key"]},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}]
            if allow_echo
            else [],
        }
    )

    @runtime.tool(name="echo")
    def echo(message: str, api_key: str | None = None) -> dict[str, str | None]:
        return {"message": message, "api_key": api_key}

    return runtime


def _metadata() -> AgentMetadata:
    return AgentMetadata(
        agent_id="dict-agent",
        name="Dictionary Agent",
        provider="local",
        framework="plain-python",
        capabilities=["tool.invoke:echo"],
        runtime_profile=RuntimeProfile(environment="dev", execution_mode="runtime_tools", max_tool_calls=1),
    )


class DictAgent:
    def run(self, prompt: str) -> dict[str, object]:
        return {
            "answer": f"handled: {prompt}",
            "actor": self.actor["id"],
            "environment": self.environment,
            "api_key": "secret-value",
        }


@dataclass(frozen=True)
class ToolTranscript:
    status: str
    output: dict[str, object]
    tool_results: list[ToolResult] = field(default_factory=list)


class ToolCallingAgent:
    def run(self, prompt: str) -> ToolTranscript:
        result = self.runtime.call_tool(
            "echo",
            {"message": prompt, "api_key": "secret-value"},
            actor=self.actor,
            environment=self.environment,
        )
        return ToolTranscript(status="completed", output={"tool_status": result.status}, tool_results=[result])


class FailingAgent:
    def run(self, prompt: str) -> dict[str, str]:
        raise RuntimeError(f"cannot handle {prompt}")


def test_agent_run_session_wraps_arbitrary_python_output(tmp_path):
    runtime = _runtime(tmp_path)
    registered = runtime.register_agent(
        "dict-agent",
        DictAgent(),
        actor={"id": "alice"},
        environment="dev",
        metadata=_metadata(),
    )

    result = registered.run_session("hello")

    assert isinstance(result, AgentRunResult)
    assert result.agent_id == "dict-agent"
    assert result.registration == "registered"
    assert result.status == "completed"
    assert result.output == {
        "answer": "handled: hello",
        "actor": "alice",
        "environment": "dev",
        "api_key": "[REDACTED]",
    }
    assert result.agent_metadata["framework"] == "plain-python"
    assert result.trace_id.startswith("trace_")
    assert result.agent_span_id.startswith("span_")
    assert result.tool_results == []
    assert result.error is None
    assert result.audit_events == [
        "AgentRegistered",
        "AgentRunStarted",
        "TraceSpanStarted",
        "AgentRunFinished",
        "TraceSpanFinished",
    ]
    assert result.to_dict()["output"]["api_key"] == "[REDACTED]"


def test_agent_run_session_preserves_runtime_tool_results(tmp_path):
    runtime = _runtime(tmp_path)
    registered = runtime.register_agent(
        "tool-agent",
        ToolCallingAgent(),
        actor={"id": "alice"},
        environment="dev",
        metadata={**_metadata().to_dict(), "agent_id": "tool-agent", "name": "Tool Agent"},
    )

    result = registered.run_session(AgentRunRequest(prompt="echo me", context={"ticket": "INC-1"}))

    assert result.agent_id == "tool-agent"
    assert result.status == "completed"
    assert result.output["output"] == {"tool_status": "success"}
    assert len(result.tool_results) == 1
    assert result.tool_results[0].status == "success"
    assert result.tool_results[0].output == {"message": "echo me", "api_key": "[REDACTED]"}
    assert result.request.context == {"ticket": "INC-1"}
    assert "ToolCallRequested" in result.audit_events
    assert "PolicyEvaluated" in result.audit_events
    assert "ToolExecutionFinished" in result.audit_events


def test_agent_run_session_returns_failed_result_without_breaking_legacy_run(tmp_path):
    runtime = _runtime(tmp_path)
    registered = runtime.register_agent(
        "failing-agent",
        FailingAgent(),
        actor={"id": "alice"},
        environment="dev",
        metadata={**_metadata().to_dict(), "agent_id": "failing-agent", "name": "Failing Agent"},
    )

    result = registered.run_session("boom")

    assert result.status == "failed"
    assert result.output is None
    assert result.error == "RuntimeError"
    assert "AgentRunFinished" in result.audit_events
    assert "TraceSpanFinished" in result.audit_events

    legacy = runtime.register_agent(
        "legacy-failing-agent",
        FailingAgent(),
        actor={"id": "alice"},
        environment="dev",
        metadata={**_metadata().to_dict(), "agent_id": "legacy-failing-agent", "name": "Legacy Failing Agent"},
    )
    try:
        legacy.run("boom")
    except RuntimeError as error:
        assert str(error) == "cannot handle boom"
    else:
        raise AssertionError("legacy run should re-raise agent exceptions")


def test_runtime_run_agent_registers_and_returns_session_result(tmp_path):
    runtime = _runtime(tmp_path)

    result = runtime.run_agent(
        "dict-agent",
        DictAgent(),
        prompt="from runtime",
        actor={"id": "alice"},
        environment="dev",
        metadata=_metadata(),
    )

    assert isinstance(result, AgentRunResult)
    assert result.status == "completed"
    assert result.output["answer"] == "handled: from runtime"
