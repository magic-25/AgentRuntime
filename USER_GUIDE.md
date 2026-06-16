# Agent Runtime 用户指南：场景与概念

Agent Runtime 是一个面向生产 agent 工具调用的 runtime。它把 agent 对工具的调用放进统一链路：

```text
ToolCall -> Context Filter -> Policy Engine -> Approval Gate -> Executor -> Result Filter -> Audit
```

当前公开状态是 **Technical Preview**，下一门禁是 **Design Partner Pilot**。这意味着 Agent Runtime 已经具备可验证的 runtime contracts、policy、audit、sandbox、adapter、conformance 和 platform-ready manifest，但还不是 public launch，也不是 hosted enterprise platform。

## 这份文档适合谁

这份文档适合三类用户：

- 正在把个人或团队 agent 接入真实工程流程的人。
- 想给 agent tool execution 加 policy、approval、audit、sandbox 的平台团队。
- 想评估 Agent Runtime 是否适合 design partner pilot 的工程负责人。

读完后，你应该能回答：

- Agent Runtime 现在能做哪些场景。
- 每个场景里哪些能力已经能跑，哪些只是 contract 或 preview。
- cloud runtime、control plane、remote executor、sandbox、audit 这些概念分别是什么意思。
- 应该从哪个 pilot 场景开始。

## 一句话定位

Agent Runtime 不是“更聪明的 agent”，而是 agent 工具调用的治理运行时。

它关注的是：

- agent 可以调用什么工具。
- 谁批准高风险工具调用。
- 工具调用在哪里执行。
- 执行是否进入 sandbox。
- 输入输出如何脱敏。
- 审计记录是否可验证。
- adapter 是否绕过 runtime 语义。
- cloud 或 platform 组件不可用时是否 fail closed。

它当前不承诺：

- hosted SaaS。
- hosted control plane。
- enterprise console。
- RBAC UI。
- remote executor production ready。
- 绝对 sandbox escape prevention。
- 真实 provider SDK 全量兼容。

## 核心概念

### Agent

agent 是能根据上下文决定下一步动作的软件组件。它可能来自 OpenAI、Anthropic、LangGraph、MCP、Codex、IDE 插件、内部自动化系统，或自研 orchestration。

在 Agent Runtime 里，agent 本身不是安全边界。安全边界来自 runtime 的 policy、approval、executor、sandbox、audit 和宿主部署策略。

### Agent Runtime

agent runtime 是 agent 执行工具调用时经过的受控运行层。它不负责替代模型推理，也不负责成为完整 agent 框架；它负责接住 tool call，并决定是否允许、是否审批、如何执行、如何记录。

### Tool Call

tool call 是 agent 请求执行某个工具的动作。它通常包含：

- tool name。
- input arguments。
- actor。
- environment。
- capabilities。
- adapter source。
- trace metadata。

Agent Runtime 的核心目标是让所有 tool call 都经过统一链路，而不是让 agent 或 adapter 直接执行工具。

### Capability

capability 是工具调用所需的权限标签，例如：

- `tool.invoke:read_customer`
- `customer.read`
- `customer.write`
- `command.execute:python`

policy engine 根据 capability 判断 allow、deny 或 require approval。未知 capability 默认 deny。

### Policy Engine

policy engine 根据 tool、capability、actor、environment 和规则决定工具调用是否允许。

当前安全默认值包括：

- unknown tool 默认 deny。
- unknown capability 默认 deny。
- policy hook exception 默认 deny。
- prod audit write failure 默认 fail closed。

### Approval Gate

approval gate 用于处理高风险或需要人工确认的工具调用。policy 可以返回 `require_approval`，runtime 会向 approval provider 发起请求。

approval timeout 默认 reject。

### Executor

executor 是实际执行工具调用的组件。当前常见 executor 包括：

- in-process function executor。
- limited subprocess executor。
- sandboxed command tool。
- sandbox backend contract。

limited subprocess executor 不是强安全沙箱。它只提供独立进程、cwd、env allowlist、timeout、stdout/stderr 捕获和输出截断。

### Sandbox Backend

sandbox backend 是宿主注入的强隔离执行后端。它用于承载高风险 command tool。

当前 support level：

- container backend：stable candidate。
- sidecar backend：preview。
- remote executor：contract beta。

Docker smoke evidence 只能证明当前环境可以执行 no-network/read-only/cap-drop smoke，不证明绝对逃逸防护。

