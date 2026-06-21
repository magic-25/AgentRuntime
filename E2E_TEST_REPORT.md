# Agent Runtime E2E 测试报告

报告日期：2026-06-21  
报告状态：公开测试报告  
产品状态：Technical Preview  
对应计划：[E2E_TEST_PLAN.md](E2E_TEST_PLAN.md)

## 结论摘要

本轮 E2E 结论：自动化 E2E smoke、E2E readiness 和完整回归套件均通过。

核心证据：

- E2E 自动化集合：`6 passed in 6.47s`
- 全量回归集合：`201 passed in 34.08s`
- GitHub Actions：`main` 分支 commit `d379c9c` 通过 CI

本报告覆盖五类端到端路径：

| ID | 路径 | 状态 | 外部依赖 |
| --- | --- | --- | --- |
| E2E-001 | clean wheel install | 通过 | 无 |
| E2E-002 | production incident run view | 通过 | 无 |
| E2E-003 | Docker sandbox runtime | 通过 | 本地 Docker daemon |
| E2E-004 | complete report fake provider | 通过 | 无 |
| E2E-MANUAL-001 | complete report real provider key | 手工门禁 | `GLM_API_KEY` 或 `ZAI_API_KEY` |

## 测试环境

| 项目 | 值 |
| --- | --- |
| 工作目录 | Agent Runtime 仓库根目录 |
| 日期 | 2026-06-21 |
| Python | 3.12.9 |
| pytest | 9.0.2 |
| Docker client | `Docker version 28.0.1, build 068a01e` |
| Docker server | `28.0.1` |
| 密钥策略 | `.env` 被忽略，不提交真实 API key |

说明：E2E 测试中生成的临时文件和报告 artifact 使用测试临时目录或 `.agent-runtime/` 下的本地产物，不作为仓库提交内容。

## 需求到测试追踪

| Requirement ID | 要求 | Product or design decision | Architecture or contract decision | Implementation area | Test coverage | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-E2E-001 | Python package artifact 必须可以从 wheel 干净安装 | 使用 technical preview package version | CLI entry point 必须随 wheel 可用 | `pyproject.toml`、CLI package entry | E2E-001 | clean wheel install output | verified |
| REQ-E2E-002 | 复杂 agent 在 runtime 中运行时必须能产出可审计运行视图 | production incident agent 作为复杂代理场景 | direct execution 与 registered runtime execution 可比较 | `examples/production_incident_comparison.py`、`src/agent_runtime/run_view.py` | E2E-002 | run view HTML 和 audit JSONL | verified |
| REQ-E2E-003 | sandboxed command tool 必须能进入真实 Docker backend | Docker backend 是显式 opt-in preview | policy、sandbox、audit、trace 必须在同一路径中联动 | `DockerSandboxBackend`、runtime tool execution | E2E-003 | Docker stdout、audit、trace | verified |
| REQ-E2E-004 | complete runtime report 必须能稳定生成多格式 artifact | fake provider mode 用于 CI 稳定性 | report 需要包含 scenario、治理摘要、trace 和 audit | `examples/complete_runtime_report.py` | E2E-004 | JSON、Markdown、HTML、PNG | verified |
| REQ-E2E-005 | E2E coverage 必须有文档和 readiness gate | E2E 计划与测试文件要同步 | readiness test 阻止计划和文件漂移 | `E2E_TEST_PLAN.md`、`tests/test_e2e_readiness.py` | Readiness | readiness output | verified |
| REQ-E2E-006 | 真实 provider key 路径必须可人工复跑且不能泄漏密钥 | 真实调用只作为 manual gate | `.env` ignored，artifact 不得包含 key | `.env.example`、complete report runner | E2E-MANUAL-001 | manual command | manual gate |

## 自动化 E2E 集合

**命令**

```bash
PYTHONPATH=src python -m pytest tests/e2e tests/test_e2e_readiness.py -q
```

**输出结果**

```text
......                                                                   [100%]
6 passed in 6.47s
```

**输出解释**

