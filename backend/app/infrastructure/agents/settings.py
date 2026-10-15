"""Responses request settings shared by connectivity checks and research."""

from urllib.parse import urlparse


def responses_settings(
    base_url: str, provider_type: str, *, deep_thinking: bool = False, effort: str = "medium"
) -> dict:
    settings = {"openai_store": False}
    if deep_thinking:
        settings["openai_reasoning_effort"] = effort
    elif provider_type == "deepseek" or urlparse(base_url).hostname == "api.deepseek.com":
        # DeepSeek defaults to thinking=high. Omitting effort does not turn it off,
        # and a tiny probe budget can otherwise be exhausted before visible text.
        settings["openai_reasoning_effort"] = "none"
    return settings