### Adapter

adapter 把不同 agent/provider 的 tool call shape 翻译成 Agent Runtime 的统一调用格式。

adapter 的边界非常重要：

- adapter 只翻译调用。
- adapter 不授予 capability。
- adapter 不直接执行工具。
- adapter 不绕过 policy、approval、sandbox、audit。

当前 stable candidate adapter 包括：

- OpenAI adapter。
- Anthropic adapter。
- LangGraph adapter。
- MCP adapter。
- Codex workspace adapter。

### Audit Sink

audit sink 是审计事件写入位置。当前支持：

- JSONL audit sink。
- SQLite audit sink。

审计记录用于回答谁在什么环境下调用了什么工具、policy 如何决策、是否经过 approval、执行结果如何。

### Audit Hash Chain

audit hash chain 是本地审计链的 tamper-evident 机制。每条事件包含当前事件 hash 和上一条事件 hash，可以用 `agent-runtime audit verify` 验证链完整性。

它不是外部 WORM 或合规归档。需要更强追责时，应接入宿主的 append-only sink。

### Observer

observer 记录运行时指标，例如：

- tool calls。
- denied。
- approval requests。
- approval rejected。
- timeouts。
- audit write failures。
- failure rate。

observer 用于运行状态检查，不替代 audit。

### Conformance

conformance 是对 adapter、sandbox backend、pack 等扩展点的契约检查。它回答“这个实现是否遵守 runtime contract”。

### Certification

certification 是 platform-ready runtime 的证据报告。它列出 stable candidate subject、contract、support level、evidence refs 和 pass/fail 状态。