`6 passed` 表示四条自动化 E2E path 和两个 readiness 检查全部通过。它证明当前仓库可以完成 clean wheel install、复杂 agent run view、Docker sandbox runtime、complete report fake provider，以及 E2E 计划和测试文件的基本一致性检查。

**结论**

通过。

## E2E-001 Clean Wheel Install

**用例设计**

该用例模拟开源用户从构建出的 wheel artifact 安装 Agent Runtime，而不是直接依赖仓库源码路径。测试流程会构建 wheel、新建临时 virtualenv、安装 wheel、执行 CLI help、生成默认配置，并运行配置校验。

**命令**

```bash
PYTHONPATH=src python -m pytest tests/e2e/test_clean_wheel_install.py -q
```

**输出结果**

```text
.                                                                        [100%]
1 passed in 6.42s
```

**输出解释**

`1 passed` 表示 wheel 可以成功构建和安装，且安装后的 CLI 入口可以执行 `--help`、`init` 和 `validate`。这覆盖的是本地 artifact 安装链路，不等同于 PyPI 发布验证。

**结论**

通过。

## E2E-002 Production Incident Run View

**用例设计**

该用例使用 production incident agent 作为复杂测试对象。它会比较同一个 agent 在未注册 direct execution 和 registered runtime execution 下的行为差异，并检查 runtime 运行后产生的治理证据。

验证点包括：

- direct execution 会直接 apply hotfix。
- registered runtime execution 会在 policy deny 时拒绝 hotfix。
- registered path 会产生 audit JSONL。
- registered path 会生成 run view HTML。
- HTML 中包含 agent 说明、prompt、policy、sandbox、trace tree 和 raw evidence。

**命令**

```bash
PYTHONPATH=src python -m pytest tests/e2e/test_production_incident_run_view_e2e.py -q
```

**输出结果**

```text
.                                                                        [100%]
1 passed in 0.08s
```

**输出解释**

`1 passed` 表示复杂 agent 的 direct vs registered 对比路径可跑通，并且 registered runtime path 没有在 policy deny 后回落到 direct execution。生成的 HTML run view 可以用于人工查看 agent 做了什么、为什么允许或拒绝、是否经过 sandbox、是否有 audit 和 trace。

**结论**

通过。

## E2E-003 Docker Sandbox Runtime

**用例设计**

该用例验证真实 Docker sandbox backend，而不是 container plan simulation。测试会注册一个 sandboxed command tool，让 runtime 经过 policy 评估后把命令交给 `DockerSandboxBackend` 执行，并检查 stdout、audit event 和 trace span。

验证点包括：

- Docker daemon 不可用时测试会 skip，不把环境不可用误报为功能失败。
- tool call 必须经过 policy。
- tool call 必须进入 `DockerSandboxBackend`。
- stdout 必须返回容器内命令输出。
- audit 必须包含 sandbox enforcement 证据。
- trace 必须记录 tool call 开始和结束。

**命令**

```bash
PYTHONPATH=src python -m pytest tests/e2e/test_docker_sandbox_runtime_e2e.py -q
```

**输出结果**

```text
.                                                                        [100%]
1 passed in 0.78s
```

**输出解释**

`1 passed` 表示当前本地 Docker 环境可用，并且 runtime 可以把 sandboxed command tool 放入真实 Docker backend 执行。该结果证明 runtime 与 Docker backend 的端到端集成可用，但不证明绝对 sandbox escape prevention。

**结论**

通过。

## E2E-004 Complete Report Fake Provider

**用例设计**

该用例使用 fake provider mode 运行 complete runtime report runner，用于 CI 中稳定验证完整体验报告的 artifact 生成路径。fake provider 不依赖外部网络或真实 API key，但仍会覆盖 provider-style tool call、policy deny、approval gate、sandboxed command 和 production incident scenario。

验证点包括：

- `provider_mode == "fake"`。
- 至少生成 6 个 scenario。
- 生成 `complete-report.json`、`complete-report.md`、`complete-report.html` 和 `complete-report.png`。
- production incident scenario 包含 deny、approval、sandbox、audit 和 trace summary。
- JSON 内容可以被后续 viewer 和人工审查使用。

