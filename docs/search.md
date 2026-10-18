# 官方联网搜索

搜索使用当前账户所选模型预设的运行快照，其中包含服务端解密的 API key。浏览器不接收密钥。没有匿名搜索引擎回退，也不再依赖 `ddgs`。

本实现依据 2026-10-18 阅读的官方公开文档；没有调用真实收费搜索或模型来验证能力。

## DeepSeek

[Search API 参考](https://api-docs.deepseek.com/api/search)与 [Search & Fetch 指南](https://api-docs.deepseek.com/guides/search)定义了独立 JSON 搜索接口：

```http
POST https://api.deepseek.com/v1/tools/search
Authorization: Bearer <当前预设的 API key>
Content-Type: application/json
```

```json
{"query":"研究问题 site:example.com","count":5,"need_content":false}
```

支持官方 Base URL `https://api.deepseek.com` 和 `https://api.deepseek.com/v1`。接口使用同一 DeepSeek API key，不需要指定模型 ID。带 DeepSeek 类型的非官方地址会明确报错，避免假设网关实现了独立搜索接口。

查询剥除首尾空白后按 Unicode 字符截取前 128 字符，保留 `site:`、引号、日期等搜索语法；结果数约束为 1 至 50。没有匹配结果时返回空列表。返回结构为 `results` 数组，其中包含 `title`、`url`、`snippet`、`summary`、`date` 等字段。适配器优先使用面向模型的 `summary`，缺失时使用 `snippet`，最多保留 1200 字符；`date` 映射为 `published`，未知日期保留空字符串。不会把服务端检索摘要宣称为已读取网页全文。

DeepSeek 的[发布公告](https://api-docs.deepseek.com/news/news261017)确认 Search/Fetch 于 2026-10-17 开放。[Responses 指南](https://api-docs.deepseek.com/guides/responses_api)还说明，内置 `web_search` 仅适用于 `deepseek-v4-pro`，`deepseek-flash` 会忽略该工具。因此这里直接使用独立搜索端点，让所选聊天模型不影响搜索能力。

独立搜索不产生模型 token usage，也不占用本应用的模型请求计数，但每次调用都占用研究搜索预算。官方按成功且非空的搜索请求收费，`count` 不改变每次请求的计价单位；具体价格与账户限制以 [Search & Fetch 指南](https://api-docs.deepseek.com/guides/search)为准。没有自动重试，以免一次应用搜索消耗多个收费请求。

## OpenAI 与 Responses 网关

按 [OpenAI 官方 Web search 指南](https://developers.openai.com/api/docs/guides/tools-web-search)，在当前预设的 `/responses` 发出一次搜索请求：

```json
{
  "model":"当前预设的模型 ID",
  "input":"搜索关键词",
  "tools":[{"type":"web_search","search_context_size":"low"}],
  "tool_choice":"required",
  "max_tool_calls":1,
  "reasoning":{"effort":"medium"},
  "max_output_tokens":4000,
  "include":["web_search_call.action.sources"],
  "store":false
}
```

这是一个额外的 Responses 模型请求，可能同时产生模型 token 费用和搜索工具费用。`max_tool_calls: 1` 限制该响应内置工具的总调用次数；`search_context_size` 影响上下文规模，不保证精确的来源数量。只有模型/网关实际完成了 `web_search_call` 才接受其联网证据；不支持时会返回明确错误。

适配器从 `message.content[*].annotations` 的 `url_citation` 读取标题和链接，从 `web_search_call.action.sources` 补全来源 URL。官方来源列表不保证提供网页摘要或发布日期，因此不会编造这些字段。引用摘要按照未截断正文中的 `start_index` / `end_index` 定位，提取对应句段的最多 500 字符局部上下文，并标注为“搜索模型生成的摘要（非网页原文）”。同一 URL 最多合并两个去重的对应片段；位置无效、跨段或无法关联正文时保留空摘要。只出现在来源列表、没有引用正文的 URL 也保留空摘要。

自定义预设使用相同 Responses 工具协议，不假设网关支持 OpenAI 的全部能力；拒绝工具或没有实际搜索输出时明确失败。其他预设类型目前不提供此搜索适配，关闭联网仍可正常使用模型。

## 注入、预算和取消

```python
search = make_web_search(
    provider_snapshot,
    client=optional_async_http_client,
    timeout=30,
    on_model_request=reserve_model_request,
    on_usage=record_model_usage,
)
results = await search(query, limit=6)
```

结果为 `list[dict[str, str]]`，每项包含 `title`、`url`、`snippet`、`published`。两个回调均为同步函数。OpenAI 请求发送前调用 `on_model_request()`，预算拒绝时不发请求；响应包含 usage 时调用 `on_usage({"input_tokens": n, "output_tokens": n, "total_tokens": n})`，即使响应未能提供有效搜索证据，也保留已报告的用量。DeepSeek 独立搜索不会调用这两个模型回调。

调用方负责搜索次数、请求次数、全局 token 和并发预算；工厂没有隐式共享状态。外部注入的 HTTP client 由调用方关闭，默认 client 在单次请求结束后关闭。HTTP 重定向禁用，避免携带 Bearer key 跳转到其他地址。错误仅返回固定中文说明或 HTTP 状态码，不回显响应正文、请求 URL、密钥或底层异常详情。

网络调用使用异步 HTTP 和整体截止时间。调用方取消会中断在途 HTTP，不转为普通搜索错误；截止时间到达会报搜索超时。取消本地请求无法保证服务商停止计费，未返回的 usage 也不能推断为零。

`backend/tests/test_web_search.py` 全部使用 `httpx.MockTransport` 验证端点、请求字段、预设密钥隔离、响应解析、预算回调、错误脱敏、拒绝跳转、整体超时和取消传播，不访问实际搜索服务。
