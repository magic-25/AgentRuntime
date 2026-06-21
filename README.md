# Agent Runtime

Agent Runtime 是一个面向生产 agent 工具调用的 Python runtime。它把工具调用放进统一链路：

```text
ToolCall -> Context Filter -> Policy Engine -> Approval Gate -> Executor -> Result Filter -> Audit
```

当前公开状态：**Technical Preview**。  
下一门禁：**Design Partner Pilot**。

这不是 public launch，也不是 hosted enterprise platform。当前重点是把 runtime contracts、policy/audit/sandbox、adapter、conformance certification 和 platform-ready manifest 做到可验证，供少量 design partner 在真实场景中试点。

Python 包版本使用 `0.x`，表示当前是开源 technical preview；`release status` 中的 `1.0` / `2.0` 表示内部 runtime contract 阶段，不等同于公开稳定版发布。

## English Summary

Agent Runtime is a Python technical preview for running agent tool calls through policy, approval, execution, sandbox contracts, tracing, observer metrics, and audit evidence. It is intended for design partner pilots and local/runtime integration experiments, not for hosted SaaS, an enterprise console, or a stable public platform release.

Quick start:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
python examples/minimal_agent.py
```

Before using high-risk tools, read the [Security Boundary](#security-boundary) section. `subprocess` is not a strong sandbox, and sandbox backends remain explicit opt-in.

## 项目文档

- [用户指南：场景与概念](/docs/user-guide.md)
- [Agent Registry Contract](/docs/reference/agent-registry-contract.md)
- [Design Partner Runbook](/docs/runbooks/design-partner-runbook.md)
- [测试与验证报告](/docs/reports/test-report.md)
- [Roadmap：版本与阶段说明](ROADMAP.md)
- [文档索引](/docs/README.md)
- [贡献指南](CONTRIBUTING.md)
- [安全策略](SECURITY.md)

## 当前能力

### Production Core

- Python SDK core。
- policy config schema v1。
- capability-level policy。
- approval provider interface。
- JSONL / SQLite audit sink。
- tamper-evident audit hash chain。
- audit chain verifier。
- trace span events。
- observer metrics。
- limited subprocess executor。
- sandbox provider interface。
- agent execution session contract：`AgentRunRequest` / `AgentRunResult`。

### Contrib / Adapter / Sandbox Preview

- `agent_runtime_contrib` package shell。
- pack registry，默认 disabled，必须 explicit allowlist。
- OpenAI、Anthropic、LangGraph、MCP、Codex workspace adapter stable candidate。
- adapter conformance 和 replay。
- container plan backend stable candidate contract，不执行真实 Docker container。
- Docker sandbox backend preview，显式 opt-in，使用本地 Docker daemon 执行 no-network/read-only/cap-drop command。
- sidecar backend preview。
- remote executor contract beta。
- sandbox conformance 和 Docker runtime evidence。
- Code/CI reference pilot。
- GLM/OpenAI-compatible provider agent optional integration test。
- agent registration lifecycle comparison test。
- formal agent registry contract。
- generic registered agent `run_session(...)`，支持任意 Python agent 输出并生成统一运行结果。
- governed agent tracing test。
- complete runtime report runner。
- single agent run screenshot runner。
- provider retry/backoff test。
- optional LangGraph framework agent registration test。

### Platform-Ready Contracts

- policy bundle validation。
- audit forwarding contract。
- run export contract，默认 redacted。
- adapter/backend registry contract。
- platform simulation harness。
- conformance certification format。
- platform-ready release manifest。

## 不支持 / 不承诺

- 不自带 hosted SaaS。
- 不自带 hosted control plane。
- 不自带 enterprise console。
- 不自带 RBAC UI。
- 不声称 sandbox 绝对不可逃逸。
- 不把 remote executor 声明为 stable。
- 不把 weak subprocess 用于高风险生产写操作。
- 不自动启用 optional adapter/backend pack。

## 快速开始

首次克隆后推荐使用 editable install：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
PYTHONPATH=src python -m pytest tests/e2e -q
python examples/minimal_agent.py
```

运行 real-agent 测试：

