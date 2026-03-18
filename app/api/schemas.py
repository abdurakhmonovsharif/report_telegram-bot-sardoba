from __future__ import annotations

from datetime import date as DateType
from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    telegram_id: int
    name: str
    role: str
    language: str | None = None
    created_at: datetime
    updated_at: datetime


class RequestOut(BaseModel):
    id: int
    operation_type: str
    branch: str
    warehouse: str
    supplier_name: str | None = None
    date: DateType | None = None
    comment: str | None = None
    created_at: datetime
    user_id: int
    user_telegram_id: int
    user_name: str
    line_items: list[dict[str, str]] = Field(default_factory=list)
    photos: list[str] = Field(default_factory=list)


class SystemLogOut(BaseModel):
    id: int
    event_type: str
    level: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    stack_trace: str | None = None
    created_at: datetime


class StatsOut(BaseModel):
    users_total: int
    requests_total: int
    arrivals_total: int
    transfers_total: int
    errors_total: int
    errors_last_24h: int


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class ChangeLoginRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_login: str = Field(min_length=8, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)


class WarehouseUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


class DashboardSummaryOut(BaseModel):
    total_users: int
    today_active_users: int
    total_arrivals: int
    total_transfers: int
    today_operations: int
    total_images: int
    operations_with_images: int


class AdminProfileOut(BaseModel):
    id: int
    login: str
    full_name: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AuthOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    admin: AdminProfileOut