运行：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main certify run --subject all
```

### Evidence

evidence 是可复查的运行证据，例如：

- certification report。
- adapter replay report。
- sandbox evidence report。
- audit verify result。
- pilot report。
- pytest output。

### Control Plane

control plane 是集中管理 policy、registry、audit forwarding、run export、tenant/project/actor/resource 的平台层。

当前 Agent Runtime 有 platform integration contracts 和 simulation harness，但不自带 hosted control plane。

### Control Plane API

control plane API 是本地 runtime 与外部治理层之间的 contract。它描述 policy bundle、audit forwarding、run export、adapter/backend registry 等数据如何交换。

`control_plane_api` 当前是 stable candidate subject，但这不等于项目已经提供 hosted control plane。它表示 API contract 有 evidence，可以进入 design partner 验证。

### Cloud Runtime Control Plane

cloud runtime control plane 是部署在 cloud 里的治理层。推荐理解为：

- cloud 负责 policy registry、pack registry、audit forwarding、run export。
- local runtime 负责实际 tool execution、sandbox、本地 audit chain。

这是当前最适合 design partner pilot 的 cloud 连接方式。

### Remote Executor

remote executor 是把工具执行放到远程环境里的执行后端。它不同于 cloud control plane。

当前 `remote_executor` 是 contract beta，不适合宣称 production ready。

### Technical Preview

Technical Preview 表示当前能力适合工程验证和 design partner pilot，不适合宣称大规模公开发布或完整企业平台 ready。

### Design Partner Pilot

Design Partner Pilot 是和少量真实用户一起验证真实工作流的阶段。目标不是追求功能越多越好，而是验证 policy、audit、sandbox、adapter、cloud handoff 是否解决真实痛点。

### Support Level

| Level | 含义 |
| --- | --- |
| supported | core contract 已稳定，适合作为当前公开能力描述 |
| stable candidate | 有 conformance evidence，适合 design partner 验证 |
| preview | 可试用，但边界和能力仍会变化 |
| experimental | 仅实验性探索，不建议依赖 |
| beta / contract beta | contract 可讨论和演示，不代表生产执行 ready |
| unsupported | 当前不支持，不应对外承诺 |

## 场景总览

| 场景 | 当前状态 | 推荐用途 |
| --- | --- | --- |
| 本地 Python agent runtime | 可实际跑 | 最小集成、SDK 验证 |
| 本地 command tool 治理 | 可实际跑 | 本地自动化、低风险命令 |
| Staging internal admin agent | 可实际跑 | 审批、审计、observer 演示 |
| Code/CI agent governance | 可实际跑，pilot report 是 digest-only | coding agent 治理试点 |
| Adapter replay / conformance | 可实际跑 | 验证 adapter 不绕过 runtime |
| Container sandbox evidence | 可实际跑 | 验证本机 container backend evidence |
| Local agent + cloud runtime control plane | contract/demo 可做 | cloud 治理层 design partner |
| MCP tool governance | contract/demo 可做 | MCP 工具调用治理 |
| Ops diagnostic read-only agent | 可做 staging pilot | 企业只读诊断 agent |
| Local Codex/IDE agent governance | 可做 staging pilot | 本地开发工具治理 |
| Remote executor | contract beta | 协议设计，不适合 production 声明 |

## 场景一：本地 Python Agent Runtime

### 适合谁

适合想先把一个 Python agent 或内部自动化工具接入 runtime 的团队。

### 解决什么问题

很多 agent demo 会直接在应用进程里调用函数或命令，缺少统一 policy、approval、audit。这个场景把工具调用接入 Agent Runtime，让每次调用都有可检查的治理链路。

### 当前能做到什么

- 注册 Python function tool。
- 配置 allow / deny / require approval。
- 基于 capability 做 policy decision。
- 写 JSONL 或 SQLite audit。
- 生成 trace span events。
- 观察 observer metrics。
- 验证 audit hash chain。

### 不能承诺什么

- 不替代完整 agent framework。
- 不自动理解业务权限。
- 不保证宿主应用绕过 runtime 的直接调用也被拦截。

### 推荐验证

```bash
PYTHONPATH=src python examples/minimal_agent.py
python -m pytest
```

### 成功标准

- tool call 经过 runtime。
- policy decision 可解释。
- audit 记录可查询。
- 禁止的 tool 或 capability 被 deny。

## 场景二：本地 Command Tool 治理

### 适合谁

适合已经让 agent 执行本地命令的团队，例如跑测试、读文件、执行诊断脚本。

### 解决什么问题

command tool 风险高。没有治理时，agent 可能执行未授权命令、读取敏感环境变量、输出过大日志、卡住进程，或在错误目录里运行。

### 当前能做到什么

- command argv allowlist。
- cwd 控制。
- env allowlist。
- timeout。
- stdout/stderr 截断。
- policy 控制 command capability。
- 高风险 prod command 要求 sandbox backend。

### 不能承诺什么

- limited subprocess 不是强安全沙箱。
- 不防止宿主进程本身有过宽权限。
- 不声明容器绝对不可逃逸。

### 推荐验证

```bash
PYTHONPATH=src python examples/staging_internal_admin_pilot.py
PYTHONPATH=src python -m agent_runtime.cli.main audit verify --path .agent-runtime/staging-pilot/pilot-audit.db --sink sqlite
```

### 成功标准

- 非 allowlisted 或未知 command 被拒绝。
- 只有 allowlisted env 进入子进程。
- timeout 和输出截断生效。
- audit 中能看到 command 相关事件。

## 场景三：Staging Internal Admin Agent

### 适合谁

适合想演示后台管理、客户操作、内部自动化审批流程的团队。

### 解决什么问题

内部 admin agent 通常涉及读写内部数据。这个场景验证 staging 环境中 read、write approval、approval timeout、unknown prod tool deny、observer、audit verify 是否能一起工作。

### 当前能做到什么

已有示例：

```bash
PYTHONPATH=src python examples/staging_internal_admin_pilot.py
```

示例覆盖：

- staging read allow。
- staging write require approval。
- approval timeout reject。
- unknown prod tool deny。
- command env allowlist。
- SQLite audit。
- observer metrics。
- pilot report。

### 不能承诺什么

- 示例不连接真实客户系统。
- 示例不替代企业权限模型。
- 示例 isolation level 是 subprocess limited，不是强 sandbox。

### 推荐验证

```bash
PYTHONPATH=src python -m agent_runtime.cli.main audit query --path .agent-runtime/staging-pilot/pilot-audit.db --tool-name read_customer
PYTHONPATH=src python -m agent_runtime.cli.main audit verify --path .agent-runtime/staging-pilot/pilot-audit.db --sink sqlite
PYTHONPATH=src python -m agent_runtime.cli.main observe status --path .agent-runtime/staging-pilot/observer.json
```

### 成功标准

- approval request 和 rejection 可见。
- unknown prod tool 被 deny。
- audit hash chain valid。
- observer 有 tool_calls、denied、timeouts 等指标。

## 场景四：Code/CI Agent Governance

### 适合谁

适合把 coding agent 接入 repo、CI、测试、patch 生成流程的团队。

### 解决什么问题

coding agent 很容易从“跑测试”扩展到“改代码、commit、push、开 PR”。这个场景先把边界收紧：允许读 repo 和跑 allowlisted command，但拒绝 commit/push/PR。

### 当前能做到什么

当前 Code/CI reference pilot 能做到：

- clean repo 检查。
- dirty workspace 默认 abort。
- allowlisted command 执行。
- `git commit` / `git push` / `gh pr` 拒绝。
- network access 默认为 false。
- 生成 digest-only pilot report。

### 不能承诺什么

- 当前 Code/CI pilot report 是 digest-only，不是完整 runtime audit chain。
- 不自动生成 patch 安全评审。
- 不代表所有 IDE/Codex 工作流都已完成生产验证。

### 推荐验证

```bash
PYTHONPATH=src python -m agent_runtime.cli.main pilot code-ci \
  --repo . \
  --command "python -m pytest tests/test_code_ci_pilot.py" \
  --allow-command "python -m pytest tests/test_code_ci_pilot.py" \
  --write-scope .agent-runtime/design-partner-code-ci \
  --report .agent-runtime/design-partner-code-ci/code-ci-success-report.json
