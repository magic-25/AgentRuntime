from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class PackValidationError(ValueError):
    pass


class AdapterTranslationError(ValueError):
    pass


SUPPORTED_PACK_KINDS = {"adapter", "sandbox_backend", "pilot", "platform"}
SUPPORTED_SUPPORT_LEVELS = {"experimental", "preview", "stable_candidate", "contract_beta"}


@dataclass(frozen=True)
class PackMetadata:
    pack_id: str
    kind: str
    support_level: str
    dependencies_group: str
    default_enabled: bool = False
    capabilities_declared: list[str] = field(default_factory=list)
    conformance_profile: str = "default"
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.pack_id:
            raise PackValidationError("pack_id is required")
        if self.kind not in SUPPORTED_PACK_KINDS:
            raise PackValidationError(f"kind is unsupported: {self.kind}")
        if self.support_level not in SUPPORTED_SUPPORT_LEVELS:
            raise PackValidationError(f"support_level is unsupported: {self.support_level}")
        if not self.dependencies_group:
            raise PackValidationError("dependencies_group is required")
        if self.default_enabled:
            raise PackValidationError("default_enabled packs are not allowed")


@dataclass(frozen=True)
class PackRegistryResult:
    enabled: list[PackMetadata]
    disabled: dict[str, str]


class PackRegistry:
    def __init__(self, discovered: list[PackMetadata], allowlist: list[str] | None = None) -> None:
        self._discovered = list(discovered)
        self._allowlist = set(allowlist or [])

    def resolve(self) -> PackRegistryResult:
        enabled: list[PackMetadata] = []
        disabled: dict[str, str] = {}
        for metadata in self._discovered:
            if metadata.pack_id not in self._allowlist:
                disabled[metadata.pack_id] = "not_allowlisted"
                continue
            enabled.append(metadata)
        return PackRegistryResult(enabled=enabled, disabled=disabled)


@dataclass(frozen=True)
class RuntimeToolCall:
    tool_name: str
    arguments: dict[str, Any]
    adapter_source: str
    capabilities_granted: list[str] = field(default_factory=list)
