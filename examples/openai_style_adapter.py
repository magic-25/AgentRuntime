from __future__ import annotations

from pathlib import Path

from agent_runtime import AgentRuntime
from agent_runtime.adapters.openai_style import OpenAIStyleAdapter


def main() -> None:
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": ".agent-runtime/openai-style-audit.jsonl"},
            "tracing": {"enabled": True},
            "rules": [
                {
                    "id": "allow-echo",
                    "environment": "dev",
                    "effect": "allow",
                    "capabilities": ["tool.invoke:echo"],
                }
            ],
        }
    )

    @runtime.tool(name="echo", capabilities_required=["tool.invoke:echo"])
    def echo(value: str) -> str:
        return value

    adapter = OpenAIStyleAdapter(runtime)
    result = adapter.call(
        {"type": "function_call", "name": "echo", "arguments": {"value": "hello adapter"}},
        actor={"type": "user", "id": "local"},
        environment="dev",
    )
    print(result.output)
    print(f"audit written to {Path('.agent-runtime/openai-style-audit.jsonl').resolve()}")


if __name__ == "__main__":
    main()
