# E2E Test Plan

本计划把 Agent Runtime 的端到端测试分成自动化 E2E、optional local E2E 和 manual E2E。默认 CI 只运行不需要密钥、不依赖外部 provider、不强制 Docker daemon 的路径。

扩展 spec：[docs/superpowers/specs/2026-06-21-e2e-expansion-spec.md](/docs/superpowers/specs/2026-06-21-e2e-expansion-spec.md)

## Coverage Matrix

| ID | Path | Entry | External dependency | CI status | Purpose |
| --- | --- | --- | --- | --- | --- |
| E2E-001 | clean wheel install | `tests/e2e/test_clean_wheel_install.py` | none | automated | 从 wheel artifact 安装到干净 venv，再跑 CLI smoke。 |
| E2E-002 | production incident run view | `tests/e2e/test_production_incident_run_view_e2e.py` | none | automated | 从 example 入口跑复杂 agent，对比 direct vs registered runtime，并验证 audit/run view artifact。 |
| E2E-003 | Docker sandbox runtime | `tests/e2e/test_docker_sandbox_runtime_e2e.py` | local Docker daemon | automated skip if unavailable | 注册 sandboxed command tool，使用 `DockerSandboxBackend` 真实执行，再验证 audit 和 trace。 |
| E2E-004 | complete report fake provider | `tests/e2e/test_complete_report_e2e.py` | none | automated | 从 complete report example 生成 JSON/Markdown/HTML/PNG，并验证 production incident scenario。 |
| E2E-005 | Docker sandbox failure paths | `tests/e2e/test_docker_sandbox_failure_paths_e2e.py` | local Docker daemon | automated skip if unavailable | 验证 no-network、read-only workspace、env allowlist 和 timeout 的受治理失败路径。 |
| E2E-006 | run view browser evidence | `tests/e2e/test_run_view_browser_evidence_e2e.py` | none | automated | 生成 complete report 和 run view HTML，验证浏览器可见证据区域、JSON beauty view 和截图 artifact。 |
| E2E-007 | runtime governance matrix | `tests/e2e/test_runtime_governance_matrix_e2e.py` | none | automated | 验证 approval approve/reject/timeout、并发 SQLite runtime audit hash chain 和 registered agent context isolation。 |
| E2E-MANUAL-001 | complete report real provider key | manual command | `GLM_API_KEY` or `ZAI_API_KEY` | manual only | 使用真实 provider key 生成完整报告，确认 key 不进入 artifact。 |

## P0 / P1 / P2 Backlog

| Priority | Requirement | E2E ID | Status | Evidence |
| --- | --- | --- | --- | --- |
| P0 | REQ-E2E-X-001 P0/P1/P2 backlog 和 readiness guard | E2E readiness | implemented | `tests/test_e2e_readiness.py` |
| P0 | REQ-E2E-X-003 真实 provider registered runtime execution | E2E-MANUAL-001 | manual gate | `examples/complete_runtime_report.py` with `provider_mode=real` |
| P0 | REQ-E2E-X-004 direct vs registered runtime comparison | E2E-002 | implemented | production incident comparison |
| P0 | REQ-E2E-X-005 registered deny no direct fallback | E2E-002 | implemented | `registered_deny_no_direct_fallback` assertion |
| P0 | REQ-E2E-X-006 Docker sandbox failure paths | E2E-005 | implemented | no-network、read-only、env allowlist、timeout |
| P0 | REQ-E2E-X-007 run view / complete report browser evidence | E2E-006 | implemented | HTML evidence sections and PNG artifact |
| P0 | REQ-E2E-X-008 secret boundary | E2E-MANUAL-001 plus scan | manual/automated | `.env` ignored and secret scan command |
| P1 | REQ-E2E-X-009 OpenAI、Anthropic、LangGraph、MCP、Codex adapter/framework runtime E2E | planned | planned | 保持 optional，不进入 core runtime |
| P1 | REQ-E2E-X-010 approval provider approve/reject/timeout E2E | E2E-007 | implemented | approval matrix |
| P1 | REQ-E2E-X-011 concurrent audit/trace/observer E2E | E2E-007 | implemented | concurrent SQLite runtime audit chain and registered agent context isolation |
| P2 | REQ-E2E-X-012 sidecar、remote executor、staging/design partner、long-running recovery | deferred | deferred/manual | 需要真实或本地服务门禁 |

## E2E-001 clean wheel install

目标：证明 release artifact 可以安装，并且 CLI entry point 可用。

验证点：

