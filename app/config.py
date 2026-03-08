from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field
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

    routing_map_json: str = Field(
        default='{"Sardoba":{"Asosiy":-1001111111111}}',
        alias="ROUTING_MAP_JSON",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

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

    def group_for(self, branch: str, warehouse: str) -> int | None:
        branch_map = self.routing_map.get(branch)
        if not branch_map:
            return None
        return branch_map.get(warehouse)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