**命令**

```bash
PYTHONPATH=src python -m pytest tests/e2e/test_complete_report_e2e.py -q
```

**输出结果**

```text
.                                                                        [100%]
1 passed in 0.23s
```

**输出解释**

`1 passed` 表示 complete report 的多 artifact 生成路径稳定可跑。该测试覆盖的是 fake provider 模式，适合 CI；真实 provider 的端到端体验仍由手工门禁覆盖。

**结论**

通过。

## E2E Readiness

**用例设计**

该用例检查 E2E 测试计划和测试文件是否同步，避免文档写了 E2E path 但仓库中没有对应测试文件，或新增测试后计划没有更新。

**命令**

```bash
PYTHONPATH=src python -m pytest tests/test_e2e_readiness.py -q
```

**输出结果**

```text
..                                                                       [100%]
2 passed in 0.01s
```

**输出解释**

`2 passed` 表示 `E2E_TEST_PLAN.md` 中声明的自动化和手工 E2E path 存在，且自动化测试入口文件可找到。

**结论**

通过。

## E2E-MANUAL-001 Complete Report Real Provider Key

**用例设计**

该手工门禁用于验证用户使用真实 provider key 运行 complete runtime report 的体验。它回答的问题是：真实 agent provider 在 Agent Runtime 中运行时，是否能生成完整 output、治理证据、trace、audit 和可视化报告。

测试 agent 包括：

- scripted echo agent：验证最小 runtime 路径。
- provider-style tool calling agent：验证 provider tool call shape。
- policy deny agent：验证拒绝路径和解释。
- approval gate agent：验证 approval gate。
- sandboxed command agent：验证 sandbox summary。
- production incident agent：验证复杂生产事故处置路径。

**命令**

```bash
cp .env.example .env
# 在 .env 中填写轮换后的 GLM_API_KEY 或 ZAI_API_KEY
PYTHONPATH=src python examples/complete_runtime_report.py
```

**期望输出**

```text
.agent-runtime/complete-report/complete-report.json
.agent-runtime/complete-report/complete-report.md
.agent-runtime/complete-report/complete-report.html
.agent-runtime/complete-report/complete-report.png
```

**输出解释**

手工通过标准：

- `summary.provider_mode == "real"`。
- provider scenario 成功生成 tool result。
- artifact 中不包含 API key。
- `.env` 未被提交。
- HTML 和 PNG 能人工打开查看。

**结论**

手工门禁。该路径不进入默认 CI，因为它依赖真实 API key、外部网络和 provider 可用性。

## 全量回归补充

**命令**

```bash
PYTHONPATH=src python -m pytest -q
```

**输出结果**

```text
201 passed in 34.08s
```

**输出解释**

全量回归包含 unit、integration、contract、scenario、real-agent、provider optional、tracing、complete report、run viewer、sandbox、adapter、platform、pilot 和 E2E smoke。它用于确认新增 E2E 覆盖没有破坏既有 runtime 行为。

**结论**

通过。

## 已知边界

- 自动 CI 不调用真实 provider；真实 provider 路径保留为手工门禁。
- Docker E2E 依赖本地 Docker daemon；daemon 不可用时该用例会 skip。
- HTML run view 当前以 artifact 存在性和关键内容检查为主，没有浏览器像素级视觉断言。
- clean wheel install 验证本地 wheel artifact，不验证 PyPI 上传和跨平台安装矩阵。
- 外部 design partner staging 场景仍需要按 [DESIGN_PARTNER_RUNBOOK.md](DESIGN_PARTNER_RUNBOOK.md) 复跑。

## 总结

当前 E2E 覆盖已经能证明 Agent Runtime 的主要开源体验链路可跑：从安装、CLI、复杂 agent runtime 治理、真实 Docker sandbox、完整运行报告，到 E2E 文档 readiness。下一步最有价值的补充不是再增加 fake happy path，而是把真实 provider 手工门禁和 design partner staging runbook 变成可重复的外部验收证据。
