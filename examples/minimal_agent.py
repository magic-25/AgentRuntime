from __future__ import annotations

from pathlib import Path

from agent_runtime import AgentRuntime


def main() -> None:
    runtime = AgentRuntime.from_dict(
        {
            "default_decision": "deny",
            "audit": {"path": ".agent-runtime/audit.jsonl"},
            "rules": [
                {"id": "dev-echo", "environment": "dev", "tool": "echo", "effect": "allow"},
            ],
        }
    )

    @runtime.tool(name="echo", description="Echo a safe message")
    def echo(message: str) -> str:
        return message

    result = runtime.call_tool(
        "echo",
        {"message": "hello agent runtime"},
        actor={"type": "user", "id": "local"},
        environment="dev",
    )
    print(result.output)
    print(f"audit written to {Path('.agent-runtime/audit.jsonl').resolve()}")


if __name__ == "__main__":
    main()