```

拒绝路径：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main pilot code-ci \
  --repo . \
  --command "git commit" \
  --write-scope .agent-runtime/design-partner-code-ci \
  --report .agent-runtime/design-partner-code-ci/code-ci-deny-report.json
```

### 成功标准

- allowlisted test command 成功。
- commit/push/PR 被拒绝。
- dirty workspace 被 abort。
- report 中明确 `commit_push_pr_denied=true`。

## 场景五：Adapter Replay / Conformance

### 适合谁

适合需要接入 OpenAI、Anthropic、LangGraph、MCP、Codex 等不同 agent 技术栈的团队。

### 解决什么问题

不同 provider 的 tool call shape 不同。如果 adapter 自己执行工具或自己授予权限，runtime 的 policy/audit/sandbox 就会被绕过。

这个场景验证 adapter 只负责翻译，不负责授权和执行。

### 当前能做到什么

当前支持：

- OpenAI adapter conformance。
- Anthropic adapter conformance。
- LangGraph adapter conformance。
- MCP adapter conformance。
- Codex workspace adapter conformance。
- Code/CI adapter replay。

### 不能承诺什么

- 不声明真实 provider SDK 全量兼容。
- 不声明所有 provider payload shape 都已覆盖。
- 不支持 adapter 自行授予 capability。

### 推荐验证

```bash
PYTHONPATH=src python -m agent_runtime.cli.main adapter conformance --adapter all --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main adapter replay --scenario code-ci --adapter openai --adapter langgraph --adapter codex
```

### 成功标准

- replay passed。
- `capabilities_granted=[]`。
- `runtime_semantics=policy_audit_sandbox_preserved`。
- adapter source 进入 metadata/audit 语义。

## 场景六：Container Sandbox Evidence

### 适合谁

适合需要验证本机或 staging 环境是否具备 container sandbox 基础运行条件的团队。

### 解决什么问题

高风险 command tool 不能只靠 subprocess。这个场景验证当前环境是否能运行 container backend smoke，并记录 evidence。

### 当前能做到什么

- 检测 Docker client。
- 检测 daemon。
- 运行 no-network/read-only/cap-drop smoke。
- 输出 schema 化 evidence。
- 标明 sandbox 限制。

### 不能承诺什么

- 不证明绝对 escape prevention。
- 不替代容器基线加固。
- 不替代多租户隔离平台。

### 推荐验证

```bash
PYTHONPATH=src python -m agent_runtime.cli.main sandbox evidence --backend container --run-smoke --image busybox:latest
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend container --dry-run
```

### 成功标准

- daemon available。
- smoke ran。
- smoke passed。
- limitations 明确包含 `no_absolute_escape_prevention`。

## 场景七：Local Agent + Cloud Runtime Control Plane

### 适合谁

适合想保留本地执行和本地 sandbox，同时把 policy、registry、audit、run export 放到云端统一治理的团队。

### 解决什么问题

很多企业不希望 agent 工具执行直接跑在外部 cloud，但又希望集中管理策略、审计和运行记录。这个场景把执行留在本地，把治理放到 cloud control plane。

