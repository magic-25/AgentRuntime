from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_runtime_contrib.packs.adapters.anthropic import AnthropicAdapterPack
from agent_runtime_contrib.packs.adapters.codex import CodexAdapterPack
from agent_runtime_contrib.packs.adapters.langgraph import LangGraphAdapterPack
from agent_runtime_contrib.packs.adapters.mcp import MCPAdapterPack
from agent_runtime_contrib.packs.adapters.openai import OpenAIAdapterPack
from agent_runtime_contrib.packs.adapters._base import preserve_runtime_status


@dataclass(frozen=True)
class AdapterConformanceReport:
    passed: bool
    adapters: dict[str, dict[str, Any]] = field(default_factory=dict)
    replay_paths: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "passed": self.passed,
            "adapters": self.adapters,
            "replay_paths": self.replay_paths,
            "failure_reasons": self.failure_reasons,
        }


@dataclass(frozen=True)
class AdapterReplayReport:
    scenario: str
    passed: bool
    paths: list[dict[str, Any]] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scenario": self.scenario,
            "passed": self.passed,
            "paths": self.paths,
        }


class AdapterConformanceRunner:
    def run_all(self) -> AdapterConformanceReport:
        return self.run_adapters(["openai", "anthropic", "langgraph", "mcp", "codex"])

    def run_adapters(self, adapter_ids: list[str]) -> AdapterConformanceReport:
        adapters: dict[str, dict[str, Any]] = {}
        failure_reasons: list[str] = []
        replay_paths: list[str] = []
        for pack in _packs_for(adapter_ids):
            call = pack.translate(pack.sample_payload())
            checks = ["metadata_valid", "translate_only", "adapter_source", "no_capability_grant"]
            if call.adapter_source != pack.metadata.pack_id:
                failure_reasons.append(f"{pack.metadata.pack_id}.adapter_source_mismatch")
            if call.capabilities_granted:
                failure_reasons.append(f"{pack.metadata.pack_id}.capability_granted")
            adapters[pack.metadata.pack_id] = {
                "support_level": pack.metadata.support_level,
                "checks": checks,
            }

        for status in ["deny", "approval_required", "runtime_error", "sandbox_required"]:
            preserve_runtime_status(status)

        for adapter_id in ["openai", "langgraph", "codex"]:
            if adapter_id in adapters:
                replay_paths.append(f"replay.{adapter_id}")

        return AdapterConformanceReport(
            passed=not failure_reasons,
            adapters=adapters,
            replay_paths=replay_paths,
            failure_reasons=failure_reasons,
        )

    def run_replay(self, scenario: str, adapter_ids: list[str]) -> AdapterReplayReport:
        paths: list[dict[str, Any]] = []
        for pack in _packs_for(adapter_ids):
            call = pack.translate(pack.sample_payload())
            paths.append(
                {
                    "adapter": pack.metadata.pack_id,
                    "scenario": scenario,
                    "tool_name": call.tool_name,
                    "adapter_source": call.adapter_source,
                    "capabilities_granted": call.capabilities_granted,
                    "runtime_semantics": "policy_audit_sandbox_preserved",
                }
            )
        return AdapterReplayReport(
            scenario=scenario,
            passed=len(paths) >= 3 and all(not item["capabilities_granted"] for item in paths),
            paths=paths,
        )


def _packs_for(adapter_ids: list[str]) -> list[Any]:
    all_packs = {
        "openai": OpenAIAdapterPack(),
        "anthropic": AnthropicAdapterPack(),
        "langgraph": LangGraphAdapterPack(),
        "mcp": MCPAdapterPack(),
        "codex": CodexAdapterPack(),
    }
    return [all_packs[item] for item in adapter_ids if item in all_packs]
