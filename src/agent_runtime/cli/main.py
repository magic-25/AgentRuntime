from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from agent_runtime.audit.sqlite import SQLiteAuditSink
from agent_runtime.audit.verify import verify_audit_chain
from agent_runtime.core.registry import ToolRegistry
from agent_runtime.policy.engine import PolicyEngine
from agent_runtime.release import production_release_manifest
from agent_runtime.schema.policy_config import policy_config_schema


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-runtime")
    subcommands = parser.add_subparsers(dest="command", required=True)

    init_parser = subcommands.add_parser("init")
    init_parser.add_argument("--path", default="agent-runtime.json")

    validate_parser = subcommands.add_parser("validate")
    validate_parser.add_argument("--path", default="agent-runtime.json")

    doctor_parser = subcommands.add_parser("doctor")
    doctor_parser.add_argument("--path", default="agent-runtime.json")

    tools_parser = subcommands.add_parser("tools")
    tools_subcommands = tools_parser.add_subparsers(dest="tools_command", required=True)
    tools_subcommands.add_parser("list")

    audit_parser = subcommands.add_parser("audit")
    audit_subcommands = audit_parser.add_subparsers(dest="audit_command", required=True)
    tail_parser = audit_subcommands.add_parser("tail")
    tail_parser.add_argument("--path", default=".agent-runtime/audit.jsonl")
    query_parser = audit_subcommands.add_parser("query")
    query_parser.add_argument("--path", default=".agent-runtime/audit.db")
    query_parser.add_argument("--run-id")
    query_parser.add_argument("--trace-id")
    query_parser.add_argument("--tool-name")
    verify_parser = audit_subcommands.add_parser("verify")
    verify_parser.add_argument("--path", required=True)
    verify_parser.add_argument("--sink", choices=["jsonl", "sqlite"], required=True)

    observe_parser = subcommands.add_parser("observe")
    observe_subcommands = observe_parser.add_subparsers(dest="observe_command", required=True)
    status_parser = observe_subcommands.add_parser("status")
    status_parser.add_argument("--path", default=".agent-runtime/observer.json")

    policy_parser = subcommands.add_parser("policy")
    policy_subcommands = policy_parser.add_subparsers(dest="policy_command", required=True)
    debug_parser = policy_subcommands.add_parser("debug")
    debug_parser.add_argument("--path", default="agent-runtime.json")
    debug_parser.add_argument("--tool", required=True)
    debug_parser.add_argument("--environment", required=True)

    schema_parser = subcommands.add_parser("schema")
    schema_subcommands = schema_parser.add_subparsers(dest="schema_command", required=True)
    schema_export_parser = schema_subcommands.add_parser("export")
    schema_export_parser.add_argument("--type", choices=["policy-config"], required=True)
    schema_export_parser.add_argument("--output")

    release_parser = subcommands.add_parser("release")
    release_subcommands = release_parser.add_subparsers(dest="release_command", required=True)
    release_subcommands.add_parser("status")

    contrib_parser = subcommands.add_parser("contrib")
    contrib_subcommands = contrib_parser.add_subparsers(dest="contrib_command", required=True)
    contrib_subcommands.add_parser("list")
    contrib_check_parser = contrib_subcommands.add_parser("check")
    contrib_check_parser.add_argument("--config")

    conformance_parser = subcommands.add_parser("conformance")
    conformance_subcommands = conformance_parser.add_subparsers(dest="conformance_command", required=True)
    conformance_run_parser = conformance_subcommands.add_parser("run")
    conformance_run_parser.add_argument("--pack", required=True)
    conformance_run_parser.add_argument("--dry-run", action="store_true")

    adapter_parser = subcommands.add_parser("adapter")
    adapter_subcommands = adapter_parser.add_subparsers(dest="adapter_command", required=True)
    adapter_conformance_parser = adapter_subcommands.add_parser("conformance")
    adapter_conformance_parser.add_argument("--adapter", required=True)
    adapter_conformance_parser.add_argument("--dry-run", action="store_true")
    adapter_replay_parser = adapter_subcommands.add_parser("replay")
    adapter_replay_parser.add_argument("--scenario", required=True)
    adapter_replay_parser.add_argument("--adapter", action="append", required=True)

    certify_parser = subcommands.add_parser("certify")
    certify_subcommands = certify_parser.add_subparsers(dest="certify_command", required=True)
    certify_run_parser = certify_subcommands.add_parser("run")
    certify_run_parser.add_argument("--subject", default="all")

    pilot_parser = subcommands.add_parser("pilot")
    pilot_subcommands = pilot_parser.add_subparsers(dest="pilot_command", required=True)
    pilot_code_ci_parser = pilot_subcommands.add_parser("code-ci")
    pilot_code_ci_parser.add_argument("--repo", required=True)
    pilot_code_ci_parser.add_argument("--command", dest="pilot_shell_command", required=True)
    pilot_code_ci_parser.add_argument("--allow-command", action="append", default=[])
    pilot_code_ci_parser.add_argument("--write-scope", required=True)
    pilot_code_ci_parser.add_argument("--report")

    sandbox_parser = subcommands.add_parser("sandbox")
    sandbox_subcommands = sandbox_parser.add_subparsers(dest="sandbox_command", required=True)
    sandbox_conformance_parser = sandbox_subcommands.add_parser("conformance")
    sandbox_conformance_parser.add_argument("--backend", choices=["container", "sidecar", "remote"], required=True)
    sandbox_conformance_parser.add_argument("--dry-run", action="store_true")
    sandbox_evidence_parser = sandbox_subcommands.add_parser("evidence")
    sandbox_evidence_parser.add_argument("--backend", choices=["container"], required=True)
    sandbox_evidence_parser.add_argument("--run-smoke", action="store_true")
    sandbox_evidence_parser.add_argument("--image", default="busybox:latest")

    platform_parser = subcommands.add_parser("platform")
    platform_subcommands = platform_parser.add_subparsers(dest="platform_command", required=True)
    platform_simulate_parser = platform_subcommands.add_parser("simulate")
    platform_simulate_parser.add_argument("--scenario", default="all")

    args = parser.parse_args(argv)

    if args.command == "init":
        Path(args.path).write_text(
            json.dumps({"version": 1, "default_decision": "deny", "rules": [], "audit": {}}, indent=2),
            encoding="utf-8",
        )
        return 0

    if args.command == "validate":
        result = _validate_config(Path(args.path))
        if result.valid:
            return 0
        print(result.message)
        return 1

    if args.command == "doctor":
        result = _validate_config(Path(args.path))
        if result.valid:
            print(f"ok: {args.path}")
            return 0
        print(result.message)
        return 1

    if args.command == "tools" and args.tools_command == "list":
        print("No runtime tools loaded from CLI in 0.1 preview.")
        return 0

    if args.command == "audit" and args.audit_command == "tail":
        path = Path(args.path)
        if not path.exists():
            return 1
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines[-20:]:
            print(line)
        return 0

    if args.command == "audit" and args.audit_command == "query":
        for event in SQLiteAuditSink(args.path).query(run_id=args.run_id, trace_id=args.trace_id, tool_name=args.tool_name):
            print(json.dumps(event, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "audit" and args.audit_command == "verify":
        result = verify_audit_chain(args.path, sink=args.sink)
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
        return 0 if result.valid else 1

    if args.command == "observe" and args.observe_command == "status":
        try:
            status = json.loads(Path(args.path).read_text(encoding="utf-8"))
        except OSError:
            print(f"observer status not found: {args.path}")
            return 1
        print(json.dumps(status, ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "policy" and args.policy_command == "debug":
        config = json.loads(Path(args.path).read_text(encoding="utf-8"))
        registry = ToolRegistry()
        tool_config = config.get("tools", {}).get(args.tool, {})
        registry.register_command(
            name=args.tool,
            command={"argv": [args.tool], "cwd": ".", "env": {}, "env_allowlist": []},
            capabilities_required=tool_config.get("capabilities_required", [f"tool.invoke:{args.tool}"]),
        )
        decision = PolicyEngine(config, registry).evaluate(args.tool, args.environment, actor={})
        print(
            json.dumps(
                {
                    "decision": decision.decision,
                    "rule_id": decision.rule_id,
                    "capability": decision.capability,
                    "environment": decision.environment,
                    "reason": decision.reason,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "schema" and args.schema_command == "export":
        schema = policy_config_schema()
        payload = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True)
        if args.output:
            Path(args.output).write_text(payload, encoding="utf-8")
        else:
            print(payload)
        return 0

    if args.command == "release" and args.release_command == "status":
        print(json.dumps(production_release_manifest(), ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "contrib" and args.contrib_command == "list":
        print(json.dumps(_contrib_list_payload(), ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "contrib" and args.contrib_command == "check":
        print(json.dumps(_contrib_list_payload(), ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "conformance" and args.conformance_command == "run":
        print(json.dumps(_conformance_run_payload(args.pack, args.dry_run), ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "adapter" and args.adapter_command == "conformance":
        print(json.dumps(_adapter_conformance_payload(args.adapter, args.dry_run), ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "adapter" and args.adapter_command == "replay":
        print(json.dumps(_adapter_replay_payload(args.scenario, args.adapter), ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "certify" and args.certify_command == "run":
        print(json.dumps(_certify_run_payload(args.subject), ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "pilot" and args.pilot_command == "code-ci":
        print(
            json.dumps(
                _pilot_code_ci_payload(args.repo, args.pilot_shell_command, args.allow_command, args.write_scope, args.report),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "sandbox" and args.sandbox_command == "conformance":
        print(json.dumps(_sandbox_conformance_payload(args.backend, args.dry_run), ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "sandbox" and args.sandbox_command == "evidence":
        print(json.dumps(_sandbox_evidence_payload(args.backend, args.run_smoke, args.image), ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "platform" and args.platform_command == "simulate":
        print(json.dumps(_platform_simulation_payload(args.scenario), ensure_ascii=False, sort_keys=True))
        return 0

    return 1


class ValidationResult:
    def __init__(self, valid: bool, message: str = "") -> None:
        self.valid = valid
        self.message = message


def _validate_config(path: Path) -> ValidationResult:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        return ValidationResult(False, f"配置路径 {path} 无法读取：{error}。建议：确认文件存在。")
    except json.JSONDecodeError as error:
        return ValidationResult(False, f"配置路径 {path} 不是有效 JSON：{error}。建议：修复 JSON 格式。")
    if config.get("default_decision") not in {"allow", "deny"}:
        return ValidationResult(False, f"配置路径 {path} 字段 default_decision 无效。建议：设置为 deny。")
    if config.get("version") != 1:
        return ValidationResult(False, f"配置路径 {path} 字段 version 无效。建议：设置为 1。")
    if not isinstance(config.get("rules"), list):
        return ValidationResult(False, f"配置路径 {path} 字段 rules 无效。建议：设置为空数组或规则数组。")
    return ValidationResult(True)


def _builtin_adapter_packs() -> list[Any]:
    from agent_runtime_contrib.packs.adapters.anthropic import AnthropicAdapterPack
    from agent_runtime_contrib.packs.adapters.codex import CodexAdapterPack
    from agent_runtime_contrib.packs.adapters.langgraph import LangGraphAdapterPack
    from agent_runtime_contrib.packs.adapters.mcp import MCPAdapterPack
    from agent_runtime_contrib.packs.adapters.openai import OpenAIAdapterPack

    return [OpenAIAdapterPack(), AnthropicAdapterPack(), LangGraphAdapterPack(), MCPAdapterPack(), CodexAdapterPack()]


def _contrib_list_payload() -> dict[str, Any]:
    from agent_runtime_contrib.packs.base import PackRegistry

    metadata = [pack.metadata for pack in _builtin_adapter_packs()]
    result = PackRegistry(metadata, allowlist=[]).resolve()
    enabled_ids = {pack.pack_id for pack in result.enabled}
    return {
        "packs": [
            {
                "pack_id": pack.pack_id,
                "kind": pack.kind,
                "support_level": pack.support_level,
                "enabled": pack.pack_id in enabled_ids,
                "disabled_reason": result.disabled.get(pack.pack_id),
            }
            for pack in metadata
        ]
    }


def _conformance_run_payload(pack_id: str, dry_run: bool) -> dict[str, Any]:
    from agent_runtime_contrib.conformance import ConformanceRunner

    runner = ConformanceRunner()
    packs = _builtin_adapter_packs()
    selected = packs if pack_id == "all" else [pack for pack in packs if pack.metadata.pack_id == pack_id]
    return {
        "dry_run": dry_run,
        "reports": [runner.run_adapter_pack(pack).to_dict() for pack in selected],
    }


def _pilot_code_ci_payload(
    repo: str,
    command: str,
    allow_commands: list[str],
    write_scope: str,
    report: str | None,
) -> dict[str, Any]:
    import shlex

    from agent_runtime_contrib.pilot.code_ci import CodeCIPilot

    parsed_command = shlex.split(command)
    parsed_allowlist = [shlex.split(item) for item in allow_commands]
    result = CodeCIPilot(allowed_commands=parsed_allowlist).run(
        repo_path=repo,
        command=parsed_command,
        write_scope=write_scope,
        report_path=report,
    )
    return result.to_dict()


def _sandbox_conformance_payload(backend: str, dry_run: bool) -> dict[str, Any]:
    from agent_runtime_contrib.sandbox_conformance import SandboxConformanceRunner, backend_for_name

    report = SandboxConformanceRunner().run_backend(backend_for_name(backend))
    return {"dry_run": dry_run, "report": report.to_dict()}


def _adapter_conformance_payload(adapter: str, dry_run: bool) -> dict[str, Any]:
    from agent_runtime_contrib.adapter_conformance import AdapterConformanceRunner

    runner = AdapterConformanceRunner()
    report = runner.run_all() if adapter == "all" else runner.run_adapters([adapter])
    return {"dry_run": dry_run, "report": report.to_dict()}


def _adapter_replay_payload(scenario: str, adapters: list[str]) -> dict[str, Any]:
    from agent_runtime_contrib.adapter_conformance import AdapterConformanceRunner

    return AdapterConformanceRunner().run_replay(scenario, adapter_ids=adapters).to_dict()


def _certify_run_payload(subject: str) -> dict[str, Any]:
    from agent_runtime.certification import build_platform_ready_certification_report

    return build_platform_ready_certification_report(subject=subject).to_dict()


def _sandbox_evidence_payload(backend: str, run_smoke: bool, image: str) -> dict[str, Any]:
    from agent_runtime_contrib.sandbox_evidence import DockerRuntimeEvidenceCollector

    if backend != "container":
        raise ValueError(f"unsupported sandbox evidence backend: {backend}")
    return DockerRuntimeEvidenceCollector().collect(run_smoke=run_smoke, image=image).to_dict()


def _platform_simulation_payload(scenario: str) -> dict[str, Any]:
    from agent_runtime.control_plane.platform import PlatformSimulationHarness

    report = PlatformSimulationHarness().run_all()
    payload = report.to_dict()
    payload["requested_scenario"] = scenario
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
