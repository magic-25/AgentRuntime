import pytest

from agent_runtime.core.models import AgentMetadata, RuntimeProfile
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.testing.langgraph_agents import LangGraphToolCallingAgent


langgraph_graph = pytest.importorskip("langgraph.graph")


def _langgraph_echo_graph():
    graph = langgraph_graph.StateGraph(dict)

    def choose_echo(state):
        return {"tool_name": "echo", "arguments": {"message": state["message"]}}

    graph.add_node("choose_echo", choose_echo)
    graph.add_edge(langgraph_graph.START, "choose_echo")
    graph.add_edge("choose_echo", langgraph_graph.END)
    return graph.compile()


def _runtime(tmp_path):
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(tmp_path / "langgraph-agent-audit.jsonl")},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(message: str) -> dict[str, str]:
        return {"message": message}

    return runtime


def test_langgraph_agent_compares_unregistered_and_registered_runtime_execution(tmp_path):
    agent = LangGraphToolCallingAgent(
        runtime=None,
        graph=_langgraph_echo_graph(),
        actor={"id": "langgraph-agent"},
        environment="dev",
    )

    def direct_echo(message: str) -> dict[str, str]:
        return {"message": message}

    unregistered = agent.run_unregistered(
        "langgraph registration comparison",
        direct_tools={"echo": direct_echo},
    )

    runtime = _runtime(tmp_path)
    metadata = AgentMetadata(
        agent_id="langgraph-agent",
        name="LangGraph echo agent",
        provider="local",
        framework="langgraph",
        capabilities=["tool.invoke:echo"],
        runtime_profile=RuntimeProfile(environment="dev", execution_mode="runtime_tools", max_tool_calls=1),
    )
    registered = runtime.register_agent(
        "langgraph-agent",
        agent,
        actor={"id": "langgraph-agent"},
        environment="dev",
        metadata=metadata,
    ).run("langgraph registration comparison")

    assert unregistered.registration == "unregistered"
    assert unregistered.decisions == ["graph:invoke", "tool_call:echo", "direct:success", "stop"]
    assert unregistered.tool_results[0].run_id is None
    assert unregistered.audit_events == []

    assert registered.registration == "registered"
    assert registered.agent_id == "langgraph-agent"
    assert registered.agent_metadata["framework"] == "langgraph"
    assert registered.decisions == ["graph:invoke", "tool_call:echo", "runtime:success", "stop"]
    assert registered.tool_results[0].run_id is not None
    assert registered.audit_events == [
        "AgentRegistered",
        "AgentRunStarted",
        "ToolCallRequested",
        "PolicyEvaluated",
        "ToolExecutionStarted",
        "ToolExecutionFinished",
        "AgentRunFinished",
    ]
