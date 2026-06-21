# Security Policy

Agent Runtime 当前处于 **Technical Preview**，下一门禁是 **Design Partner Pilot**。项目目标是让 agent 工具调用在 policy、approval、executor、audit、observer 和 sandbox contract 下可验证地运行，但当前不声明 public launch、hosted enterprise platform 或绝对 sandbox escape prevention。

## 支持范围

当前安全边界覆盖：

- runtime policy enforcement。
- approval gate。
- JSONL / SQLite audit sink。
- tamper-evident audit hash chain。
- audit chain verifier。
- observer metrics。
- adapter translate-only contract。
- sandbox backend contract。
- container plan backend stable candidate contract，不执行真实 Docker container。
- Docker sandbox backend preview，显式 opt-in，依赖本地 Docker daemon 和宿主安全基线。
- sidecar backend preview contract。
- remote executor contract beta。

当前不支持或不承诺：

- hosted SaaS。
- hosted control plane。
- enterprise console。
- RBAC UI。
- multi-tenant hosted execution pool。
- remote executor production use。
- 绝对 sandbox escape prevention。
- weak subprocess 用于高风险生产写操作。

## 报告安全问题

请不要在公开 issue 中披露可利用细节、凭证、客户数据、生产路径或完整攻击步骤。

优先使用 GitHub private vulnerability reporting。若仓库尚未启用该功能，请创建一个不含敏感细节的公开 issue，请求维护者提供私下沟通渠道。公开 issue 中只写影响范围类别，例如：

- policy bypass。
- approval bypass。
- audit tampering。
- sandbox escape or confinement bypass。
- secret redaction bypass。
- adapter capability escalation。
- unsafe default enablement。

## 报告内容

私下报告建议包含：

- 受影响版本或 commit。
- 影响的组件。
- 复现环境。
- 最小复现步骤。
- 预期行为和实际行为。
- 影响评估。
- 是否涉及密钥、凭证、客户数据或生产系统。

请尽量提供最小化复现，不要附带真实客户数据、生产凭证或不可公开的第三方材料。

## 安全边界说明

`require_approval` 没有显式 approval provider 时默认 reject。测试或 demo 可以显式注入静态 approval provider，但生产配置不应依赖默认批准。

`subprocess` executor 不是强安全沙箱。它只提供独立进程、cwd、env allowlist、timeout、stdout/stderr 捕获和输出截断。

高风险 prod command tool 必须使用 `sandboxed_command_tool` 和宿主注入的强隔离 sandbox backend；backend 不可用时 runtime 返回 `sandbox.unavailable`，不会退回普通 subprocess。

sandboxed command 的环境变量会在进入 sandbox backend 前按 `env_allowlist` 裁剪，backend 不应接触未授权 secret。

JSONL / SQLite audit sink 的 hash chain 用于检测本地审计链篡改。JSONL sink 会使用本地 advisory file lock 串行化单节点写入，避免并发写破坏 hash chain；这不等同于分布式锁、外部 WORM 或合规归档。需要更强追责时，应接入宿主的 append-only sink。

当前 contrib `ContainerSandboxBackend` 是 container execution plan simulation，用于 contract 和 abuse check，不执行真实 Docker container。

`DockerSandboxBackend` 是显式 opt-in 的真实 Docker execution preview。它默认使用 no-network、read-only root filesystem、cap-drop ALL、no-new-privileges、pids/cpu/memory 限制、只挂载 runtime 允许的路径，并在进入 Docker 前裁剪 env allowlist。它仍依赖宿主 Docker daemon、镜像可信链、宿主内核/容器配置和外部审计归档，不声明绝对 sandbox escape prevention。

真实 Docker smoke evidence 由 `agent-runtime sandbox evidence --backend container --run-smoke` 单独采集，不能替代生产隔离评估。

adapter 不应授予 capability，不应绕过 runtime core 执行工具。所有 optional adapter/backend pack 默认 disabled，必须 explicit allowlist。

## 处理原则

维护者处理安全问题时应：

- 优先确认是否可复现。
- 判断是否涉及 policy、approval、audit、sandbox、adapter、secret redaction 或 unsafe default。
- 在修复中补充 regression test 或 conformance evidence。
- 避免在修复发布前公开可利用细节。
- 在变更记录中说明影响范围、修复状态和剩余限制。
