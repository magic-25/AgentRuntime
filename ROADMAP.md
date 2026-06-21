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

- 用真实 design partner/staging 场景跑通 `DESIGN_PARTNER_RUNBOOK.md`。
- 将 Docker sandbox backend 从 preview 推进到 stable candidate 前，补充宿主安全基线、镜像可信链、资源限制证据和失败回退 runbook。
- 在 GitHub 仓库设置中启用 branch protection、required checks 和 private vulnerability reporting。
- 收集 OpenAI、Anthropic、LangGraph、MCP、Codex 的真实 payload fixture，扩展 adapter replay。
