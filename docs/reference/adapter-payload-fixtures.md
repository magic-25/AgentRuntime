# Adapter Payload Fixtures

当前 adapter fixture 位于 `tests/fixtures/adapter_payloads/`，覆盖：

- OpenAI。
- Anthropic。
- LangGraph。
- MCP。
- Codex。

这些 fixture 是匿名 shape fixture，不包含 provider secret、客户数据或原始生产 payload。

## 验证命令

```bash
PYTHONPATH=src python -m pytest tests/test_adapter_payload_fixtures.py -q
```

## 当前保证

每个 fixture 都会验证：

- adapter 能翻译真实风格的 tool-call shape。
- tool name 保持正确。
- arguments 保持正确。
- adapter source 保持正确。
- adapter 不授予 capability，`capabilities_granted == []`。

## 扩展规则

新增 fixture 时必须：

- 去除 secret、客户数据、生产路径和 request body 中的敏感内容。
- 保留 provider payload 的结构特征。
- 写清 `source` 是匿名 fixture 还是公开文档 shape。
- 补充 expected tool name 和 arguments。
- 确保 fixture 能被 `tests/test_adapter_payload_fixtures.py` 覆盖。
