# 提供方配置与研究报错

项目统一使用 Responses API。推荐模型来自配置目录，不表示已验证账户权限或研究工具能力；实际列表通过已验证所有权的预设密钥或新输入的密钥读取 Models API，不发送生成请求。

## 官方资料

- [DeepSeek Responses 指南](https://api-docs.deepseek.com/guides/responses_api/)：官方根地址为 `https://api.deepseek.com`，支持函数工具、结构化输出和流式返回。
- [DeepSeek Responses 参数](https://api-docs.deepseek.com/api/create-response/)：思考默认开启，`reasoning.effort=none` 关闭；输出预算包含推理 token。
- [DeepSeek Models API](https://api-docs.deepseek.com/api/list-models/)：获取当前可见模型和元数据。
- [百炼 Responses](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-responses)：按地域、工作空间及授权选择模型与地址。
- [Claude 模型目录](https://platform.claude.com/docs/en/api/models/list)：Claude 原生协议与本项目不同，Claude 预设需使用支持 Responses 的网关。

## 截图失败与改动范围

截图只有泛化提示，无法确认实际上游状态、密钥权限或网络故障。本次没有使用真实模型密钥重放付费请求。

代码检查确认：此前关闭模型推理时未发送关闭参数，但 DeepSeek 默认开启思考；64-token 连接测试可能在正文输出前耗尽。现在关闭时显式发送 `none`，连接测试增加到 256 token 并禁用自动重试。仍使用官方 Responses，不引入协议转换。

研究和连接测试将上游错误转换成安全提示，不返回原始响应正文。研究失败原因也保存在对应轮次，便于重试。

| 状态 | 检查方向 |
| --- | --- |
| 401 | 密钥、提供方、地域是否匹配 |
| 402 / 429 | 余额、额度、并发与限流 |
| 403 | 密钥权限与模型授权 |
| 404 | API 根地址及模型 ID |
| 400 / 422 | Responses 函数工具、结构化输出支持 |
| 超时 / 连接失败 | 网络、代理与服务商状态 |
| 输出不符合要求 | 模型格式与工具能力 |

「测试连接」只验证基本正文响应，不保证完整研究能力；真实请求可能收费，由用户在界面主动触发。

## 密钥与升级

省略 JWT_SECRET / ENCRYPTION_KEY 会生成并持久保存随机值，已有环境配置优先。不要替换旧 ENCRYPTION_KEY；备份数据库时同时备份密钥文件。已有管理员密码不因重启而重置。生产按 `.env.example` 注释重新配置独立凭据。
