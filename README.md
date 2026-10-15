# AI Research Assistant

自托管的多智能体研究工作台，使用 FastAPI、Pydantic AI、PostgreSQL 与 React。模型调用统一使用 **Responses API**。

## 快速启动

需要 Docker 与 Docker Compose 2.24.0 或更新版本。在项目根目录运行：

```bash
docker compose up --build -d
```

无需先运行密钥脚本，也无需创建 `.env`。首次启动会迁移数据库、初始化管理员，随机生成 JWT 与 API key 加密密钥，并保存于 uploads 持久卷的 `.local-secrets.json`。重启和重建容器继续使用同一组密钥。

| 入口 | 地址 / 默认值 |
| --- | --- |
| 工作台 | http://localhost:8080 |
| API 文档 | http://localhost:8080/api/docs |
| 健康检查 | http://localhost:8080/api/health |
| Adminer | http://localhost:8081 |
| 初始管理员 | `admin@example.com` / `administrator-password` |
| 开发数据库 | 库名、用户名、密码均为 `research` |

**默认账户和数据库密码仅供开发。生产环境必须重新配置数据库密码、管理员账户、JWT_SECRET、ENCRYPTION_KEY，启用 HTTPS 和安全 cookie。** 配置项及注释见 [.env.example](.env.example)。需要覆盖默认值时才复制为 `.env`；已有 `.env` 继续优先生效。初始化不会重设已存在管理员的密码。

## 配置模型

登录后打开「模型设置」或「工作区设置」：

1. 选择提供方，自动填入默认地址和推荐模型；地址、名称、模型 ID 都可以修改。
2. 填写 API key，点击「获取可用模型」读取该账户的 Models API 列表。此步骤不会发送模型生成请求。
3. 保存预设，在研究输入框选择使用。可选的「测试连接」会发送一次小型生成请求，可能产生服务商费用；它只检查基本连接和正文响应。

| 提供方 | 默认 API 根地址 | 说明 |
| --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | Responses |
| DeepSeek | `https://api.deepseek.com` | 官方原生 Responses；推荐 `deepseek-flash`、`deepseek-v4-pro` |
| Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 百炼 Responses；可改为密钥对应地域 / 工作空间地址 |
| Claude | 用户填写 | 需要提供 Claude 模型且支持 Responses 的网关 |
| 自定义 | 可修改 | 必须支持 Responses |

Base URL 填 API 根路径，不包含 `/responses`、`/models` 等具体接口。推荐列表不代表账户已获授权；Models API 列表也不保证工具能力。研究需要模型支持函数工具与结构化输出。读取列表失败时保留推荐项并允许手填。Claude 原生 Messages 地址不能直接用于本项目。

API key 在服务端使用 Fernet 加密，已保存密钥不会回显。DeepSeek 关闭模型推理时显式发送 `reasoning.effort=none`，开启时发送所选强度。详细资料与报错排查见 [提供方配置](docs/providers.md)。

编辑预设时，地址不变可留空密钥继续使用；更改地址后需要重新输入对应密钥，避免把旧密钥发送给另一家服务商。

## 工作台能力

- 邮箱密码账户、HttpOnly cookie、用户数据隔离与管理员管理。
- 快速 / 深度研究，主管计划、并行研究者、受预算约束的子任务派生、证据审阅与流式报告。
- ddgs 联网搜索及明确开关；来源显示搜索摘要和链接，不声称读取了网页全文。
- TXT、Markdown、CSV、DOCX、文本 PDF 上传和中英文词法检索；只读取本人明确选择且处理完成的资料。暂不支持 OCR、扫描件、图片和 XLSX。
- 会话、每轮来源、公开活动、状态与已报告 token 用量持久化；支持停止、编辑重试、历史搜索、重命名和 Markdown 导出。
- 不展示或持久保存模型的私密思考过程；失败与取消不会伪装成成功报告。

