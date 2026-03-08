from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import asyncpg

from app.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            dsn=self.settings.database_url,
            min_size=1,
            max_size=10,
            command_timeout=60,
        )
        if self.settings.auto_migrate:
            await self.apply_schema()

    async def disconnect(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def apply_schema(self) -> None:
        pool = self._require_pool()
        schema_sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        async with pool.acquire() as connection:
            await connection.execute(schema_sql)

    def _require_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("Database pool is not initialized")
        return self.pool

    async def log_event(
        self,
        *,
        level: str,
        event_type: str,
        message: str,
        context: dict[str, Any] | None = None,
        stack_trace: str | None = None,
    ) -> None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO system_logs (event_type, level, message, context, stack_trace)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                """,
                event_type,
                level.upper(),
                message,
                json.dumps(context or {}),
                stack_trace,
            )

    async def upsert_user(self, telegram_id: int, name: str) -> dict[str, Any]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            record = await connection.fetchrow(
                """
                INSERT INTO users (telegram_id, name)
                VALUES ($1, $2)
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    updated_at = NOW()
                RETURNING id, telegram_id, name, role, language, created_at, updated_at
                """,
                telegram_id,
                name,
            )
        return dict(record)

    async def update_user_language(self, telegram_id: int, language: str) -> dict[str, Any] | None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            record = await connection.fetchrow(
                """
                UPDATE users
                SET language = $2, updated_at = NOW()
                WHERE telegram_id = $1
                RETURNING id, telegram_id, name, role, language, created_at, updated_at
                """,
                telegram_id,
                language,
            )
        return dict(record) if record else None

    async def get_user_by_telegram_id(self, telegram_id: int) -> dict[str, Any] | None:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            record = await connection.fetchrow(
                """
                SELECT id, telegram_id, name, role, language, created_at, updated_at
                FROM users
                WHERE telegram_id = $1
                """,
                telegram_id,
            )
        return dict(record) if record else None

    async def create_request(
        self,
        *,
        user_id: int,
        operation_type: str,
        branch: str,
        warehouse: str,
        supplier_name: str | None,
        request_date: Any | None,
        comment: str | None,
        photos: list[str],
    ) -> dict[str, Any]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            async with connection.transaction():
                request_record = await connection.fetchrow(
                    """
                    INSERT INTO requests (
                        operation_type,
                        branch,
                        warehouse,
                        supplier_name,
                        date,
                        comment,
                        user_id
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id, operation_type, branch, warehouse, supplier_name,
                              date, comment, created_at, user_id
                    """,
                    operation_type,
                    branch,
                    warehouse,
                    supplier_name,
                    request_date,
                    comment,
                    user_id,
                )

                request_id = request_record["id"]
                if photos:
                    await connection.executemany(
                        """
                        INSERT INTO request_photos (request_id, telegram_file_id)
                        VALUES ($1, $2)
                        """,
                        [(request_id, file_id) for file_id in photos],
                    )

        result = dict(request_record)
        result["photos"] = photos
        return result

    async def list_users(self, limit: int, offset: int) -> list[dict[str, Any]]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT id, telegram_id, name, role, language, created_at, updated_at
                FROM users
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
        return [dict(row) for row in rows]

    async def list_requests(
        self,
        limit: int,
        offset: int,
        operation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        pool = self._require_pool()
        query = """
            SELECT
                r.id,
                r.operation_type,
                r.branch,
                r.warehouse,
                r.supplier_name,
                r.date,
                r.comment,
                r.created_at,
                r.user_id,
                u.telegram_id AS user_telegram_id,
                u.name AS user_name,
                COALESCE(
                    ARRAY_AGG(rp.telegram_file_id) FILTER (WHERE rp.id IS NOT NULL),
                    ARRAY[]::TEXT[]
                ) AS photos
            FROM requests r
            JOIN users u ON u.id = r.user_id
            LEFT JOIN request_photos rp ON rp.request_id = r.id
        """

        params: list[Any] = []
        if operation_type:
            query += " WHERE r.operation_type = $1"
            params.append(operation_type)

        query += """
            GROUP BY r.id, u.telegram_id, u.name
            ORDER BY r.created_at DESC
        """

        params.extend([limit, offset])
        query += f" LIMIT ${len(params)-1} OFFSET ${len(params)}"

        async with pool.acquire() as connection:
            rows = await connection.fetch(query, *params)
        return [dict(row) for row in rows]

    async def list_logs(
        self,
        limit: int,
        offset: int,
        level: str | None = None,
    ) -> list[dict[str, Any]]:
        pool = self._require_pool()
        query = """
            SELECT id, event_type, level, message, context, stack_trace, created_at
            FROM system_logs
        """
        params: list[Any] = []

        if level:
            query += " WHERE level = $1"
            params.append(level.upper())

        params.extend([limit, offset])
        query += " ORDER BY created_at DESC"
        query += f" LIMIT ${len(params)-1} OFFSET ${len(params)}"

        async with pool.acquire() as connection:
            rows = await connection.fetch(query, *params)
        return [dict(row) for row in rows]

    async def get_stats(self) -> dict[str, Any]:
        pool = self._require_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT
                    (SELECT COUNT(*) FROM users) AS users_total,
                    (SELECT COUNT(*) FROM requests) AS requests_total,
                    (SELECT COUNT(*) FROM requests WHERE operation_type = 'arrival') AS arrivals_total,
                    (SELECT COUNT(*) FROM requests WHERE operation_type = 'transfer') AS transfers_total,
                    (SELECT COUNT(*) FROM system_logs WHERE level = 'ERROR') AS errors_total,
                    (
                        SELECT COUNT(*)
                        FROM system_logs
                        WHERE level = 'ERROR'
                          AND created_at >= NOW() - INTERVAL '24 hours'
                    ) AS errors_last_24h
                """
            )
        return dict(row)

