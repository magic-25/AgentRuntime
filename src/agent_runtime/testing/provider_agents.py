from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from agent_runtime.core.models import ToolResult
from agent_runtime.core.runtime import AgentRuntime


DEFAULT_GLM_BASE_URL = "https://api.z.ai/api/paas/v4"
DEFAULT_GLM_MODEL = "glm-5.2"


class ProviderAgentError(RuntimeError):
    pass


class ChatCompletionTransport(Protocol):
    def complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class ProviderToolCallingTranscript:
    status: str
    provider: str
    model: str
    decisions: list[str]
    raw_tool_name: str | None = None
    raw_arguments: dict[str, Any] = field(default_factory=dict)
    tool_results: list[ToolResult] = field(default_factory=list)
    error: str | None = None


class OpenAICompatibleChatCompletionTransport:
    def __init__(self, api_key: str, base_url: str, timeout_seconds: float = 30.0) -> None:
        if not api_key:
            raise ProviderAgentError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = _redact_secret(error.read().decode("utf-8", errors="replace"), self.api_key)
            raise ProviderAgentError(f"provider.http_error:{error.code}:{_truncate(detail)}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise ProviderAgentError(f"provider.request_failed:{error}") from error


class OpenAICompatibleToolCallingAgent:
    def __init__(
        self,
        runtime: AgentRuntime,
        transport: ChatCompletionTransport,
        provider: str,
        model: str,
        actor: dict[str, Any],
        environment: str,
    ) -> None:
        self.runtime = runtime
        self.transport = transport
        self.provider = provider
        self.model = model
        self.actor = actor
        self.environment = environment

    def run(self, prompt: str) -> ProviderToolCallingTranscript:
        decisions = [f"request:{self.provider}"]
        response = self.transport.complete(self._payload(prompt))
        tool_call = self._first_tool_call(response)
        if tool_call is None:
            decisions.append("blocked:provider.no_tool_call")
            return ProviderToolCallingTranscript(
                status="blocked",
                provider=self.provider,
                model=self.model,
                decisions=decisions,
                error="provider.no_tool_call",
            )

        tool_name, arguments = tool_call
        decisions.append(f"tool_call:{tool_name}")
        result = self.runtime.call_tool(
            tool_name,
            arguments,
            actor=self.actor,
            environment=self.environment,
            adapter_source=self.provider,
        )
        decisions.append(f"runtime:{result.status}")
        decisions.append("stop" if result.status == "success" else "blocked")
        return ProviderToolCallingTranscript(
            status="completed" if result.status == "success" else "blocked",
            provider=self.provider,
            model=self.model,
            raw_tool_name=tool_name,
            raw_arguments=arguments,
            tool_results=[result],
            decisions=decisions,
            error=result.error,
        )

    def _payload(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a test agent. Use the available tool exactly once when the user asks "
                        "for echo, and do not include secrets in tool arguments."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "echo",
                        "description": "Echo a short test message through Agent Runtime.",
                        "parameters": {
                            "type": "object",
                            "properties": {"message": {"type": "string"}},
                            "required": ["message"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            "tool_choice": "auto",
            "temperature": 0,
        }

    def _first_tool_call(self, response: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
        choices = response.get("choices", [])
        if not choices:
            return None
        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            return None
        function = tool_calls[0].get("function", {})
        name = function.get("name")
        if not name:
            return None
        return name, _coerce_arguments(function.get("arguments", {}))


def create_glm_tool_calling_agent_from_env(
    runtime: AgentRuntime,
    actor: dict[str, Any],
    environment: str,
    env_path: str | Path | None = ".env",
) -> OpenAICompatibleToolCallingAgent:
    dotenv = _read_dotenv(env_path)
    api_key = _env_or_dotenv("GLM_API_KEY", dotenv) or _env_or_dotenv("ZAI_API_KEY", dotenv)
    if not api_key:
        raise ProviderAgentError("GLM_API_KEY or ZAI_API_KEY is required")
    base_url = _env_or_dotenv("GLM_BASE_URL", dotenv) or _env_or_dotenv("ZAI_BASE_URL", dotenv) or DEFAULT_GLM_BASE_URL
    model = _env_or_dotenv("GLM_MODEL", dotenv) or _env_or_dotenv("ZAI_MODEL", dotenv) or DEFAULT_GLM_MODEL
    timeout_seconds = float(_env_or_dotenv("GLM_TIMEOUT_SECONDS", dotenv) or "30")
    return OpenAICompatibleToolCallingAgent(
        runtime=runtime,
        transport=OpenAICompatibleChatCompletionTransport(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        ),
        provider="glm",
        model=model,
        actor=actor,
        environment=environment,
    )


def _coerce_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise ProviderAgentError("provider.arguments_invalid") from error
    if not isinstance(value, dict):
        raise ProviderAgentError("provider.arguments_invalid")
    return value


def _truncate(value: str, limit: int = 240) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def _redact_secret(value: str, secret: str) -> str:
    if not secret:
        return value
    return value.replace(secret, "[REDACTED]")


def _env_or_dotenv(key: str, dotenv: dict[str, str]) -> str | None:
    return os.getenv(key) or dotenv.get(key)


def _read_dotenv(env_path: str | Path | None) -> dict[str, str]:
    if env_path is None:
        return {}
    path = Path(env_path)
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _strip_dotenv_quotes(value.strip())
    return values


def _strip_dotenv_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
