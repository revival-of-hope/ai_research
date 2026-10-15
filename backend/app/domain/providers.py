"""Provider configuration values, independent of SDKs and HTTP adapters."""

from typing import Literal

ProviderType = Literal["openai", "deepseek", "qwen", "anthropic", "custom"]

# Suggestions are starting points, never proof of account access or tool support.
PROVIDER_CATALOG = (
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-5.2", "gpt-5-mini"],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-flash", "deepseek-v4-pro"],
    },
    {
        "id": "qwen",
        "name": "Qwen / 通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen3.8-max", "qwen3.8-flash", "qwen3.7-plus"],
    },
    {
        "id": "anthropic",
        "name": "Claude / Anthropic",
        "base_url": "",
        "models": ["claude-sonnet-4-6", "claude-haiku-4-5"],
    },
    {
        "id": "custom",
        "name": "自定义服务",
        "base_url": "https://api.openai.com/v1",
        "models": [],
    },
)
