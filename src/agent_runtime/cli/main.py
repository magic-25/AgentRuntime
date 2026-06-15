from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

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


if __name__ == "__main__":
    raise SystemExit(main())