- `python -m build --wheel` 生成 wheel。
- 新建临时 venv。
- 从 wheel 安装。
- 运行 `agent-runtime --help`。
- 运行 `agent-runtime init` 和 `agent-runtime validate`。

## E2E-002 production incident run view

目标：证明复杂生产级 agent 的用户入口能完整产出治理证据。

验证点：

- direct execution 会直接 apply hotfix。
- registered runtime execution 会拒绝 hotfix。
- registered path 产生 audit JSONL。
- registered path 产生 run view HTML。
- run view HTML 包含 prompt、policy、sandbox、trace tree 和 raw evidence。

## E2E-003 Docker sandbox runtime

目标：证明 runtime 可以把 sandboxed command tool 交给真实 Docker backend 执行。

验证点：

- Docker daemon 不可用时 skip，不误报失败。
- tool call 经过 policy。
- tool call 进入 `DockerSandboxBackend`。
- stdout 返回容器内命令输出。
- audit 包含 `SandboxEnforced` 和 trace events。

## E2E-004 complete report fake provider

目标：证明 complete report 的可视化 artifact 生成路径可在 CI 中稳定运行。

验证点：

- 使用 fake provider mode。
- 生成 `complete-report.json`、`complete-report.md`、`complete-report.html`、`complete-report.png`。
- report 至少包含 6 个 scenario。
- production incident scenario 包含 deny、approval、sandbox、audit/trace summary。

## E2E-005 Docker sandbox failure paths

目标：证明 Docker sandbox E2E 不只覆盖 happy path，也覆盖关键失败路径。

验证点：

- `network_access=True` 在进入 Docker 前被 runtime/sandbox plan 拒绝，并以 runtime-level denied result 暴露。
- 只读 workspace 下写 `/workspace/blocked.txt` 失败，且不会在宿主目录留下文件。
- `env_allowlist` 只允许指定变量进入容器，secret env 不进入 stdout 或 audit。
- timeout command 返回 `exit_code=124` 和 `docker.timeout`。
- audit 包含 `SandboxEnforced` 和 trace events。

## E2E-006 run view browser evidence

目标：证明 run view / complete report 的 HTML 不是空壳 artifact，而是包含人工可审查的完整运行过程证据。

验证点：

- 使用 fake provider 生成 complete report，保证 CI 稳定。
- 生成 production incident run view HTML。
- HTML 包含 agent 说明、prompt/agent report、runtime governance、timeline、tool calls、trace tree、raw evidence 和 JSON beauty view。
- complete report HTML 包含 provider、policy deny、sandboxed command 等多个 agent scenario。
- PNG screenshot artifact 存在且非空；P0 不做浏览器像素级 CI 断言。

## E2E-007 runtime governance matrix

目标：证明 runtime governance 的关键矩阵不只在 unit test 中存在，也能作为端到端 smoke 路径稳定运行。

验证点：

- approval provider approve 路径会执行工具并记录 observer approval request。
- approval provider reject 路径返回 `status=rejected`。
- approval timeout 路径返回 `approval.timeout`，observer 记录 timeout。
- 并发 runtime tool calls 写入 SQLite audit 后，hash chain 仍可验证。
- 同一个 runtime 上并发运行 registered agents 时，agent identity、declared capabilities、trace context 和 session audit events 不串线。

## E2E-MANUAL-001 complete report real provider key

命令：

```bash
cp .env.example .env
# 在 .env 中填写轮换后的 GLM_API_KEY 或 ZAI_API_KEY
PYTHONPATH=src python examples/complete_runtime_report.py
```

验收：

- `summary.provider_mode == "real"`。
- provider scenario 通过 `runtime.register_agent(...)` 注册到 Agent Runtime 后成功生成 tool result。
- artifact 不包含 API key。
- `.env` 不提交。
- 生成的 HTML/PNG 能人工打开查看。

Secret scan：

```bash
rg -n "(api[_-]?key|apikey|secret|token|password|sk-[A-Za-z0-9]|[A-Za-z0-9]{32,}\\.[A-Za-z0-9]{10,})" .agent-runtime/complete-report
```

该命令可以命中字段名或说明文字，但不能命中真实 key 值。

## Known Gaps

- 自动 CI 不调用真实 provider。
- 自动 CI 不强制 Docker daemon 存在。
- 当前没有 browser rendering pixel test；HTML 只验证内容和 artifact 生成。
- 外部 design partner 仍需用真实 staging service 复跑 `docs/runbooks/design-partner-runbook.md`。
- P1 adapter/framework E2E 已列入 backlog，尚未 verified。
- P2 sidecar、remote executor、staging 和长任务恢复仍是 deferred/manual。
