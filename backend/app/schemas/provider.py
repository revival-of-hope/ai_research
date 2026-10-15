from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ProviderUpsert(BaseModel):
    name: str = Field(default="My Responses API", min_length=1, max_length=80)
    base_url: HttpUrl
    model: str = Field(min_length=1, max_length=120)
    api_key: str | None = Field(default=None, min_length=1, max_length=2000)

    @field_validator("name", "model")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("名称和模型 ID 不能为空")
        return value

    @field_validator("api_key")
    @classmethod
    def strip_api_key(cls, value: str | None) -> str | None:
        return value.strip() if value else None


class ProviderPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    model: str
    compatible: bool
    has_api_key: bool = True


class ProviderTestResult(BaseModel):
    message: str


class ProviderUsage(BaseModel):
    provider_id: int | None
    provider_name: str
    model: str
    today_tokens: int
    month_tokens: int
    input_tokens: int
    output_tokens: int
    total_tokens: int


class UsageSummary(BaseModel):
    today_tokens: int
    month_tokens: int
    lifetime_tokens: int
    input_tokens: int
    output_tokens: int
    by_provider: list[ProviderUsage] = Field(default_factory=list)
