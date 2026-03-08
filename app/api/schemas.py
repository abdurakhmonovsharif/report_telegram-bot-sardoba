from __future__ import annotations

from datetime import date as DateType
from datetime import datetime
from typing import Any

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
