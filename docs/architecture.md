# 架构、接口与数据升级

## 统一研究工作台

问答、深度研究和实验核验共用资料库、模型预设和会话历史。问答仍由一次 Responses 调用完成；深度研究继续执行计划、研究、审阅和报告流程；实验核验保留独立的复核界面与领域规则，但作为研究工作台内的一类任务管理。

`domain` 只包含规则和值对象；`application/service` 编排用例；仓库负责查询和持久化；Unit of Work 管理提交、回滚和会话生命周期；`infrastructure` 实现 SQL、文件和模型适配；`api` 处理 HTTP 和 SSE。领域及应用层不导入 FastAPI、SQLModel 或 Pydantic AI。

研究与实验核验通过 `infrastructure/repo/resources.py` 共用模型预设解析、密钥解密、地址校验和已选资料所有权检查。核验调用模型期间不持有数据库事务，返回后重新验证资料和模型归属，再原子保存会话与核验结果。

## HTTP 契约

以下路径均以 `/api` 为前缀，除健康检查和登录注册外均需要登录。精确请求结构以应用的 `/api/docs` 为准。

| 方法与路径 | 用途 |
| --- | --- |
| `GET /research/conversations` | 统一历史，包含 `kind` 和 `comparison_id` |
| `GET /research/conversations/{id}` | 问答消息 |
| `GET /research/conversations/{id}/runs` | 研究执行记录 |
| `PATCH /research/conversations/{id}` | 重命名研究或核验历史 |
| `DELETE /research/conversations/{id}` | 删除历史及关联消息、执行记录或核验结果，保留资料 |
| `POST /research/ask/stream` | 快速问答或深度研究，SSE 返回 |
| `GET /research/comparisons` | 已保存的实验核验 |
| `POST /research/comparisons` | 用 `paper_document_id`、`run_document_id`、`provider_id`、`metric` 创建核验 |
| `GET /research/comparisons/{id}` | 核验内容、原文摘录及检查状态 |
| `GET /research/comparisons/{id}/evidence/{side}/{key}` | 查看对应原文，`side` 为 `paper` 或 `run` |
| `GET /research/comparisons/{id}/source-chunks/{side}?q=...` | 在本次所选资料中查找引用，最多返回 12 个片段 |
| `PATCH /research/comparisons/{id}` | 保存逐项修改，或用 `confirm: true` 最终确认 |
| `GET/POST /documents` | 共用资料列表和上传 |
| `GET /documents/search` | 资料搜索 |
| `DELETE /documents/{id}` | 删除本人资料 |

实验核验返回 `conversation_id`。统一历史通过该关联计算 `kind="comparison"`、`comparison_id`，普通研究为 `kind="research"`；数据库不重复保存任务类型。重命名返回同样的元数据。核验会话不能直接传给问答接口；继续讨论会新建研究会话并复用所选资料。

`/api/comparisons` 及其子路径保留为旧客户端兼容入口，调用相同处理器，不在 OpenAPI 中重复展示。前端使用 `/research/comparisons`；旧 `/comparison` 页面会跳转到新入口。可用 `?comparison={id}` 打开核验，或 `?conversation={id}` 打开问答。

SSE 保留 `meta`、计划和活动事件、正文增量、来源、用量、`done` 与 `error`。完成后停止读取尾流；失败或取消不能保存为成功回答。事件中不展示或持久保存模型私密思考。

## 调用统计与运行边界

已移除单次研究的 `requests`、`searches`、`tool_calls`、`total_tokens` 配额配置与拒绝逻辑，同时显式将 Pydantic AI `UsageLimits` 的累计限制设为 `None`，防止默认 50 次请求上限继续生效。调用次数和已返回的 token 用量仍记录在原有 usage 结构中。

数据库模型及历史迁移没有限额专用列，因此没有为了“清理限额”删除账户、消息、资料或用量字段，也不改写旧 usage JSON。保留协作人数、派生深度、并发、单请求超时和研究总超时；快速问答仍是一次模型调用。上游自己的额度、上下文长度和单次输出限制仍然适用。

## 数据迁移

升级前备份数据库、上传目录及原加密密钥，执行：

```bash
cd backend
uv run --frozen alembic upgrade head
```

`0001`–`0010` 原有迁移不变。新增 `0011_research_comparisons` 为 `comparison_record` 增加非空且唯一的 `conversation_id` 外键，并为所有旧核验记录创建相同所有者的历史记录。原核验 ID、资料 ID、模型 ID、摘录、人工修改、确认状态和创建时间保留；原账户、密钥、问答和文档不重建。

新核验与对应会话在同一事务创建，保存失败则一起回滚。修改核验时使用行锁，并更新会话活跃时间。删除统一历史先删除关联核验，再删除会话，避免外键冲突。资料不会随会话删除。

降级到 `0010` 仅移除关联列、约束和索引，保留核验数据及已创建的会话标题，避免删除用户重命名内容；再次升级会重新创建关联历史，旧的空会话可能仍在列表中。需要回退时应先备份，并在测试副本验证，不以降级替代备份恢复。

## 实验核验的证据边界

两份资料各自整理，并发执行且共用 120 秒时限。模型返回空内容时允许在剩余时限内重试一次；已有输出却无法核实引用时不重试。模型只接收已选资料的候选片段，没有联网和执行代码工具。每份最多 12 个片段，每个最多 3000 字符。

内部比较键仍为 `dataset`、`version`、`split`、`model`、`training`、`preprocessing`、`metric`、`value`、`unit`、`seed`，状态仍为 `aligned`、`mismatch`、`unknown`；这些是 API 兼容契约，界面使用自然中文。缺失和不可信引用保持 `unknown`。数值使用十进制规范化，百分数单位归一，不自动换算尺度；指标不一致或不明确时，数值保持 `unknown`。

训练条件按预训练来源比较，忽略被否定的预训练描述；裁剪方式和输入分辨率必须在两侧具有同一组可比属性。模型名、指标简称、数据集和划分的规范化都在领域规则内完成。旧九项记录仍可读取，不凭缺失的训练条件宣称所有实验条件一致。

论文信息的确定性补齐只限于结果值所在片段、目标表格标题及前后各两个原文片段，按数据库 `ordinal` 判断原文顺序。其他章节的同名模型不扩大取证范围；没有结果值引用时不补齐条件。表号不符、多张目标表仍无法区分时保持未知。运行摘要只从显式标签行补齐缺失内容，不覆盖已有候选。所有补齐都保留逐字摘录和对应片段 ID。

人工修改引用时验证文本片段属于当前记录对应的那份资料，且摘录确实出现在其中。资料删除后保留保存的摘录；PDF 页码只在摘录唯一匹配某页时提供，不猜测表格坐标或 OCR 内容。