运行与当前 SSE 请求绑定，离开页面或连接断开会取消；暂不支持进程崩溃后的自动续跑。用量来自上游已返回的 usage，不等同服务商账单；并发在途请求可能越过 token 预算阈值。

## 本地开发

需要 Python 3.12+、uv、Node.js 22 和本地 PostgreSQL。通过 shell 设置 `DATABASE_URL` 为开发库地址、`UPLOAD_DIR=data/uploads` 为本地上传目录，然后运行：

```bash
cd backend
uv sync --dev --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

也可把本地配置写入根目录 `.env`，两条启动命令分别改为 `uv run --env-file ../.env alembic upgrade head` 和 `uv run --env-file ../.env uvicorn app.main:app --reload`。注意 Compose 的默认数据库主机 `postgres` 仅适用于容器网络。

直接运行后端时，随机密钥默认保存在 backend/data/local-secrets.json，可用 `LOCAL_SECRETS_FILE` 指定持久位置。另开终端启动前端：

```bash
cd frontend
npm ci
npm run dev
```

打开 http://localhost:5173；Vite 把 `/api` 代理到本机 8000 端口。模型 API key 在网页中配置，无需写入 `.env`。

## 测试与 CI

```bash
cd backend
uv sync --dev --frozen
uv run --frozen ruff check .
uv run --frozen pytest
uv run --frozen python ../scripts/check_structure.py
cd ../frontend
npm ci
npm test
npm run build
```

确定性测试使用 TestModel、FunctionModel 和 HTTP MockTransport，无需真实模型密钥。覆盖协作、预算、取消、失败、资源所有权、密钥与重启、提供方目录、Models API 及 Responses 请求。

[GitHub Actions CI](.github/workflows/ci.yml) 在 push / pull request 时运行后端检查、测试与前端构建。后端 job 使用 PostgreSQL 17 独立空库验证旧版数据升级、降级和再次升级。本地设置 `TEST_POSTGRES_URL` 可执行同样的迁移测试；未设置时有一项 skip。该测试拒绝非空库，**不要指向业务数据库**。

当前本地验证结果、浏览器检查与真实模型验证边界见 [验证记录](docs/verification.md)。

## 升级与生产配置

升级前备份数据库、uploads 卷及原 `.env`。保留原 `ENCRYPTION_KEY`，否则旧 API key 无法解密。`0001`–`0008` 历史迁移保持不变；新增 `0009_provider_catalog` 只增加提供方类型，旧预设归为自定义，地址、模型和密文保留。账户、资料所有权和历史会话不重置。

显式环境密钥优先于自动文件。多进程首次启动使用文件锁及原子写入，共享同一组随机密钥；文件损坏时要求恢复，避免静默换钥。备份数据库时同时备份密钥文件或显式环境配置。

生产必须按 `.env.example` 的注释设置独立凭据，启用 `COOKIE_SECURE=true`，限制 `ALLOWED_ORIGINS` 和 Adminer 入口。私有模型端点默认禁用，确需访问时设置 `ALLOW_PRIVATE_API_ENDPOINTS=true`。

`docker compose down` 停止服务；**带 `-v` 会删除数据库和包含默认密钥的持久卷**。不要在已有部署中随意更换加密密钥。

## 代码结构与约定

```text
backend/app/domain/              领域规则、预算与配置值
backend/app/application/repo/    仓库端口
backend/app/application/uow/     事务端口
backend/app/application/service/ 用例编排
backend/app/infrastructure/      SQL、研究团队、文件处理与搜索
backend/app/api/                 HTTP / SSE 适配
backend/alembic/versions/        增量迁移
frontend/src/components/        研究和设置界面
frontend/src/lib/               API、流解析、表单及历史恢复
.agent/skills/                  项目指定的可复用技能
```

后续开发遵循 [AGENTS.md](AGENTS.md)，复用本地 DDD / Pydantic AI skill 与必要参考。领域层独立于 FastAPI、SQLModel、Pydantic AI。未经任务授权，不推送、部署或调用付费模型。