### 推荐架构

```text
Local Agent
  -> Local Agent Runtime
  -> pull/validate policy bundle from Cloud Runtime Control Plane
  -> execute allowlisted tools locally
  -> write local audit hash chain
  -> forward redacted audit/run export to cloud
  -> cloud stores policy, registry, run evidence
```

### 当前能做到什么

当前可以做 contract/demo：

- policy registry contract。
- audit forwarding contract。
- run export contract。
- adapter/backend registry contract。
- tenant/project/actor/resource model。
- platform simulation harness。
- platform unavailable fail closed。
- policy stale fail closed。
- audit forwarding failed 时 local hash chain preserved。

### 不能承诺什么

- 当前没有 hosted control plane。
- 当前没有 enterprise console。
- 当前没有 RBAC UI。
- 当前不是 hosted SaaS。

### 推荐验证

```bash
PYTHONPATH=src python -m agent_runtime.cli.main platform simulate --scenario all
PYTHONPATH=src python -m agent_runtime.cli.main release status
```

### 成功标准

- simulation passed。
- platform failure semantics 清楚。
- run export 默认 redacted。
- local audit chain 先写，再 forward。

## 场景八：MCP Tool Governance

### 适合谁

适合已经在使用 MCP server 或准备把 MCP tools 接入 agent 的团队。

### 解决什么问题

MCP 让工具生态更容易扩展，也让工具治理风险变大。这个场景把 MCP tool call 接入 adapter，然后交给 runtime 做 policy、approval、sandbox、audit。

### 当前能做到什么

- MCP adapter stable candidate。
- MCP-style tool call 翻译。
- adapter conformance。
- adapter 不授予 capability。
- runtime 保留 policy/audit/sandbox 语义。

### 不能承诺什么

- 不自动信任所有 MCP server。
- 不替 MCP server 做业务权限校验。
- 不保证真实 MCP server payload 全量覆盖。

### 推荐验证

```bash
PYTHONPATH=src python -m agent_runtime.cli.main adapter conformance --adapter mcp --dry-run
```

### 成功标准

- MCP adapter 只翻译调用。
- capability 仍由 runtime policy 判断。
- adapter 不直接执行 tool。
- adapter conformance passed。

## 场景九：Ops Diagnostic Read-Only Agent

### 适合谁

适合平台、SRE、运维、安全团队做只读诊断 agent。

### 解决什么问题

ops agent 常常需要查状态、日志、metrics、配置。如果没有 policy 和 audit，它很容易变成高权限 shell。

这个场景将 ops agent 限制在 read-only、allowlisted command、audit required 的边界里。

### 当前能做到什么

可以用现有 command tool、policy、audit、observer、sandbox evidence 拼出 staging pilot：

- 只读命令 allowlist。
- prod unknown tool deny。
- command env allowlist。
- timeout。
- audit verify。
- observer status。
- sandbox backend evidence。

### 不能承诺什么

- 不连接真实生产系统。
- 不替代企业 IAM。
- 不保证 shell 命令天然只读，需要部署者维护 allowlist。

### 推荐验证

```bash
PYTHONPATH=src python examples/staging_internal_admin_pilot.py
PYTHONPATH=src python -m agent_runtime.cli.main audit verify --path .agent-runtime/staging-pilot/pilot-audit.db --sink sqlite
PYTHONPATH=src python -m agent_runtime.cli.main observe status --path .agent-runtime/staging-pilot/observer.json
```

### 成功标准

- 所有命令都有 allowlist。
- unknown tool deny。
- audit chain valid。
- observer 能看到 failure、timeout、deny。

## 场景十：Local Codex/IDE Agent Governance

### 适合谁

适合在本地 IDE、Codex workspace 或开发者机器上运行 coding agent 的团队。

### 解决什么问题

本地 coding agent 往往能读 repo、运行命令、改文件。团队需要知道它做了什么、哪些命令被允许、哪些操作必须禁止或审批。

### 当前能做到什么

可以组合：

- Codex workspace adapter stable candidate。
- Code/CI reference pilot。
- command tool governance。
- adapter replay。
- local audit 或 digest-only pilot report。
- cloud control plane contract demo。

### 不能承诺什么

- 不保证所有 Codex/IDE surface 已集成。
- Code/CI pilot 当前不是完整 runtime audit chain。
- 不自动处理 commit/push/PR 的企业审批流。

