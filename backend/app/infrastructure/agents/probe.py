"""A minimal Pydantic AI Responses connectivity check; never returns provider payloads."""

import asyncio

import httpx
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from app.core.crypto import decrypt_secret
from app.core.endpoints import validate_provider_url
from app.domain.workspace import ModelPreset
from app.infrastructure.agents.errors import provider_error_message


async def probe_provider(preset: ModelPreset):
    try:
        async with httpx.AsyncClient(timeout=45, follow_redirects=False) as http:
            client = AsyncOpenAI(
                base_url=validate_provider_url(preset.base_url),
                api_key=decrypt_secret(preset.api_key_encrypted),
                http_client=http,
                max_retries=0,
            )
            model = OpenAIResponsesModel(
                preset.model, provider=OpenAIProvider(openai_client=client)
            )
            agent = Agent(
                model,
                name="provider_connection_test",
                model_settings={
                    "max_tokens": 256,
                    # The diagnostic probe needs visible text within a tiny budget.
                    "openai_reasoning_effort": "none",
                    "openai_store": False,
                },
            )
            async with asyncio.timeout(45):
                result = await agent.run(
                    "Reply with OK only.", usage_limits=UsageLimits(request_limit=1)
                )
            if not result.output.strip():
                raise RuntimeError("模型没有返回可显示的正文")
    except Exception as error:  # noqa: BLE001 - keep upstream payloads out of HTTP responses.
        raise RuntimeError(provider_error_message(error)) from None
