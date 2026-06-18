# Agent Runtime Complete Report

报告日期：2026-06-18
报告状态：公开体验报告
产品状态：Technical Preview

## 目的

本报告展示多个 agent 放进 Agent Runtime 后，用户能看到哪些 output，以及这些 output 如何体现 runtime 的核心价值。

它回答两个问题：

1. agent 做了什么。
2. runtime 为什么允许、为什么拒绝、是否经过 approval、是否强隔离、是否可审计。

本报告不是全量测试报告。全量测试见 [TEST_REPORT.md](TEST_REPORT.md)。场景 acceptance 见 [SCENARIO_TEST_REPORT.md](SCENARIO_TEST_REPORT.md)。真实 agent 夹具说明见 [REAL_AGENT_TEST_REPORT.md](REAL_AGENT_TEST_REPORT.md)。

## 如何复现

先确保 ignored `.env` 中有轮换后的真实 provider key：

```bash
cp .env.example .env
```

需要设置 `GLM_API_KEY` 或 `ZAI_API_KEY`。`.env` 不提交，报告不会打印或写入 API key。

运行：

```bash
PYTHONPATH=src python examples/complete_runtime_report.py
```

输出摘要：

```json
{
  "path": ".agent-runtime/complete-report",
  "scenario_count": 5,
  "provider_mode": "real",
  "screenshot": ".agent-runtime/complete-report/complete-report.png"
}
```

本地生成产物：

```text
.agent-runtime/complete-report/complete-report.json
.agent-runtime/complete-report/complete-report.md
.agent-runtime/complete-report/complete-report.html
.agent-runtime/complete-report/complete-report.png
.agent-runtime/complete-report/*-audit.jsonl
```

这些本地运行产物不提交。根目录的 `COMPLETE_REPORT.md` 只提交脱敏、稳定的体验摘要。

## 输出模型

每个 scenario 都包含：

| 字段 | 说明 |
| --- | --- |
| `agent` | agent id、名称、provider、framework、registration |
| `prompt` | 输入给 agent 的任务 |
| `transcript` | agent 的状态、决策过程、trace id |
| `tool_results` | runtime 返回给 agent 的 `ToolResult` |
| `governance.policy` | policy decision、reason、rule id、policy version |
| `governance.approval` | approval 状态、原因、timeout |
| `governance.sandbox` | isolation level、backend、available |
| `governance.audit` | audit commit 状态和事件数量 |
| `trace` | governed trace 是否包含 agent/tool/policy/approval/sandbox span |
| `audit` | audit event sequence |

## 完整体验矩阵

| ID | Agent | 目的 | 关键 output |
| --- | --- | --- | --- |
| `scripted_echo` | Scripted Echo Agent | 最小成功 tool call | `ToolResult(status=success)`，policy allow，audit committed |
| `provider_tool_call` | Provider Tool Calling Agent | provider-style tool selection | provider 选择 `echo`，runtime 执行 `echo` |
| `policy_deny` | Policy Deny Agent | 展示拒绝路径 | `ToolResult(status=denied)`，policy deny，tool 未执行 |
| `approval_gate` | Approval Gate Agent | 展示 approval gate | approval approved，tool 成功执行 |
| `sandboxed_command` | Sandboxed Command Agent | 展示强隔离 command execution | sandbox `isolation_level=strong`，backend 已记录 |

## Scenario 1：Scripted Echo Agent

**输入**

```text
echo once
```

**Agent 做了什么**

```text
prompt:echo once
call:echo
stop
```

**Runtime 输出**

```json
{
  "status": "success",
  "error": null,
  "output": {
    "message": "hello from scripted agent"
  }
}
```

**Governance 输出**

```json
{
  "policy": {
    "decision": "allow",
    "reason": "matched_rule",
    "rule_id": "allow-echo",
    "policy_version": 1
  },
  "audit": {
    "status": "committed"
  }
}
```

**用户能体验到什么**

最小 agent loop 不再是直接调用函数，而是进入 runtime 的 policy、execution、audit 和 governed trace 链路。

## Scenario 2：Provider Tool Calling Agent

**输入**

```text
call echo using provider tool call
```

**Agent 做了什么**

```text
request:glm
tool_call:echo
runtime:success
stop
```

测试环境为了保持 CI 稳定，会显式使用 fake provider mode；用户运行 `examples/complete_runtime_report.py` 默认使用真实 `.env` key。

**Runtime 输出**

```json
{
  "status": "success",
  "output": {
    "message": "hello from provider-style agent"
  }
}
```

**用户能体验到什么**

provider 或 OpenAI-compatible agent 仍然负责选择 tool call，但执行权进入 Agent Runtime。这样业务输出不变，生产治理证据增加。

## Scenario 3：Policy Deny Agent

**输入**

```text
try deleting a protected record
```

**Agent 做了什么**

```text
prompt:try deleting a protected record
call:delete_record
blocked:default_decision
```

**Runtime 输出**

```json
{
  "status": "denied",
  "error": "default_decision",
  "output": null
}
```

**Governance 输出**

```json
{
  "policy": {
    "decision": "deny",
    "reason": "default_decision"
  },
  "execution": {
    "tool_executed": false
  },
  "audit": {
    "status": "committed"
  }
}
```

**用户能体验到什么**

agent 想做的动作和 runtime 为什么拒绝是分开的。拒绝不是静默失败：trace 会关闭 tool span，并记录 deny reason。

## Scenario 4：Approval Gate Agent

**输入**

```text
run high-risk echo with approval
```

**Agent 做了什么**

```text
prompt:run high-risk echo with approval
call:echo
stop
```

**Governance 输出**

```json
{
  "policy": {
    "decision": "require_approval",
    "reason": "matched_rule"
  },
  "approval": {
    "status": "approved",
    "approved": true,
    "reason": "approved-for-complete-report"
  },
  "audit": {
    "status": "committed"
  }
}
```

**用户能体验到什么**

runtime 可以表达“不是直接 allow，而是经过 approval 后 allow”。这对生产操作、内部 admin agent 和高风险 command 很重要。

## Scenario 5：Sandboxed Command Agent

**输入**

```text
run sandboxed status command
```

**Runtime 输出**

```json
{
  "status": "success",
  "output": {
    "exit_code": 0,
    "stdout": "sandbox command completed",
    "stderr": ""
  }
}
```

**Governance 输出**

```json
{
  "policy": {
    "decision": "allow",
    "reason": "matched_rule"
  },
  "sandbox": {
    "isolation_level": "strong",
    "backend": "complete-report-sandbox",
    "available": true,
    "status": "success"
  },
  "audit": {
    "status": "committed"
  }
}
```

**用户能体验到什么**

command tool 不只是“跑了命令”。runtime 能说明该命令是在强隔离 backend 下执行，并把 isolation evidence 写入 trace。

## Governed Trace

成功执行的 governed trace 结构如下：

```text
agent_run
  tool_call
    policy_evaluation
    approval_gate
    sandbox_execution
```

并非每个 scenario 都包含所有子 span：

- `policy_evaluation`：所有 tool call 都应有。
- `approval_gate`：只有 `require_approval` path 有。
- `sandbox_execution`：只有 sandboxed command path 有。
- `audit_status=committed`：tool span finish 中记录，用于说明该片段已进入 audit sink。

## 结论

`COMPLETE_REPORT.md` 和 `examples/complete_runtime_report.py` 提供了一个完整、可复现、默认使用真实 provider API key 的体验入口。它展示 Agent Runtime 不只是让 agent 调用工具，而是把 agent 行为变成可治理、可解释、可审计的运行链路。
