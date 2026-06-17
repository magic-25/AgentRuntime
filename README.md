# Agent Runtime

Agent Runtime 是一个面向生产 agent 工具调用的 Python runtime。它把工具调用放进统一链路：

```text
ToolCall -> Context Filter -> Policy Engine -> Approval Gate -> Executor -> Result Filter -> Audit
```

当前公开状态：**Technical Preview**。  
下一门禁：**Design Partner Pilot**。

这不是 public launch，也不是 hosted enterprise platform。当前重点是把 runtime contracts、policy/audit/sandbox、adapter、conformance certification 和 platform-ready manifest 做到可验证，供少量 design partner 在真实场景中试点。

## 项目文档

- [用户指南：场景与概念](USER_GUIDE.md)
- [测试报告](TEST_REPORT.md)
- [场景测试报告](SCENARIO_TEST_REPORT.md)
- [Real Agent 测试报告](REAL_AGENT_TEST_REPORT.md)
- [Provider Agent Runtime 对比测试报告](PROVIDER_RUNTIME_COMPARISON_REPORT.md)
- [开源 Agent 采用评估](OPEN_SOURCE_AGENT_EVALUATION.md)
- [贡献指南](CONTRIBUTING.md)
- [安全策略](SECURITY.md)
- [变更记录](CHANGELOG.md)

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

### Contrib / Adapter / Sandbox Preview

- `agent_runtime_contrib` package shell。
- pack registry，默认 disabled，必须 explicit allowlist。
- OpenAI、Anthropic、LangGraph、MCP、Codex workspace adapter stable candidate。
- adapter conformance 和 replay。
- container backend stable candidate contract。
- sidecar backend preview。
- remote executor contract beta。
- sandbox conformance 和 Docker runtime evidence。
- Code/CI reference pilot。
- GLM/OpenAI-compatible provider agent optional integration test。
- agent registration lifecycle comparison test。

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

源码模式：

```bash
python -m pytest
PYTHONPATH=src python examples/minimal_agent.py
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

editable install 模式：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
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

## Examples

最小 agent：

```bash
PYTHONPATH=src python examples/minimal_agent.py
```

OpenAI-style adapter 示例：

```bash
PYTHONPATH=src python examples/openai_style_adapter.py
```

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
| stable candidate | OpenAI adapter、Anthropic adapter、LangGraph adapter、MCP adapter、Codex workspace adapter、container backend、control plane API |
| preview | Codex workflow、platform integration contracts、sidecar backend |
| experimental | Codex connectors、OpenTelemetry sink、HTTP API tool |
| beta | remote executor |
| unsupported | hosted SaaS、hosted control plane、enterprise console、RBAC UI、absolute sandbox escape prevention |

## Security Boundary

subprocess executor 不是强安全沙箱。它只提供独立进程、cwd、env allowlist、timeout、stdout/stderr 捕获和输出截断。

高风险 prod command tool 必须使用 `sandboxed_command_tool` 和宿主注入的强隔离 sandbox backend；backend 不可用时 runtime 返回 `sandbox.unavailable`，不会退回普通 subprocess。

JSONL / SQLite audit sink 会写入 `event_hash` 和 `previous_event_hash`，用于检测本地审计链篡改。可以用 `agent-runtime audit verify` 验证链完整性。它不是外部 WORM/合规归档；需要更强追责时应接入宿主的 append-only sink。

## Design Partner Pilot

当前推荐使用方式是 design partner pilot，而不是公开大规模发布。

建议 pilot 场景：

- Code/CI agent：读 repo、跑 allowlisted command、产出 diff，不 commit/push。
- Ops diagnostic agent：只读系统状态，所有命令经 policy/audit。
- Internal automation agent：受限写入目录，sandbox backend 明确。

进入 pilot 前建议至少执行：

```bash
python -m pytest
PYTHONPATH=src python -m agent_runtime.cli.main certify run --subject all
PYTHONPATH=src python -m agent_runtime.cli.main sandbox evidence --backend container --run-smoke --image busybox:latest
PYTHONPATH=src python -m agent_runtime.cli.main adapter replay --scenario code-ci --adapter openai --adapter langgraph --adapter codex
```
