from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    default_language: str = Field(default="uz", alias="DEFAULT_LANGUAGE")
    auto_migrate: bool = Field(default=True, alias="AUTO_MIGRATE")

    telegram_mode: str = Field(default="polling", alias="TELEGRAM_MODE")
    webhook_url: str | None = Field(default=None, alias="WEBHOOK_URL")
    webhook_secret: str | None = Field(default=None, alias="WEBHOOK_SECRET")

    admin_token: str | None = Field(default=None, alias="ADMIN_TOKEN")
    jwt_secret: str = Field(default="change_me", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=720, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    admin_seed_login: str = Field(default="Adminaaaa11", alias="ADMIN_SEED_LOGIN")
    admin_seed_password: str = Field(default="Adminaaaa11", alias="ADMIN_SEED_PASSWORD")
    admin_seed_name: str = Field(default="Администратор", alias="ADMIN_SEED_NAME")
    frontend_origin: str = Field(default="http://localhost:5173", alias="FRONTEND_ORIGIN")
    default_report_chat_id: int | None = Field(default=None, alias="DEFAULT_REPORT_CHAT_ID")
    warehouse_bar_chat_id: int | None = Field(default=None, alias="WAREHOUSE_BAR_CHAT_ID")
    warehouse_kitchen_chat_id: int | None = Field(default=None, alias="WAREHOUSE_KITCHEN_CHAT_ID")
    warehouse_supplies_chat_id: int | None = Field(default=None, alias="WAREHOUSE_SUPPLIES_CHAT_ID")
    warehouse_meat_chat_id: int | None = Field(default=None, alias="WAREHOUSE_MEAT_CHAT_ID")

    routing_map_json: str = Field(
        default="{}",
        alias="ROUTING_MAP_JSON",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator(
        "default_report_chat_id",
        "warehouse_bar_chat_id",
        "warehouse_kitchen_chat_id",
        "warehouse_supplies_chat_id",
        "warehouse_meat_chat_id",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value):
        if value in {"", None}:
            return None
        return value

    @property
    def routing_map(self) -> dict[str, dict[str, int]]:
        raw = json.loads(self.routing_map_json)
        if not isinstance(raw, dict):
            raise ValueError("ROUTING_MAP_JSON must be an object")

        normalized: dict[str, dict[str, int]] = {}
        for branch, warehouses in raw.items():
            if not isinstance(branch, str) or not isinstance(warehouses, dict):
                raise ValueError("Invalid routing map structure")
            normalized[branch] = {}
            for warehouse, group_id in warehouses.items():
                if not isinstance(warehouse, str):
                    raise ValueError("Warehouse names must be strings")
                normalized[branch][warehouse] = int(group_id)
        return normalized

    @property
    def branches(self) -> list[str]:
        return list(self.routing_map.keys())

    def warehouses_for_branch(self, branch: str) -> list[str]:
        return list(self.routing_map.get(branch, {}).keys())

    @property
    def warehouse_group_map(self) -> dict[str, int]:
        mapping: dict[str, int] = {}
        if self.warehouse_bar_chat_id is not None:
            mapping["bar"] = self.warehouse_bar_chat_id
        if self.warehouse_kitchen_chat_id is not None:
            mapping["kitchen"] = self.warehouse_kitchen_chat_id
        if self.warehouse_supplies_chat_id is not None:
            mapping["supplies"] = self.warehouse_supplies_chat_id
        if self.warehouse_meat_chat_id is not None:
            mapping["meat"] = self.warehouse_meat_chat_id
        return mapping

    @staticmethod
    def normalize_warehouse_slug(value: str | None) -> str | None:
        if not value:
            return None

        normalized = (
            value.strip()
            .lower()
            .replace("’", "'")
            .replace("`", "'")
            .replace("ʻ", "'")
            .replace("‘", "'")
        )

        aliases = {
            "bar": "bar",
            "бар": "bar",
            "kitchen": "kitchen",
            "kuxna": "kitchen",
            "кухня": "kitchen",
            "supplies": "supplies",
            "sredstva": "supplies",
            "средства": "supplies",
            "meat": "meat",
            "go'sht": "meat",
            "go‘sht": "meat",
            "gosht": "meat",
            "мясо": "meat",
        }
        return aliases.get(normalized)

    def group_for_warehouse(self, *, warehouse_slug: str | None = None, warehouse_name: str | None = None) -> int | None:
        slug = warehouse_slug or self.normalize_warehouse_slug(warehouse_name)
        if slug:
            chat_id = self.warehouse_group_map.get(slug)
            if chat_id is not None:
                return chat_id
        return self.default_report_chat_id

    def group_for(self, branch: str, warehouse: str) -> int | None:
        chat_id = self.group_for_warehouse(warehouse_name=warehouse)
        if chat_id is not None:
            return chat_id
        branch_map = self.routing_map.get(branch)
        if branch_map:
            return branch_map.get(warehouse)
        return self.default_report_chat_id


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
