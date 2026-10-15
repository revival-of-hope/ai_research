# 验证记录

日期：2026-10-15。使用项目内 DDD / Pydantic AI skill、验证与独立代码审查流程。

## 本地结果

| 检查 | 结果 |
| --- | --- |
| 后端完整 pytest，含真实 PostgreSQL | 77 passed，0 skipped，9.54s |
| 前端 Node 测试 | 14 passed |
| TypeScript / Vite 生产构建 | 通过 |
| Ruff | 通过 |
| DDD 结构与依赖方向 | 通过 |
| git diff --check | 通过 |
| docker compose config --quiet | 通过 |
| 隔离环境无 `.env` 的 Compose 默认配置 | 通过 |

本地运行于 Windows、Python 3.13.7。CI 配置 Python 3.12、Node 22 和 PostgreSQL 17；未推送或触发远程 GitHub Actions，不将本地通过等同于已运行的线上 CI。

后端有一条 Starlette / AnyIO 的上游弃用警告，不影响测试结果。

## PostgreSQL 迁移

使用 npm 官方 registry 的 `@embedded-postgres/windows-x64@17.8.0-beta.16` 便携测试二进制，核对下载 SHA512，实际 PostgreSQL 版本为 17.8。独立新集群和空库只监听 `127.0.0.1:52768`，与业务数据库隔离。

完整测试设置 `TEST_POSTGRES_URL`，执行旧数据升级到 `0009_provider_catalog`、降级与再次升级，核对账户、加密预设、消息、资料、全文索引与外键行为。测试使用随机 schema 并清理，拒绝非空数据库。最终完整测试通过后已停止该实例；测试工具仅保存在忽略的 backend/data 中，没有加入项目依赖。

## 模型与错误处理

- TestModel / FunctionModel 覆盖真实研究编排、子任务、预算、失败、取消、用量与数据隔离。
- OpenAI SDK / Pydantic AI 对 HTTP MockTransport 的 Responses 请求覆盖结构化计划、思考开关、错误映射与认证。
- 暂时恢复旧版未发送 `reasoning.effort=none` 的行为，测试因缺少 reasoning 设置失败；恢复修复后通过，证明测试能捕获该回归。
- 七类上游 HTTP 错误均不返回原始响应正文；研究失败的安全原因能持久保存。
- Models API 验证认证、目录格式、预设所有权，地址变化时拒绝复用旧密钥。
- 自动密钥覆盖无环境启动、环境配置优先、线程与进程并发、独立进程重启、损坏文件不轮换和已有管理员密码保留。

本次没有调用真实付费模型，也没有用真实账户密钥验证各家服务的权限、额度和端到端研究能力。连接测试仍由用户在界面主动触发。

## 浏览器

用独立 SQLite 测试数据启动 API 与 Vite，登录默认开发账户。验证 OpenAI、DeepSeek、Qwen 和 Claude 卡片切换、自动地址与模型填入、Claude 网关提示、未填密钥反馈，以及窄屏和桌面布局。验证结束后已停止临时服务。

独立代码审查发现的上游异常正文透传和旧客户端更新重置提供方类型均已修复并加入测试。
