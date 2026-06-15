# Sandbox / Isolation Reviewer Memory

This file stores project-local experience for `sandbox-isolation-reviewer`. Memory is not a permanent global rule unless the user later approves a global skill upgrade.

## Stable Lessons

- subprocess executor 不是强安全沙箱，只能提供进程隔离、超时、环境变量裁剪、工作目录控制和输出捕获。
- policy guard 和 sandbox guard 必须分开描述：policy 决定是否允许，sandbox 限制允许后的执行影响面。
- 生产承诺必须绑定隔离等级；不能用一个笼统的“生产可用”覆盖所有 executor。
- 高风险生产写操作不应只依赖 in-process 或普通 subprocess。

## Candidate Improvements

- 后续可以补一份隔离等级表：`none`、`in_process`、`subprocess`、`os_sandbox`、`container`、`sidecar`、`remote`。
- 后续可以补隔离测试清单：文件越权、网络越权、环境变量泄露、子进程残留、超时逃逸、输出爆量。

## Review Patterns

- 如果文档把 subprocess 称为 sandbox，通常需要 `high` 或 `medium` finding，要求改成“弱隔离执行器”。
- 如果生产 1.0 承诺生产可用，但没有说明不同 executor 的适用场景，需要要求补 production support matrix。
- 如果工具可执行 shell、访问网络或读取宿主文件，需要检查默认拒绝、allowlist、cwd、env allowlist、timeout、输出截断和 audit。
- 如果未来引入 container/sidecar/remote executor，需要检查宿主挂载、网络模式、capability、用户身份、secret 注入和清理策略。

## Upgrade Proposals

- 如果本项目多次需要隔离专项评审，可以把该 overlay 升级为全局角色。
- 如果 container/sidecar 成为核心实现，可拆分出更专门的 `container-sandbox-reviewer`。
