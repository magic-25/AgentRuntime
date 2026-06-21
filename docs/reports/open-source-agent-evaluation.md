# 开源 Agent 采用评估

评估日期：2026-06-17  
评估状态：公开评估记录  
用途：为 Agent Runtime 选择真实 agent / 开源 agent 测试路径

## 结论

当前应分三层推进：

1. **立即纳入默认回归**：OpenAI-compatible provider agent 的 tool-call shape。  
   已通过 `tests/test_provider_real_agent.py` 覆盖，不需要真实 API key，不依赖网络。
2. **作为 optional integration**：GLM/Z.AI 真实 provider agent。  
   已提供 `GLM_API_KEY` 或 `ZAI_API_KEY` 的 shell 环境变量 / ignored `.env` 路径，不提交 secret，不进默认 CI 强依赖。
3. **作为后续 external adoption suite**：OpenHands、SWE-agent、LangGraph、CrewAI、AutoGen 等开源 agent / agent framework。  
   这些项目影响力大，但依赖、运行环境、模型配置和副作用更重，不适合直接放进 core runtime 默认测试。

## 评估样本

以下数据来自 GitHub public repository metadata，采样时间为 2026-06-17。

| 项目 | 仓库 | Stars | Forks | Open Issues | 主语言 | 评估定位 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| OpenHands | `All-Hands-AI/OpenHands` | 77512 | 9855 | 339 | Python | 完整 AI coding agent 产品，适合后续 design partner / external suite |
| SWE-agent | `SWE-agent/SWE-agent` | 19546 | 2138 | 23 | Python | Issue-to-fix coding agent，适合 Code/CI governance 场景 |
| AutoGen | `microsoft/autogen` | 59036 | 8905 | 891 | Python | 多 agent framework，影响力大但版本和项目边界需单独评估 |
| LangGraph | `langchain-ai/langgraph` | 35032 | 5866 | 592 | Python | graph agent framework，适合 optional lightweight framework integration |
| CrewAI | `crewAIInc/crewAI` | 53786 | 7524 | 474 | Python | 多 agent orchestration framework，适合后续 multi-agent governance 场景 |

## 为什么先做 GLM/OpenAI-Compatible Provider Agent

Agent Runtime 的核心风险不是“能不能跑一个大项目”，而是：

- 真实 provider 返回的 tool-call shape 能否被 agent 解析。
- agent 是否把 tool call 交给 runtime，而不是自己执行工具。
- runtime 的 policy、audit、sandbox 语义是否仍然生效。
- API key 是否不进入仓库、audit、测试报告和命令输出。

GLM/Z.AI 走 OpenAI-compatible chat/completions 形态，能用最小依赖验证真实 provider agent 的关键路径。它比直接接 OpenHands/SWE-agent 更适合作为第一条生产化验证路径。

## 为什么不把 OpenHands / SWE-agent 放进默认测试

OpenHands 和 SWE-agent 更接近完整应用或产品级 agent。直接放进默认测试会引入：

- 大量第三方依赖。
- 模型 provider 配置。
- 文件系统和代码修改副作用。
- 运行时间和网络不稳定性。
- 对第三方项目内部行为的脆弱耦合。

它们更适合做独立 external adoption suite：

- 只使用公开 fixture 或最小复现 repo。
- 默认 read-only。
- 不运行第三方 install/test 脚本，除非经过安全评估。
- 只记录摘要证据，不提交原始日志和 secret。

## 后续路线

### 阶段一：真实 provider agent

- 已完成：OpenAI-compatible provider agent fake transport 测试。
- 已完成：GLM/Z.AI optional integration test。
- 已完成：使用 ignored `.env` 中的本地 key 跑真实 GLM provider 测试，并记录不含 secret 的结果摘要。

### 阶段二：真实 framework agent

- 已完成：optional LangGraph graph agent test。
- 已完成：graph 节点产生一个 `echo` tool call。
- 已完成：注册后 runtime 负责 tool execution、policy、audit。
- 该测试通过 `framework-agents = ["langgraph"]` 标记为 optional framework integration。

### 阶段三：开源 agent external suite

- 对 SWE-agent 设计 Code/CI governance fixture。
- 对 OpenHands 设计 workspace tool governance fixture。
- 对 CrewAI / AutoGen 设计 multi-agent handoff governance fixture。
- 所有 fixture 默认 read-only，不提交第三方原始日志。

## 当前已落地文件

| 文件 | 作用 |
| --- | --- |
| `src/agent_runtime/testing/provider_agents.py` | OpenAI-compatible provider agent 和 GLM 环境变量工厂 |
| `src/agent_runtime/testing/langgraph_agents.py` | LangGraph framework agent 测试夹具 |
| `tests/test_provider_real_agent.py` | provider agent 默认测试和 GLM optional integration test |
| `tests/test_langgraph_agent_registration.py` | LangGraph graph agent 未注册 / 注册运行对比 |
| `docs/reference/agent-registry-contract.md` | agent registry contract |
| `docs/runbooks/design-partner-runbook.md` | design partner 验证 runbook |
| `docs/reports/real-agent-test-report.md` | real-agent 测试报告 |
| `docs/reports/test-report.md` | 综合测试报告 |
