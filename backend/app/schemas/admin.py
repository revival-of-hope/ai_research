from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class AdminUserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    is_admin: bool
    created_at: datetime
    total_tokens: int = 0


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None