### 推荐验证

```bash
PYTHONPATH=src python -m agent_runtime.cli.main adapter conformance --adapter codex --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main pilot code-ci \
  --repo . \
  --command "python -m pytest tests/test_code_ci_pilot.py" \
  --allow-command "python -m pytest tests/test_code_ci_pilot.py" \
  --write-scope .agent-runtime/design-partner-code-ci \
  --report .agent-runtime/design-partner-code-ci/code-ci-success-report.json
```

### 成功标准

- Codex adapter 不授予 capability。
- 本地命令必须 allowlist。
- commit/push/PR 默认拒绝。
- report 或 audit evidence 可复查。

## 场景十一：Remote Executor Contract Beta

### 适合谁

适合正在设计远程执行协议、sidecar、worker pool 或隔离执行服务的团队。

### 解决什么问题

有些场景不希望工具在 agent 所在机器上执行，而希望发送到远程环境执行。remote executor contract 用于讨论请求/响应、fail closed、transport、安全边界和 audit handoff。

### 当前能做到什么

- remote executor contract beta。
- sandbox conformance 中可验证 contract 行为。
- release manifest 明确 remote executor 不在 stable candidate。

### 不能承诺什么

- 不适合 production execution。
- 不提供 hosted execution pool。
- transport security 仍需设计。
- 不声明多租户调度 ready。

### 推荐验证

```bash
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend remote --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main release status
```

### 成功标准

- remote executor 保持 contract beta。
- failure 时 fail closed。
- 不被误列为 stable candidate。

## 如何选择第一个 Pilot 场景

| 你的目标 | 推荐场景 |
| --- | --- |
| 治理 coding agent | Code/CI Agent Governance |
| 治理本地命令 | 本地 Command Tool 治理 |
| 治理 MCP 工具生态 | MCP Tool Governance |
| 接入 cloud 但不把执行放到 cloud | Local Agent + Cloud Runtime Control Plane |
| 做企业内部演示 | Staging Internal Admin Agent |
| 做 SRE/ops 只读诊断 | Ops Diagnostic Read-Only Agent |
| 做 IDE/Codex 本地治理 | Local Codex/IDE Agent Governance |
| 设计远程执行协议 | Remote Executor Contract Beta |

## 推荐的 Design Partner 起步路径

第一阶段建议选择一个低风险、证据清楚的场景：

```text
Code/CI Agent Governance
  -> Local Agent + Cloud Runtime Control Plane
  -> MCP Tool Governance 或 Ops Diagnostic Read-Only Agent
```

原因：

- Code/CI 场景已有 reference pilot。
- cloud control plane 可以先做治理层，不碰 hosted executor 的高风险。
- MCP 和 ops 场景能验证工具生态与企业只读诊断的真实需求。

## 当前最重要的已知缺口

### Code/CI pilot audit 边界

Code/CI reference pilot 当前生成 digest-only pilot report，不是完整 runtime audit chain。用户需要完整审计链时，应把 Code/CI pilot 接入 runtime audit sink，或明确报告边界。

### 真实 provider payload

adapter conformance 和 replay 已经存在，但仍需要真实 provider payload fixture 来验证 OpenAI、Anthropic、LangGraph、MCP、Codex 的更多实际 shape。

### Hosted control plane

当前只有 platform integration contracts 和 simulation harness，没有 hosted control plane、enterprise console 或 RBAC UI。

### Remote executor

remote executor 当前是 contract beta。可以做协议设计和 contract demo，不应宣称 production ready。

### Sandbox escape

container backend 是 stable candidate，但 Docker smoke 不证明绝对逃逸防护。生产隔离需要宿主侧安全基线、容器配置、网络策略、密钥隔离和审计归档共同完成。

## 对外表述建议

可以说：

- Agent Runtime 当前适合 Technical Preview 和 Design Partner Pilot。
- Agent Runtime 提供 production agent tool execution 的 runtime contracts 和治理边界。
- 当前可以验证 policy、approval、audit、adapter、sandbox 和 platform-ready manifest。
- Local Agent + Cloud Runtime Control Plane 是当前推荐的 cloud 连接形态。

不要说：

- 已经 public launch ready。
- 已经 hosted SaaS ready。
- 已经 enterprise console ready。
- remote executor production ready。
- sandbox 绝对不可逃逸。
- provider SDK 全量兼容。
