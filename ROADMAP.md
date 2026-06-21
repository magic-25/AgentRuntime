# Roadmap

Agent Runtime 当前是 **Technical Preview**，Python package version 使用 `0.x` 语义。`pyproject.toml` 中的 `0.1.0` 表示开源包仍处于早期预览，不代表 runtime contract 的完整阶段。

历史和内部规划中出现的 `1.0` / `2.0` 指 runtime contract maturity gate，用来描述能力边界、验证深度和设计伙伴试点阶段，不等同于公开稳定版 package release。

## Package Version

| Version | 含义 |
| --- | --- |
| `0.x` | Technical Preview；API 和 contract 可能调整；适合评估、集成实验和 design partner pilot。 |
| `1.x` | 未来 public stable package；需要完成真实生产隔离后端、稳定 public API、外部 design partner 证据和安全响应流程。 |

## Runtime Contract Gates

| Gate | 目标 |
| --- | --- |
| MVP / `0.1` - `0.8` | 建立 core runtime、policy、audit、adapter、测试 agent、complete report 和场景测试基础。 |
| Contract `1.0` | Design Partner Pilot ready：治理链路可验证，公开文档边界清晰，CI 和 conformance 作为基本门禁。 |
| Contract `1.1` - `1.5` | 强化真实 sandbox backend、provider/framework adapter coverage、run visualization、audit export 和 operator runbook。 |
| Contract `2.0` | Platform integration ready：hosted control plane 仍可外置，但 runtime contract、registry、audit forwarding、remote executor contract 和 certification format 稳定。 |

## 当前下一步

- 用外部 design partner 场景复跑 `docs/runbooks/design-partner-runbook.md`，当前仓库已提供 `docs/reports/staging-validation-report.md` 作为 surrogate staging evidence。
- 扩展 OpenAI、Anthropic、LangGraph、MCP、Codex 的匿名真实 payload fixture；当前已有 `tests/fixtures/adapter_payloads/` 基线覆盖。
- 发布 `v0.1.0` GitHub technical preview release；PyPI publish 需要项目 owner 的 PyPI API token。

## Docker sandbox backend stable candidate gate

`DockerSandboxBackend` 在满足以下条件前必须保持 `preview`：

- host security baseline：记录 Docker daemon 权限、rootless/rootful 模式、宿主内核版本、seccomp/AppArmor/SELinux 状态和禁止挂载敏感 socket 的策略。
- trusted image chain：固定镜像 digest，记录镜像来源、更新流程和漏洞扫描结果。
- resource isolation evidence：记录 pids、cpu、memory、read-only root filesystem、cap-drop ALL、no-new-privileges、network none 和 tmpfs 行为证据。
- append-only audit export：将 JSONL/SQLite audit 转发到宿主 append-only 或 WORM sink，而不是只依赖本地文件。
- design partner staging evidence：至少一个真实 staging/design partner 场景跑通 runbook，并记录 operator feedback、policy denial explainability 和 failure recovery。
- rollback runbook：backend 不可用、Docker daemon 超时、镜像拉取失败、资源限制触发和 audit export 失败时必须 fail closed，并有清晰恢复步骤。
