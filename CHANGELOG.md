# Changelog

本项目遵循面向公开读者的变更记录。当前尚未发布正式稳定版本；`main` 处于 **Technical Preview**，下一门禁是 **Design Partner Pilot**。

## Unreleased

- 补充 Apache-2.0 `LICENSE`、`CODE_OF_CONDUCT.md`、GitHub Actions CI 和 pull request template，提升 public repo readiness。
- `pyproject.toml` 改为 `0.1.0` technical preview package version，并补充 readme、license、classifiers、keywords、authors 和 `dev` extra。
- `require_approval` 缺少显式 approval provider 时默认 reject，避免静默批准高风险操作。
- sandboxed command 的 env 会在进入 sandbox backend 前按 `env_allowlist` 裁剪，避免 backend 接触未授权 secret。
- JSONL audit sink 增加本地 advisory file lock，串行化单节点写入，避免并发写破坏 hash chain。
- `ContainerSandboxBackend` 明确为 `container-plan-simulation`，conformance limitations 标出不执行真实 Docker container，降低开源用户误解风险。
- 新增显式 opt-in 的 `DockerSandboxBackend` preview，使用本地 Docker daemon 执行 no-network/read-only/cap-drop command，并纳入 sandbox conformance。
- CI 增加 `ruff check`、`pyright src`、distribution build/twine/sdist content check、certification、adapter replay 和 sandbox conformance，并新增 bug、feature、design partner feedback 和 security boundary issue templates。
- 新增 `ROADMAP.md`，区分 Python package `0.x` 版本和内部 runtime contract gate。
- 新增 `docs/release/release-checklist.md`、`docs/reports/staging-validation-report.md` 和 `docs/reference/adapter-payload-fixtures.md`，补齐 release、staging surrogate validation 和 provider payload fixture 证据。
- 新增 OpenAI、Anthropic、LangGraph、MCP、Codex adapter payload fixture 回归测试，避免 adapter 只覆盖理想化 sample payload。
- 新增 `docs/test/e2e-test-plan.md`、`docs/reports/e2e-test-report.md` 和 `tests/e2e/`，覆盖 clean wheel install、production incident run view、Docker sandbox runtime、complete report fake provider、Docker sandbox failure paths、run view browser evidence 和真实 provider 手工门禁。
- 新增 E2E 扩展 OPT 产物，覆盖 P0/P1/P2 spec、架构、交互、安全门禁、QA plan 和实现计划。
- 新增 Runtime Core API 稳定化 OPT 产物，定义通用 agent execution session contract。
- 新增 `AgentRunRequest` / `AgentRunResult`、`RegisteredAgent.run_session(...)` 和 `AgentRuntime.run_agent(...)`，支持任意 Python agent 输出包装为统一、可审计、可追踪的运行结果，同时保持旧 `run(...)` 兼容。
- 强化 runtime 安全边界：tool-specific deny 覆盖 broad capability allow，registered agent metadata capabilities 和 runtime profile 参与执行拦截，注册路径移除 direct tool fallback，complete report / screenshot HTML 转义动态值，Docker backend 避免 env value 进入 argv 并拒绝 secret-like allowlisted env key，SQLite audit 本地并发写使用事务保持 hash chain。
- 继续强化 review follow-up：runtime 在调用 sandbox backend 前拒绝 secret-like sandbox env，sidecar backend 先构建 sanitized sandbox execution plan，execution error path 遵守 audit fail-closed，并新增 approval matrix / concurrent runtime audit E2E。
- 更新 README、CONTRIBUTING、SECURITY、docs/user-guide、docs/reports/test-report 和 docs/runbooks/design-partner-runbook，修复 fresh setup、测试证据和安全边界说明漂移。
- 整理公开文档信息架构：根目录仅保留开源入口文档，报告、runbook、reference、release checklist 和 E2E plan 归入 `docs/`，并新增 `docs/README.md` 索引。
- 新增 `MANIFEST.in`，发布 sdist 时排除 `tests/`、`.github/`、`docs/` 和 `roles/`，避免源码包混入内部验证材料。
- 拆分 open-source 维护性边界：`RegisteredAgent` session 逻辑移入 `agent_runtime.core.agent_session`，complete report 实现移入 `agent_runtime.reporting.complete_report`，`examples/complete_runtime_report.py` 保持薄入口。

## Technical Preview

### Platform-Ready Runtime Contracts

新增：

- `agent-runtime certify run --subject all`。
- conformance certification format。
- platform-ready release manifest。
- platform support matrix v2。
- policy bundle validation contract。
- audit forwarding contract。
- run export contract，默认 redacted。
- adapter/backend registry contract。
- platform simulation harness。

调整：

- 对外状态明确为 `technical_preview`。
- 下一门禁明确为 `design_partner_pilot`。
- `public_launch_ready=false`。
- 明确不是 hosted SaaS，也不是 hosted enterprise platform。
- `sidecar_backend` 保持 preview，不列入 stable candidate。
- `remote_executor` 保持 contract beta，不列入 stable candidate。

### Adapter / Contrib / Sandbox Preview

新增：

- `agent_runtime_contrib` package shell。
- pack registry，默认 disabled，必须 explicit allowlist。
- OpenAI adapter stable candidate。
- Anthropic adapter stable candidate。
- LangGraph adapter stable candidate。
- MCP adapter stable candidate。
- Codex workspace adapter stable candidate。
- adapter conformance。
- adapter replay。
- container plan backend stable candidate contract。
- sidecar backend preview contract。
- remote executor contract beta。
- sandbox conformance。
- Docker runtime evidence command。
- Code/CI reference pilot。

安全边界：

- adapter 只翻译 provider/tool-call shape，不授予 capability。
- optional pack 不自动启用。
- container Docker smoke 不证明绝对逃逸防护。
- weak subprocess 不用于高风险生产写操作。

### Production Core

已有能力：

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

安全默认值：

- unknown tool 默认 deny。
- unknown capability 默认 deny。
- policy hook exception 默认 deny。
- approval timeout 默认 reject。
- prod audit write failure 默认 fail closed。
- raw payload storage 默认 disabled。
- subprocess environment 使用 allowlist。
