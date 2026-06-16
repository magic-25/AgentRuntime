# Changelog

本项目遵循面向公开读者的变更记录。当前尚未发布正式稳定版本；`main` 处于 **Technical Preview**，下一门禁是 **Design Partner Pilot**。

## Unreleased

- 暂无未发布条目。

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
- container backend stable candidate contract。
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
