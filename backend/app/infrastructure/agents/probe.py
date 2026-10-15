"""A minimal Pydantic AI Responses connectivity check; never returns provider payloads."""

import asyncio

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from app.core.crypto import decrypt_secret
from app.core.endpoints import validate_provider_url
from app.domain.workspace import ModelPreset


async def probe_provider(preset: ModelPreset):
    model = OpenAIResponsesModel(
        preset.model,
        provider=OpenAIProvider(
            base_url=validate_provider_url(preset.base_url),
            api_key=decrypt_secret(preset.api_key_encrypted),
        ),
    )
    agent = Agent(model, name="provider_connection_test", model_settings={"max_tokens": 64})
    try:
        async with asyncio.timeout(45):
            result = await agent.run(
                "Reply with OK only.", usage_limits=UsageLimits(request_limit=1)
            )
        if not result.output.strip():
            raise RuntimeError("模型没有返回可显示的正文")
    except ModelHTTPError as error:
        messages = {
            401: "API key 未通过验证，请检查密钥与服务商是否匹配",
            403: "服务商拒绝访问，请检查密钥权限",
            404: "Responses 接口不存在，请检查 Base URL",
            429: "服务商限流或额度不足，请稍后重试",
        }
        raise RuntimeError(
            messages.get(error.status_code, "服务商拒绝请求，请检查模型 ID 与 Responses 支持")
        ) from None
    except TimeoutError:
        raise RuntimeError("连接超时，请检查网络和服务商状态") from None
    except RuntimeError:
        raise
    except Exception:  # noqa: BLE001 - keep upstream payloads and secrets out of HTTP responses.
        raise RuntimeError("无法连接模型服务，请检查 Base URL、密钥和 Responses 兼容性") from None
