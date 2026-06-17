import json
import os

import pytest

from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.testing.provider_agents import (
    OpenAICompatibleChatCompletionTransport,
    OpenAICompatibleToolCallingAgent,
    ProviderAgentError,
    create_glm_tool_calling_agent_from_env,
)


class FakeOpenAICompatibleTransport:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def complete(self, payload):
        self.requests.append(payload)
        return self.response


def _runtime(tmp_path):
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(tmp_path / "provider-audit.jsonl")},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(message: str) -> dict[str, str]:
        return {"message": message}

    return runtime


def test_openai_compatible_provider_agent_executes_model_tool_call_through_runtime(tmp_path):
    transport = FakeOpenAICompatibleTransport(
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "echo",
                                    "arguments": json.dumps({"message": "hello from provider"}),
                                },
                            }
                        ]
                    }
                }
            ]
        }
    )
    agent = OpenAICompatibleToolCallingAgent(
        runtime=_runtime(tmp_path),
        transport=transport,
        provider="glm",
        model="glm-5.2",
        actor={"id": "glm-agent"},
        environment="dev",
    )

    transcript = agent.run("Call the echo tool with hello from provider.")

    assert transport.requests[0]["model"] == "glm-5.2"
    assert transport.requests[0]["tool_choice"] == "auto"
    assert transport.requests[0]["tools"][0]["function"]["name"] == "echo"
    assert transcript.status == "completed"
    assert transcript.provider == "glm"
    assert transcript.model == "glm-5.2"
    assert transcript.raw_tool_name == "echo"
    assert transcript.raw_arguments == {"message": "hello from provider"}
    assert transcript.tool_results[0].status == "success"
    assert transcript.tool_results[0].output == {"message": "hello from provider"}
    assert transcript.decisions == ["request:glm", "tool_call:echo", "runtime:success", "stop"]


def test_openai_compatible_provider_agent_blocks_when_model_returns_no_tool_call(tmp_path):
    agent = OpenAICompatibleToolCallingAgent(
        runtime=_runtime(tmp_path),
        transport=FakeOpenAICompatibleTransport({"choices": [{"message": {"content": "no tool"}}]}),
        provider="glm",
        model="glm-5.2",
        actor={"id": "glm-agent"},
        environment="dev",
    )

    transcript = agent.run("Call the echo tool.")

    assert transcript.status == "blocked"
    assert transcript.error == "provider.no_tool_call"
    assert transcript.tool_results == []
    assert transcript.decisions == ["request:glm", "blocked:provider.no_tool_call"]


def test_glm_provider_agent_factory_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)

    with pytest.raises(ProviderAgentError, match="GLM_API_KEY"):
        create_glm_tool_calling_agent_from_env(
            runtime=_runtime(tmp_path),
            actor={"id": "glm-agent"},
            environment="dev",
        )


def test_glm_provider_agent_factory_reads_ignored_dotenv_file(monkeypatch, tmp_path):
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "GLM_API_KEY=dotenv-secret-key",
                "GLM_BASE_URL=https://example.invalid/api/paas/v4",
                "GLM_MODEL=glm-test-model",
            ]
        ),
        encoding="utf-8",
    )

    agent = create_glm_tool_calling_agent_from_env(
        runtime=_runtime(tmp_path),
        actor={"id": "glm-agent"},
        environment="dev",
        env_path=env_path,
    )

    assert agent.transport.api_key == "dotenv-secret-key"
    assert agent.transport.base_url == "https://example.invalid/api/paas/v4"
    assert agent.model == "glm-test-model"


def test_openai_compatible_transport_redacts_api_key_from_provider_errors(monkeypatch):
    api_key = "test-secret-provider-key"

    class ErrorBody:
        def read(self):
            return f"bad credentials: {api_key}".encode("utf-8")

        def close(self):
            return None

    def fail_urlopen(request, timeout):
        raise urllib_error.HTTPError(
            url=request.full_url,
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=ErrorBody(),
        )

    from urllib import error as urllib_error

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)
    transport = OpenAICompatibleChatCompletionTransport(
        api_key=api_key,
        base_url="https://example.invalid/api/paas/v4",
    )

    with pytest.raises(ProviderAgentError) as error:
        transport.complete({"model": "glm-5.2", "messages": []})

    assert api_key not in str(error.value)
    assert "[REDACTED]" in str(error.value)


@pytest.mark.integration
def test_glm_provider_agent_can_call_real_provider_when_key_is_configured(tmp_path):
    if not (os.getenv("GLM_API_KEY") or os.getenv("ZAI_API_KEY")):
        pytest.skip("Set GLM_API_KEY or ZAI_API_KEY to run the real GLM provider integration test")

    agent = create_glm_tool_calling_agent_from_env(
        runtime=_runtime(tmp_path),
        actor={"id": "glm-agent"},
        environment="dev",
    )

    transcript = agent.run("Call the echo tool exactly once with message 'hello from glm provider'.")

    assert transcript.status == "completed"
    assert transcript.raw_tool_name == "echo"
    assert transcript.tool_results[0].status == "success"
