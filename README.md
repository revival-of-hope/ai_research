# AI Research Assistant 2

面向 ML/CV 研究的自托管多智能体工作台。后端以 DDD 分层，研究运行由 **Pydantic AI** 编排，联网继续使用 **ddgs**。前端保留原有白色/浅灰/蓝色、圆角与宽屏对话风格，并提供计划、Agent 活动、Markdown 报告与逐轮来源。

## 能力

- 邮箱密码注册即登录、HttpOnly cookie、账户隔离、管理员管理。
- 多模型预设，Fernet 加密 API key，服务端 Responses API，模型 ID 自行填写并可测试连接；不以写死的目录冒充兼容性验证。
- 主管生成类型化计划 → 并行研究者 → 按需工具派生子智能体 → 证据审阅 → 流式报告。
- 快速/深度模式，研究者总预算和派生深度；模型推理开关与研究模式独立。
- 文档上传、处理状态、中英文词法 RAG；研究只读取本人明确选择且 ready 的资料。
- ddgs 文本/新闻搜索、显式联网开关、失败反馈；来源为搜索摘要和链接，不声称已读取网页全文。
- 每轮来源、公开活动、执行状态和用量持久化；停止和断连传播到子任务，失败不会伪装为成功回答。
- 安全 Markdown/GFM、引用跳转、复制和 Markdown 下载；历史搜索/重命名/删除、移动端抽屉、出错后编辑重试。
- 按预设快照统计成功、失败、取消运行的**已报告** token；旧消息用量兼容，不重复累计。

支持 TXT、Markdown、CSV、DOCX 和文本型 PDF；不包含 OCR、图片、扫描 PDF、旧 DOC 或 XLSX。轻量 RAG 不需要 embedding 服务。

## 启动

1. 复制环境文件：`cp .env.example .env`（PowerShell 可用 `Copy-Item .env.example .env`）。
2. 执行 `python scripts/generate_secrets.py`，填写 `.env` 中数据库密码、初始管理员、`JWT_SECRET`、`ENCRYPTION_KEY`。
3. 运行 `docker compose up --build -d`。
4. 打开 Web：<http://localhost:8080>；API：<http://localhost:8080/api/docs>；Adminer：<http://localhost:8081>。

后端启动先执行 Alembic 迁移，再创建或提升初始管理员。初次登录后创建自己的 Responses 模型预设，测试连接，选择资料/联网与研究模式即可开始。

Base URL 填写版本根路径，如 `https://api.openai.com/v1`，模型需实际支持 Responses、函数工具与结构化输出。前端和浏览器不会获取 API key。不是所有 OpenAI Chat Completions 网关都支持 Responses；以真实连接和工具能力为准。

## 升级已有部署

保留原 `.env`、`ENCRYPTION_KEY`、数据库和 uploads 卷，备份后重新构建启动。`0001` 至 `0007` 历史迁移不变，追加 `0008_research_runs`：扩展消息并新增研究运行表；不重置账户、密文、原消息或资料。旧消息缺少来源时不会臆造补齐。数据库迁移测试和当前环境验证范围见 [验证记录](docs/verification.md)。

停止服务使用 `docker compose down`；带 `-v` 会删除持久化卷。替换加密 key 会使旧预设无法解密。部署 HTTPS 时设置 `COOKIE_SECURE=true`；Adminer 默认面向本地开发，生产应限制其入口。私有模型端点需明确启用 `ALLOW_PRIVATE_API_ENDPOINTS=true`。

## 目录

```text
.agent/skills/                 本地可复用开发技能与下载的官方技能
backend/app/
  domain/                      研究预算、命令、账户/资料规则与领域值
  application/
    repo/                      持久化端口
    uow/                       事务端口
    service/                   账户、资料、研究用例
  infrastructure/
    agents/                    Pydantic AI 研究团队与连接测试
    repo/                      SQLModel 仓库
    uow/                       SQL 事务实现
    ingest/                    文件存储、解析、分块
    search/                    ddgs、轻量本地检索
  api/                         HTTP/SSE 适配及依赖装配
  models/                      兼容旧数据库的持久化映射
  schemas/                     请求/响应验证
  core/                        设置、认证、密钥和启动装配
frontend/src/
  lib/                         API、SSE、研究状态与历史恢复
  components/research/         输入、历史、活动、报告和引用
  components/settings/         模型、资料、用量
  pages/                       研究、账户与管理页面
```

## 开发与检查

```bash
cd backend
uv sync --dev --frozen
uv run pytest
uv run ruff check .
cd ../frontend
npm ci
npm test
npm run build
cd ..
python scripts/check_structure.py
```

本地开发需可访问的 PostgreSQL，将 `.env` 的 `DATABASE_URL` 改为该数据库地址，并从 backend 用 `uv run --env-file ../.env alembic upgrade head`、`uv run --env-file ../.env uvicorn app.main:app --reload` 启动 API；frontend 中 `npm run dev` 代理到 8000。正式部署仍使用 Compose。

可选迁移回归测试：为**独立空测试数据库**设置 `TEST_POSTGRES_URL` 后运行 `uv run pytest tests/test_postgres_migration.py`。测试拒绝非空库，在随机 schema 内执行升级/降级/重升并自动清理；不要指向业务数据库。

## 文档与复用

- [精确多步 Goal](docs/goal.md)、[原项目/竞品研究](docs/rewrite-research.md)
- [架构与预算](docs/architecture.md)、[API/SSE](docs/api.md)、[验证记录](docs/verification.md)
- [Skill 来源与复用](docs/skills.md)；后续开发读根目录 `AGENTS.md`。

限制：运行与当前 SSE 请求绑定，离开/停止会取消，不是后台持久任务队列；进程崩溃不会自动续跑。token 预算按上游已返回 usage 检查，并发在途请求可能越过阈值；上游未报告的中断请求用量不能等同真实账单。
