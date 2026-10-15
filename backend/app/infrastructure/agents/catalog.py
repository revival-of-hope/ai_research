"""Read a provider's Models API without generating tokens or returning secrets."""

import httpx

from app.core.endpoints import validate_provider_url
from app.infrastructure.agents.errors import status_message


async def discover_models(base_url: str, api_key: str) -> list[str]:
    base_url = validate_provider_url(base_url)
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.get(
                f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"}
            )
        if response.status_code != 200:
            if response.status_code == 404:
                raise RuntimeError("该地址未提供 Models API，可使用推荐模型或手动填写模型 ID。")
            raise RuntimeError(status_message(response.status_code))
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list):
            raise TypeError("Invalid Models response")
        models = sorted(
            {
                item["id"]
                for item in data
                if isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and item["id"].strip()
                and len(item["id"]) <= 120
                and not any(c in item["id"] for c in "\r\n")
            }
        )
        if not models:
            raise RuntimeError("服务商未返回可用模型，可手动填写已获授权的模型 ID。")
        return models
    except httpx.TimeoutException:
        raise RuntimeError("获取模型列表超时，请检查网络后重试。") from None
    except httpx.HTTPError:
        raise RuntimeError("无法获取模型列表，请检查请求网址和网络。") from None
    except (ValueError, TypeError):
        raise RuntimeError("模型列表格式无法识别，可使用推荐模型或手动填写。") from None
