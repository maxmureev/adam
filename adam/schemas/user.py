from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID


class SSOUserCreate(BaseModel):
    sso_id: str
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    picture: Optional[str] = None


class SSOUserResponse(SSOUserCreate):
    id: UUID

    class Config:
        from_attributes = True
