# Agent Runtime

Agent Runtime 是一个 1.0 production core 的 Python agent 工具调用运行时。它把工具调用放进统一链路：

```text
ToolCall -> Context Filter -> Policy Engine -> Approval Gate -> Executor -> Result Filter -> Audit
```

1.0 支持应用团队把 runtime 作为受控生产嵌入核心使用，同时保持生产边界、审计、审批和隔离等级清楚。

## 快速开始

源码模式：

```bash
python -m pytest
PYTHONPATH=src python examples/minimal_agent.py
```

editable install 模式：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
agent-runtime init --path agent-runtime.json
agent-runtime validate --path agent-runtime.json
```

生成起始配置：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main init --path agent-runtime.json
PYTHONPATH=src python -m agent_runtime.cli.main validate --path agent-runtime.json
```

查看 audit：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main audit tail --path .agent-runtime/audit.jsonl
```

0.2 Developer Preview 诊断和查询：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main init --path agent-runtime.json
PYTHONPATH=src python -m agent_runtime.cli.main doctor --path agent-runtime.json
PYTHONPATH=src python -m agent_runtime.cli.main audit query --path .agent-runtime/audit.db --run-id <run_id>
```

0.6 Production Pilot 示例：

```bash
PYTHONPATH=src python examples/staging_internal_admin_pilot.py
PYTHONPATH=src python -m agent_runtime.cli.main audit query --path .agent-runtime/staging-pilot/pilot-audit.db --tool-name read_customer
PYTHONPATH=src python -m agent_runtime.cli.main audit verify --path .agent-runtime/staging-pilot/pilot-audit.db --sink sqlite
```

命令行示例会重置 `.agent-runtime/staging-pilot/` 下由示例生成的 audit、observer 和 report 文件，确保 smoke test 不被旧格式本地审计污染。作为库函数调用 `run_pilot(work_dir)` 时默认不清理已有文件；需要可重复 demo 时显式传入 `reset=True`。

Policy config schema 导出：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main schema export --type policy-config --output policy-config.schema.json
```

1.0 release status：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main release status
```

验证 audit hash chain：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main audit verify --path .agent-runtime/audit.jsonl --sink jsonl
PYTHONPATH=src python -m agent_runtime.cli.main audit verify --path .agent-runtime/staging-pilot/pilot-audit.db --sink sqlite
```

## 0.1 范围

- Python SDK
- JSON 配置加载
- Python function tool
- command tool
- allow / deny / require_approval
- 本地 approval provider 接口
- in-process executor
- subprocess executor
- JSONL audit sink
- 常见 secret 字段脱敏

## 0.2 Developer Preview 范围

- `agent-runtime doctor`
- SQLite audit sink
- `agent-runtime audit query --run-id`
- 更可读的 CLI 配置错误，包含路径、字段和修复建议

## 0.3 Policy & Audit Hardening 范围

- capability-level policy：unknown capability 默认拒绝，deny 覆盖 allow，require approval 可作用于 capability。
- `PolicyEvaluated` audit event 记录 capability、actor、environment、policy version。
- audit event 包含 `event_id`、`trace_id`、`span_id`、`tool_name`。
- SQLite audit query 支持 `run_id`、`trace_id`、`tool_name`。
- policy hook 异常默认 deny。
- approval timeout 默认 reject。
- audit sink 写入失败按环境策略处理。
- 基础 trace span event。
- 配置化 redaction 字段。

## 0.4 Integration Preview 范围

- OpenAI-style adapter spike。
- LangGraph-style adapter spike。
- MCP-style adapter spike。
- adapter 只翻译调用并调用 runtime core，不直接执行工具。
- adapter 来源进入 audit/trace metadata。
- adapter 不能授予 capability。

运行 OpenAI-style 示例：

```bash
PYTHONPATH=src python examples/openai_style_adapter.py
```

## 0.5 Production Readiness Preview 范围

- callback approval provider。
- `agent-runtime policy debug`。
- agent-observer 基础指标。
- `agent-runtime observe status`。
- audit failure 进入 observer metric。
- dev audit failure 默认 warn，prod 默认 fail closed。

## 0.6 Production Pilot 范围

- staging internal admin pilot 示例。
- production pilot report，记录 isolation level、retention、audit sink 责任边界、失败演练和已知绕过方式。
- SQLite audit query 可按 `run_id`、`trace_id`、`tool_name` 任意组合查询。
- runtime 对 executor timeout 和 tool error 返回可区分错误。
- command tool 试点覆盖 cwd、env allowlist、timeout、stdout/stderr 截断。
- 0.6 只表示 production pilot supported，不表示完整生产平台或强 sandbox。

## 0.8 Release Candidate 范围

- policy config JSON Schema release candidate。
- `agent-runtime schema export --type policy-config`。
- 稳定 API 和 experimental API 清单。
- 0.x 到 1.0 迁移说明。
- adapter 和 pilot report 仍标记为 experimental。

## 1.0 Production Core 范围

- Python SDK core。
- policy config schema v1。
- capability policy。
- approval provider interface。
- JSONL / SQLite audit sink。
- tamper-evident audit hash chain。
- audit chain verifier：`agent-runtime audit verify`。
- trace span events。
- observer metrics。
- limited subprocess executor for low-risk allowlisted commands。
- sandbox provider interface；强隔离由宿主接入的 sandbox backend 提供，backend 不可用时 fail closed。
- release manifest：`agent-runtime release status`。

## 1.0 Experimental / Unsupported

- OpenAI-style、LangGraph-style、MCP adapter 仍为 experimental。
- production pilot report 仍为 experimental。
- sidecar、remote、container executor 不属于 1.0 稳定生产承诺。
- 弱隔离 subprocess 不可用于高风险 prod 写操作；不可信代码执行、hosted control plane、RBAC 不属于 1.0 支持范围。

## 安全边界

subprocess executor 不是强安全沙箱。它只提供独立进程、cwd、env allowlist、timeout、stdout/stderr 捕获和输出截断。高风险 prod command tool 必须使用 `sandboxed_command_tool` 和宿主注入的强隔离 sandbox backend；未配置 backend 时 runtime 返回 `sandbox.unavailable`，不会退回普通 subprocess。

JSONL / SQLite audit sink 会写入 `event_hash` 和 `previous_event_hash`，用于检测本地审计链篡改。可以用 `agent-runtime audit verify` 验证链完整性。它不是外部 WORM/合规归档；需要更强追责时应接入宿主的 append-only sink。

## 1.0 Production Core 限制

- 当前已验证源码模式和 editable install 模式。
- 1.0 支持 JSON 配置路径；YAML 可以在后续版本或可选依赖中补齐。
- `tools list` 仍是 CLI 占位命令，不会自动发现宿主应用里的 runtime tool。
- 生产环境建议使用 capability-level policy，并保持 `default_decision: deny`。
