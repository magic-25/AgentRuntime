# E2E Test Plan

本计划把 Agent Runtime 的端到端测试分成自动化 E2E 和 manual E2E。默认 CI 只运行不需要密钥、不依赖外部 provider、不强制 Docker daemon 的路径。

## Coverage Matrix

| ID | Path | Entry | External dependency | CI status | Purpose |
| --- | --- | --- | --- | --- | --- |
| E2E-001 | clean wheel install | `tests/e2e/test_clean_wheel_install.py` | none | automated | 从 wheel artifact 安装到干净 venv，再跑 CLI smoke。 |
| E2E-002 | production incident run view | `tests/e2e/test_production_incident_run_view_e2e.py` | none | automated | 从 example 入口跑复杂 agent，对比 direct vs registered runtime，并验证 audit/run view artifact。 |
| E2E-003 | Docker sandbox runtime | `tests/e2e/test_docker_sandbox_runtime_e2e.py` | local Docker daemon | automated skip if unavailable | 注册 sandboxed command tool，使用 `DockerSandboxBackend` 真实执行，再验证 audit 和 trace。 |
| E2E-004 | complete report fake provider | `tests/e2e/test_complete_report_e2e.py` | none | automated | 从 complete report example 生成 JSON/Markdown/HTML/PNG，并验证 production incident scenario。 |
| E2E-MANUAL-001 | complete report real provider key | manual command | `GLM_API_KEY` or `ZAI_API_KEY` | manual only | 使用真实 provider key 生成完整报告，确认 key 不进入 artifact。 |

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

## E2E-MANUAL-001 complete report real provider key

命令：

```bash
cp .env.example .env
# 在 .env 中填写轮换后的 GLM_API_KEY 或 ZAI_API_KEY
PYTHONPATH=src python examples/complete_runtime_report.py
```

验收：

- `summary.provider_mode == "real"`。
- provider scenario 成功生成 tool result。
- artifact 不包含 API key。
- `.env` 不提交。
- 生成的 HTML/PNG 能人工打开查看。

## Known Gaps

- 自动 CI 不调用真实 provider。
- 自动 CI 不强制 Docker daemon 存在。
- 当前没有 browser rendering pixel test；HTML 只验证内容和 artifact 生成。
- 外部 design partner 仍需用真实 staging service 复跑 `DESIGN_PARTNER_RUNBOOK.md`。
