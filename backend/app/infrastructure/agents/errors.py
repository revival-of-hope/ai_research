"""Actionable diagnostics without returning upstream bodies, prompts or API keys."""

import httpx
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded

from app.domain.research import ResearchError


def provider_error_message(error: BaseException) -> str:
    if isinstance(error, BaseExceptionGroup):
        return provider_error_message(error.exceptions[0])
    if isinstance(error, ResearchError):
        return str(error)
    if isinstance(error, ModelHTTPError):
        return status_message(error.status_code)
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "模型请求超时，请减少研究范围或选择快速模式后重试。"
    if isinstance(error, httpx.HTTPError):
        return "无法连接模型服务，请检查请求网址、代理和网络。"
    if isinstance(error, UsageLimitExceeded):
        return "已达到本次研究的模型调用或 token 预算，请减少研究范围后重试。"
    if isinstance(error, UnexpectedModelBehavior):
        return "模型响应不符合研究要求，请选择支持 Responses 工具调用和结构化输出的模型。"
    return "模型调用未完成，请检查请求网址、模型权限、服务商额度和网络。"


def status_message(status: int) -> str:
    return {
        400: "服务商拒绝请求参数，请检查模型是否支持 Responses 工具调用和结构化输出。",
        401: "API key 未通过验证，请检查密钥、服务商和地域是否匹配。",
        402: "服务商账户余额不足，请检查账户额度。",
        403: "服务商拒绝访问，请检查密钥权限和模型授权。",
        404: "模型或 Responses 接口不存在，请检查请求网址和模型 ID。",
        422: "服务商无法处理请求，请检查模型的 Responses 工具调用支持。",
        429: "服务商限流或额度不足，请检查账户额度并稍后重试。",
    }.get(status, f"模型服务返回 HTTP {status}，请稍后重试或检查服务商状态。")
