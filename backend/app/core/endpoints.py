"""Validation for user-configured Responses endpoints."""

import ipaddress
from urllib.parse import urlparse

from app.core.config import settings
from app.domain.workspace import InvalidInput


def validate_provider_url(base_url: str) -> str:
    base_url = base_url.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidInput("Base URL 必须是 HTTP 或 HTTPS 地址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise InvalidInput("Base URL 不能包含凭据、查询参数或片段")
    if parsed.path.endswith(("/responses", "/chat/completions")):
        raise InvalidInput("Base URL 应填写版本根路径，不要包含 /responses")
    if not settings.allow_private_api_endpoints:
        host = parsed.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith((".localhost", ".local")):
            raise InvalidInput("默认禁止访问私有模型地址")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise InvalidInput("默认禁止访问私有模型地址")
    return base_url


def is_responses_model_compatible(base_url: str, model: str) -> bool:
    return bool(base_url.strip() and model.strip() and not any(c in model for c in "\r\n"))


def validate_responses_model(base_url: str, model: str) -> None:
    # Model catalogs vary by gateway. The connection test is the source of truth.
    if not is_responses_model_compatible(base_url, model):
        raise InvalidInput("请填写有效的 Responses 模型 ID")
