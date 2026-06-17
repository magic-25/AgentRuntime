import json

from agent_runtime import AgentMetadata as PublicAgentMetadata
from agent_runtime import AgentRuntime as PublicAgentRuntime
from agent_runtime import RuntimeProfile as PublicRuntimeProfile
from agent_runtime.core.models import AgentMetadata, RuntimeProfile
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.testing.provider_agents import OpenAICompatibleToolCallingAgent


class FakeOpenAICompatibleTransport:
    def __init__(self, message: str):
        self.message = message

    def complete(self, payload):
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "echo",
                                    "arguments": json.dumps({"message": self.message}),
                                },
                            }
                        ]
                    }
                }
            ]
        }


def _runtime(tmp_path, allow_echo=True):
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(tmp_path / "agent-audit.jsonl")},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}] if allow_echo else [],
        }
    )

    @runtime.tool(name="echo")
    def echo(message: str) -> dict[str, str]:
        return {"message": message}

    return runtime


def _agent(message="contract"):
    return OpenAICompatibleToolCallingAgent(
        runtime=None,
        transport=FakeOpenAICompatibleTransport(message),
        provider="glm",
        model="glm-5.2",
        actor={"id": "glm-agent"},
        environment="dev",
    )


def _audit_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_agent_registry_contract_types_are_public_api():
    assert PublicAgentMetadata is AgentMetadata
    assert PublicRuntimeProfile is RuntimeProfile
    assert PublicAgentRuntime is AgentRuntime


def test_register_agent_records_formal_metadata_profile_capabilities_and_lifecycle(tmp_path):
    runtime = _runtime(tmp_path)
    metadata = AgentMetadata(
        agent_id="glm-agent",
        name="GLM tool caller",
        provider="glm",
        framework="openai-compatible",
        version="test",
        capabilities=["tool.invoke:echo"],
        runtime_profile=RuntimeProfile(
            environment="dev",
            execution_mode="runtime_tools",
            max_tool_calls=1,
            network_access=True,
        ),
    )

    registered = runtime.register_agent(
        "glm-agent",
        _agent(),
        actor={"id": "glm-agent"},
        environment="dev",
        metadata=metadata,
    )
    transcript = registered.run("Call echo.")

    assert registered.metadata == metadata
    assert transcript.registration == "registered"
    assert transcript.agent_metadata == metadata.to_dict()
    assert transcript.audit_events == [
        "AgentRegistered",
        "AgentRunStarted",
        "ToolCallRequested",
        "PolicyEvaluated",
        "ToolExecutionStarted",
        "ToolExecutionFinished",
        "AgentRunFinished",
    ]

    events = _audit_events(tmp_path / "agent-audit.jsonl")
    registered_payload = events[0]["payload"]
    assert registered_payload["agent_id"] == "glm-agent"
    assert registered_payload["metadata"]["provider"] == "glm"
    assert registered_payload["metadata"]["capabilities"] == ["tool.invoke:echo"]
    assert registered_payload["metadata"]["runtime_profile"]["execution_mode"] == "runtime_tools"
    assert events[1]["payload"]["metadata"]["runtime_profile"]["max_tool_calls"] == 1


def test_registered_agent_deny_path_cannot_fall_back_to_direct_execution(tmp_path):
    runtime = _runtime(tmp_path, allow_echo=False)
    direct_calls = []

    def direct_echo(message: str) -> dict[str, str]:
        direct_calls.append(message)
        return {"message": message}

    agent = _agent("deny me")
    # The same agent can run direct when it is intentionally unregistered.
    unregistered = agent.run_unregistered("Call echo.", direct_tools={"echo": direct_echo})
    assert unregistered.status == "completed"
    assert direct_calls == ["deny me"]

    direct_calls.clear()
    registered = runtime.register_agent(
        "glm-agent",
        agent,
        actor={"id": "glm-agent"},
        environment="dev",
        direct_tools={"echo": direct_echo},
    ).run("Call echo.")

    assert registered.status == "blocked"
    assert registered.tool_results[0].status == "denied"
    assert registered.tool_results[0].output is None
    assert registered.decisions == ["request:glm", "tool_call:echo", "runtime:denied", "blocked"]
    assert direct_calls == []
    assert "ToolExecutionFinished" not in registered.audit_events
    assert "RuntimeError" in registered.audit_events
