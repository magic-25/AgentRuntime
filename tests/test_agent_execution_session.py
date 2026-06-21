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


class FailingAuditSink:
    def write(self, event):
        raise OSError("audit sink unavailable")


@dataclass(frozen=True)
class MultiToolTranscript:
    status: str
    tool_results: list[ToolResult] = field(default_factory=list)


class MultiToolAgent:
    def __init__(self, tool_names: list[str]) -> None:
        self.tool_names = tool_names

    def run(self, prompt: str) -> MultiToolTranscript:
        results = [
            self.runtime.call_tool(tool_name, {}, actor=self.actor, environment=self.environment)
            for tool_name in self.tool_names
        ]
        return MultiToolTranscript(status="completed", tool_results=results)


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


def test_agent_run_session_fails_closed_when_lifecycle_audit_write_fails(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.config["audit"]["on_write_failure"] = {"dev": "fail_closed"}
    runtime.audit_sink = FailingAuditSink()

    result = runtime.run_agent(
        "dict-agent",
        DictAgent(),
        prompt="from runtime",
        actor={"id": "alice"},
        environment="dev",
        metadata=_metadata(),
    )

    assert result.status == "failed"
    assert result.error == "audit.write_failed"
    assert result.audit_events == []


def test_registered_agent_declared_capabilities_are_enforced(tmp_path):
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(tmp_path / "capability-audit.jsonl")},
            "rules": [
                {"id": "allow-tools", "environment": "dev", "effect": "allow", "capabilities": ["tool.invoke:*"]},
            ],
        }
    )
    calls = []

    @runtime.tool(name="delete_record")
    def delete_record() -> str:
        calls.append("delete_record")
        return "deleted"

    result = runtime.run_agent(
        "limited-agent",
        MultiToolAgent(["delete_record"]),
        prompt="try delete",
        actor={"id": "alice"},
        environment="dev",
        metadata=AgentMetadata(
            agent_id="limited-agent",
            name="Limited Agent",
            provider="local",
            framework="plain-python",
            capabilities=["tool.invoke:echo"],
            runtime_profile=RuntimeProfile(environment="dev", max_tool_calls=1),
        ),
    )

    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].error == "agent.capability_denied"
    assert calls == []


def test_registered_agent_max_tool_calls_is_enforced(tmp_path):
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(tmp_path / "max-tool-calls-audit.jsonl")},
            "rules": [
                {"id": "allow-tools", "environment": "dev", "effect": "allow", "capabilities": ["tool.invoke:*"]},
            ],
        }
    )
    calls = []

    @runtime.tool(name="first")
    def first() -> str:
        calls.append("first")
        return "first"

    @runtime.tool(name="second")
    def second() -> str:
        calls.append("second")
        return "second"

    result = runtime.run_agent(
        "one-call-agent",
        MultiToolAgent(["first", "second"]),
        prompt="call twice",
        actor={"id": "alice"},
        environment="dev",
        metadata=AgentMetadata(
            agent_id="one-call-agent",
            name="One Call Agent",
            provider="local",
            framework="plain-python",
            capabilities=["tool.invoke:first", "tool.invoke:second"],
            runtime_profile=RuntimeProfile(environment="dev", max_tool_calls=1),
        ),
    )

    assert [tool.status for tool in result.tool_results] == ["success", "denied"]
    assert result.tool_results[1].error == "agent.max_tool_calls_exceeded"
    assert calls == ["first"]


def test_registered_agent_max_tool_calls_counts_denied_attempts(tmp_path):
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(tmp_path / "max-tool-calls-denied-audit.jsonl")},
            "rules": [{"id": "allow-tools", "environment": "dev", "effect": "allow", "capabilities": ["tool.invoke:*"]}],
        }
    )
    calls = []

    @runtime.tool(name="first")
    def first() -> str:
        calls.append("first")
        return "first"

    result = runtime.run_agent(
        "one-attempt-agent",
        MultiToolAgent(["missing", "first"]),
        prompt="call twice",
        actor={"id": "alice"},
        environment="dev",
        metadata=AgentMetadata(
            agent_id="one-attempt-agent",
            name="One Attempt Agent",
            provider="local",
            framework="plain-python",
            capabilities=["tool.invoke:first"],
            runtime_profile=RuntimeProfile(environment="dev", max_tool_calls=1),
        ),
    )

    assert [tool.status for tool in result.tool_results] == ["denied", "denied"]
    assert result.tool_results[0].error == "tool.unknown"
    assert result.tool_results[1].error == "agent.max_tool_calls_exceeded"
    assert calls == []


def test_registered_agent_sandbox_required_profile_is_enforced(tmp_path):
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(tmp_path / "sandbox-required-audit.jsonl")},
            "rules": [
                {"id": "allow-tools", "environment": "dev", "effect": "allow", "capabilities": ["tool.invoke:*"]},
                {"id": "allow-python", "environment": "dev", "effect": "allow", "capabilities": ["command.execute:python"]},
            ],
        }
    )

    runtime.command_tool(
        name="dangerous_write",
        argv=["python", "-c", "print('written')"],
        cwd=str(tmp_path),
        risk_level="high",
        capabilities_required=["tool.invoke:dangerous_write", "command.execute:python"],
    )

    result = runtime.run_agent(
        "sandbox-required-agent",
        MultiToolAgent(["dangerous_write"]),
        prompt="echo",
        actor={"id": "alice"},
        environment="dev",
        metadata=AgentMetadata(
            agent_id="sandbox-required-agent",
            name="Sandbox Required Agent",
            provider="local",
            framework="plain-python",
            capabilities=["tool.invoke:dangerous_write", "command.execute:python"],
            runtime_profile=RuntimeProfile(environment="dev", max_tool_calls=1, sandbox_required=True),
        ),
    )

    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].error == "agent.sandbox_required"


def test_registered_agent_approval_required_profile_is_enforced(tmp_path):
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(tmp_path / "approval-required-audit.jsonl")},
            "rules": [{"id": "allow-tools", "environment": "dev", "effect": "allow", "capabilities": ["tool.invoke:*"]}],
        }
    )

    @runtime.tool(name="restart_service", risk_level="high")
    def restart_service() -> str:
        return "restarted"

    result = runtime.run_agent(
        "approval-required-agent",
        MultiToolAgent(["restart_service"]),
        prompt="echo",
        actor={"id": "alice"},
        environment="dev",
        metadata=AgentMetadata(
            agent_id="approval-required-agent",
            name="Approval Required Agent",
            provider="local",
            framework="plain-python",
            capabilities=["tool.invoke:restart_service"],
            runtime_profile=RuntimeProfile(environment="dev", max_tool_calls=1, approval_required=True),
        ),
    )

    assert result.tool_results[0].status == "denied"
    assert result.tool_results[0].error == "agent.approval_required"