```bash
python -m pytest tests/test_real_agent_scenarios.py tests/test_provider_real_agent.py -q
```

真实 GLM/Z.AI provider integration 默认跳过。不要把 API key 写入可提交文件；如需本地验证，可以复制 `.env.example` 到 ignored `.env` 并填入轮换后的 key：

```bash
cp .env.example .env
python -m pytest tests/test_provider_real_agent.py::test_glm_provider_agent_can_call_real_provider_when_key_is_configured -q
```

只验证 CLI 初始化和配置校验：

```bash
agent-runtime init --path agent-runtime.json
agent-runtime validate --path agent-runtime.json
```

生成和校验起始配置：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main init --path agent-runtime.json
PYTHONPATH=src python -m agent_runtime.cli.main validate --path agent-runtime.json
```

查看 release manifest：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main release status
```

## Certification / Evidence

生成 platform-ready certification report：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main certify run --subject all
```

采集 container sandbox runtime evidence：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main sandbox evidence --backend container
```

运行 Docker smoke evidence：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main sandbox evidence --backend container --run-smoke --image busybox:latest
```

注意：Docker smoke 只证明当前环境可以执行 no-network/read-only/cap-drop smoke，不证明绝对逃逸防护。

运行 adapter replay：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main adapter replay --scenario code-ci --adapter openai --adapter langgraph --adapter codex
```

运行 adapter conformance：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main adapter conformance --adapter all --dry-run
```

运行 sandbox conformance：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend container --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend docker --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend sidecar --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend remote --dry-run
```

运行 platform simulation：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main platform simulate --scenario all
```

## Audit / Policy / Observer

查看 audit：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main audit tail --path .agent-runtime/audit.jsonl
```

查询 SQLite audit：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main audit query --path .agent-runtime/audit.db --run-id <run_id>
```

验证 audit hash chain：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main audit verify --path .agent-runtime/audit.jsonl --sink jsonl
PYTHONPATH=src python -m agent_runtime.cli.main audit verify --path .agent-runtime/staging-pilot/pilot-audit.db --sink sqlite
```

导出 policy config schema：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main schema export --type policy-config --output policy-config.schema.json
```

调试 policy：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main policy debug --path agent-runtime.json --tool <tool> --environment prod
```

查看 observer：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main observe status --path .agent-runtime/observer.json
```

生成单次 run 的完整运行过程 HTML：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main run view \
  --audit .agent-runtime/run-screenshots/real-provider-agent-run-audit.jsonl \
  --snapshot .agent-runtime/run-screenshots/real-provider-agent-run.json \
  --output .agent-runtime/run-screenshots/real-provider-agent-run-view.html
```

该页面会展示 input、agent decision、runtime governance、execution timeline、tool calls、trace tree 和 raw evidence。

## Examples

最小 agent：

```bash
PYTHONPATH=src python examples/minimal_agent.py
```

OpenAI-style adapter 示例：

```bash
PYTHONPATH=src python examples/openai_style_adapter.py
```

完整 runtime report，包含复杂 `ProductionIncidentAgent` 场景：

```bash
PYTHONPATH=src python examples/complete_runtime_report.py
PYTHONPATH=src python -m agent_runtime.cli.main run view \
  --audit .agent-runtime/complete-report/production_incident-audit.jsonl \
  --report .agent-runtime/complete-report/complete-report.json \
  --scenario production_incident \
  --output .agent-runtime/complete-report/production-incident-run-view.html
```

同一个 `ProductionIncidentAgent` 的未注册 direct execution 和 registered runtime execution 对比：

```bash
PYTHONPATH=src python examples/production_incident_comparison.py
open .agent-runtime/production-incident-comparison/registered-run-view.html
```

运行后会生成：

- `.agent-runtime/production-incident-comparison/comparison.json`
- `.agent-runtime/production-incident-comparison/registered-audit.jsonl`
- `.agent-runtime/production-incident-comparison/registered-run-view.html`

其中 direct 路径直接调用本地工具，不产生 audit/trace；registered 路径会进入 policy、approval、sandbox、audit 和 trace，并拒绝未授权 `apply_hotfix`。

staging internal admin pilot：

```bash
PYTHONPATH=src python examples/staging_internal_admin_pilot.py
PYTHONPATH=src python -m agent_runtime.cli.main audit query --path .agent-runtime/staging-pilot/pilot-audit.db --tool-name read_customer
PYTHONPATH=src python -m agent_runtime.cli.main audit verify --path .agent-runtime/staging-pilot/pilot-audit.db --sink sqlite
```

命令行示例会重置 `.agent-runtime/staging-pilot/` 下由示例生成的 audit、observer 和 report 文件，确保 smoke test 不被旧格式本地审计污染。作为库函数调用 `run_pilot(work_dir)` 时默认不清理已有文件；需要可重复 demo 时显式传入 `reset=True`。

## Support Matrix

| Level | Items |
| --- | --- |
| supported | core runtime contracts、policy config schema v1、approval provider interface、audit sink contract、observer metrics、adapter/sandbox conformance contracts |
| stable candidate | OpenAI adapter、Anthropic adapter、LangGraph adapter、MCP adapter、Codex workspace adapter、container plan backend contract、control plane API |
| preview | Codex workflow、platform integration contracts、sidecar backend、Docker sandbox backend |
| experimental | Codex connectors、OpenTelemetry sink、HTTP API tool、`agent_runtime.testing` reference agents |
| beta | remote executor |
| unsupported | hosted SaaS、hosted control plane、enterprise console、RBAC UI、absolute sandbox escape prevention |

## Security Boundary

`require_approval` 没有显式 approval provider 时默认 reject，不会静默批准。测试或 demo 如需自动批准，必须显式注入 `StaticApprovalProvider(approved=True, ...)`。

subprocess executor 不是强安全沙箱。它只提供独立进程、cwd、env allowlist、timeout、stdout/stderr 捕获和输出截断。

注册 agent 后，metadata capabilities 和 runtime profile 会参与执行拦截：未声明能力、超过 `max_tool_calls`、违反高风险 tool 的 sandbox / approval profile 都会被拒绝。注册路径不接受 direct tool fallback。

高风险 prod command tool 必须使用 `sandboxed_command_tool` 和宿主注入的强隔离 sandbox backend；backend 不可用时 runtime 返回 `sandbox.unavailable`，不会退回普通 subprocess。当前 contrib `ContainerSandboxBackend` 是 container execution plan simulation，用于验证 contract 和 abuse checks；`DockerSandboxBackend` 是显式 opt-in 的真实 Docker execution preview，默认 no-network、read-only、cap-drop ALL、no-new-privileges、资源限制和 env allowlist。secret-like env key 即使被误放进 allowlist，也会在普通 subprocess、runtime / sandbox plan 层被拒绝，backend 不会收到该 env。`SidecarSandboxBackend` 会先构建裁剪后的 sandbox execution plan，再传给 sidecar client。它仍依赖宿主 Docker/sidecar 安全基线，不声明绝对 escape prevention。

JSONL / SQLite audit sink 会写入 `event_hash` 和 `previous_event_hash`，用于检测本地审计链篡改。JSONL sink 会用本地 advisory file lock 串行化单节点写入，SQLite sink 会用写事务串行化本地并发写入，避免并发写破坏 hash chain。可以用 `agent-runtime audit verify` 验证链完整性。它不是分布式锁、外部 WORM 或合规归档；需要更强追责时应接入宿主的 append-only sink。

## Design Partner Pilot

当前推荐使用方式是 design partner pilot，而不是公开大规模发布。

建议 pilot 场景：

- Code/CI agent：读 repo、跑 allowlisted command、产出 diff，不 commit/push。
- Ops diagnostic agent：只读系统状态，所有命令经 policy/audit。
- Internal automation agent：受限写入目录，sandbox backend 明确。

进入 pilot 前建议至少执行：

```bash
python -m pytest
python -m pyright src
python -m ruff check .
PYTHONPATH=src python -m agent_runtime.cli.main certify run --subject all
PYTHONPATH=src python -m agent_runtime.cli.main sandbox evidence --backend container --run-smoke --image busybox:latest
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend docker --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main adapter replay --scenario code-ci --adapter openai --adapter langgraph --adapter codex
```
