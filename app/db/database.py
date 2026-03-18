from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

from app.config import Settings
from app.core.security import hash_password, validate_admin_login, validate_admin_password

STATIC_WAREHOUSE_SLUGS = ("bar", "kitchen", "supplies", "meat")


def _record_to_dict(record: asyncpg.Record | None) -> dict[str, Any] | None:
    return dict(record) if record else None


def _json_dumps(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, default=str)


def _request_code(*, operation_type: str, request_id: int, created_at: datetime | None) -> str:
    prefix = "PRI" if operation_type == "arrival" else "PER"
    ts = (created_at or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return f"{prefix}-{ts}-{request_id:06d}"


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
        await self.seed_default_admin()

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None

    def _require_pool(self) -> asyncpg.Pool:
        if not self.pool:
            raise RuntimeError("Database pool is not initialized")
        return self.pool

    # ========================
    # SCHEMA + MIGRATION
    # ========================
    async def apply_schema(self) -> None:
        pool = self._require_pool()

        base_dir = Path(__file__).parent
        schema_file = base_dir / "schema.sql"
        migrations_dir = base_dir / "migrations"

        async with pool.acquire() as connection:
            if schema_file.exists():
                schema_sql = schema_file.read_text(encoding="utf-8")
                if schema_sql.strip():
                    try:
                        await connection.execute(schema_sql)
                    except Exception as exc:
                        if "already exists" not in str(exc).lower():
                            raise

            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            applied_versions = {
                row["version"]
                for row in await connection.fetch("SELECT version FROM schema_migrations")
            }

            if migrations_dir.exists():
                for migration_file in sorted(migrations_dir.glob("*.sql")):
                    if migration_file.name in applied_versions:
                        continue

                    migration_sql = migration_file.read_text(encoding="utf-8")
                    async with connection.transaction():
                        await connection.execute(migration_sql)
                        await connection.execute(
                            "INSERT INTO schema_migrations (version) VALUES ($1)",
                            migration_file.name,
                        )

    # ========================
    # ADMIN SEED
    # ========================
    async def seed_default_admin(self) -> None:
        login = validate_admin_login(self.settings.admin_seed_login)
        password = validate_admin_password(self.settings.admin_seed_password)
        await self.execute(
            """
            INSERT INTO admin_users (login, password_hash, full_name, is_active)
            VALUES ($1, $2, $3, TRUE)
            ON CONFLICT (login)
            DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                full_name = EXCLUDED.full_name,
                is_active = TRUE,
                updated_at = NOW()
            """,
            login,
            hash_password(password),
            self.settings.admin_seed_name,
        )

    # ========================
    # BASE METHODS
    # ========================
    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        async with self._require_pool().acquire() as conn:
            rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        async with self._require_pool().acquire() as conn:
            row = await conn.fetchrow(query, *args)
        return _record_to_dict(row)

    async def fetchval(self, query: str, *args: Any) -> Any:
        async with self._require_pool().acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        async with self._require_pool().acquire() as conn:
            return await conn.execute(query, *args)

    async def executemany(self, query: str, args: list[tuple[Any, ...]]) -> None:
        if not args:
            return
        async with self._require_pool().acquire() as conn:
            await conn.executemany(query, args)

    # ========================
    # LOGS + AUDIT
    # ========================
    async def log_event(
        self,
        *,
        level: str,
        event_type: str,
        message: str,
        context: dict[str, Any] | None = None,
        stack_trace: str | None = None,
    ) -> None:
        try:
            await self.execute(
                """
                INSERT INTO system_logs (event_type, level, message, context, stack_trace)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                """,
                event_type,
                level.upper(),
                message,
                _json_dumps(context),
                stack_trace,
            )
        except Exception as exc:
            print("log_event failed:", exc)

    async def log_audit(
        self,
        *,
        actor_type: str,
        action_type: str,
        entity_type: str,
        message: str,
        actor_user_id: int | None = None,
        actor_admin_id: int | None = None,
        entity_id: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        try:
            await self.execute(
                """
                INSERT INTO audit_logs (
                    actor_type,
                    actor_user_id,
                    actor_admin_id,
                    action_type,
                    entity_type,
                    entity_id,
                    message,
                    meta
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                """,
                actor_type,
                actor_user_id,
                actor_admin_id,
                action_type,
                entity_type,
                entity_id,
                message,
                _json_dumps(meta),
            )
        except Exception as exc:
            print("log_audit failed:", exc)

    # ========================
    # USERS
    # ========================
    async def upsert_user(
        self,
        telegram_id: int,
        name: str,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        username: str | None = None,
    ) -> dict[str, Any]:
        record = await self.fetchrow(
            """
            INSERT INTO users (
                telegram_id,
                name,
                first_name,
                last_name,
                username,
                first_seen_at,
                last_seen_at
            )
            VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
            ON CONFLICT (telegram_id)
            DO UPDATE SET
                name = EXCLUDED.name,
                first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                username = COALESCE(EXCLUDED.username, users.username),
                updated_at = NOW(),
                last_seen_at = NOW()
            RETURNING *
            """,
            telegram_id,
            name,
            first_name,
            last_name,
            username,
        )
        if record is None:
            raise RuntimeError("Failed to upsert user")
        return record

    async def get_user_by_telegram_id(self, telegram_id: int) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            SELECT *
            FROM users
            WHERE telegram_id = $1
            """,
            telegram_id,
        )

    async def update_user_language(self, telegram_id: int, language: str) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            UPDATE users
            SET language = $2, updated_at = NOW(), last_seen_at = NOW()
            WHERE telegram_id = $1
            RETURNING *
            """,
            telegram_id,
            language,
        )

    async def update_user_contact(
        self,
        *,
        telegram_id: int,
        phone_number: str,
        full_name: str,
        first_name: str | None = None,
        last_name: str | None = None,
        username: str | None = None,
    ) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            INSERT INTO users (
                telegram_id,
                name,
                first_name,
                last_name,
                username,
                phone_number,
                first_seen_at,
                last_seen_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
            ON CONFLICT (telegram_id)
            DO UPDATE SET
                name = EXCLUDED.name,
                first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                username = COALESCE(EXCLUDED.username, users.username),
                phone_number = EXCLUDED.phone_number,
                updated_at = NOW(),
                last_seen_at = NOW()
            RETURNING *
            """,
            telegram_id,
            full_name,
            first_name,
            last_name,
            username,
            phone_number,
        )

    async def update_user_avatar(
        self,
        *,
        telegram_id: int,
        file_id: str,
        file_unique_id: str | None = None,
        width: int | None = None,
        height: int | None = None,
        file_size: int | None = None,
    ) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            UPDATE users
            SET
                avatar_file_id = $2,
                avatar_file_unique_id = $3,
                avatar_width = $4,
                avatar_height = $5,
                avatar_file_size = $6,
                updated_at = NOW(),
                last_seen_at = NOW()
            WHERE telegram_id = $1
            RETURNING *
            """,
            telegram_id,
            file_id,
            file_unique_id,
            width,
            height,
            file_size,
        )

    # ========================
    # BRANCHES + WAREHOUSES
    # ========================
    async def list_bot_branches(self) -> list[dict[str, Any]]:
        return await self.fetch(
            """
            SELECT id, code, slug, bot_name, admin_name, sort_order, is_active, created_at, updated_at
            FROM branches
            WHERE is_active = TRUE
            ORDER BY sort_order, id
            """
        )

    async def get_branch_by_id(self, branch_id: int) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            SELECT id, code, slug, bot_name, admin_name, sort_order, is_active, created_at, updated_at
            FROM branches
            WHERE id = $1
            """,
            branch_id,
        )

    async def list_active_warehouses(self) -> list[dict[str, Any]]:
        return await self.fetch(
            """
            SELECT
                id,
                slug,
                name,
                description,
                is_active,
                sort_order,
                group_chat_id,
                group_chat_title,
                group_linked_at,
                created_at,
                updated_at
            FROM warehouses
            WHERE is_active = TRUE
              AND slug = ANY($1::TEXT[])
            ORDER BY sort_order, id
            """,
            list(STATIC_WAREHOUSE_SLUGS),
        )

    async def get_warehouse_by_id(self, warehouse_id: int) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            SELECT
                id,
                slug,
                name,
                description,
                is_active,
                sort_order,
                group_chat_id,
                group_chat_title,
                group_linked_at,
                created_at,
                updated_at
            FROM warehouses
            WHERE id = $1
            """,
            warehouse_id,
        )

    async def get_warehouse_by_slug(self, slug: str) -> dict[str, Any] | None:
        normalized_slug = self.settings.normalize_warehouse_slug(slug) or slug.strip().lower()
        return await self.fetchrow(
            """
            SELECT
                id,
                slug,
                name,
                description,
                is_active,
                sort_order,
                group_chat_id,
                group_chat_title,
                group_linked_at,
                created_at,
                updated_at
            FROM warehouses
            WHERE slug = $1
            """,
            normalized_slug,
        )

    async def get_active_warehouse_by_name(self, name: str) -> dict[str, Any] | None:
        normalized_slug = self.settings.normalize_warehouse_slug(name)
        return await self.fetchrow(
            """
            SELECT
                id,
                slug,
                name,
                description,
                is_active,
                sort_order,
                group_chat_id,
                group_chat_title,
                group_linked_at,
                created_at,
                updated_at
            FROM warehouses
            WHERE is_active = TRUE
              AND (LOWER(name) = LOWER($1) OR slug = $2)
            ORDER BY sort_order, id
            LIMIT 1
            """,
            name.strip(),
            normalized_slug,
        )

    async def bind_warehouse_group(
        self,
        *,
        warehouse_id: int,
        group_chat_id: int,
        group_chat_title: str | None,
    ) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            UPDATE warehouses
            SET
                group_chat_id = $2,
                group_chat_title = $3,
                group_linked_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            warehouse_id,
            group_chat_id,
            group_chat_title,
        )

    # ========================
    # ADMIN USERS
    # ========================
    async def get_admin_by_login(self, login: str) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            SELECT id, login, password_hash, full_name, is_active, last_login_at, created_at, updated_at
            FROM admin_users
            WHERE login = $1
            """,
            login.strip(),
        )

    async def get_admin_by_id(self, admin_id: int) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            SELECT id, login, password_hash, full_name, is_active, last_login_at, created_at, updated_at
            FROM admin_users
            WHERE id = $1
            """,
            admin_id,
        )

    async def update_admin_last_login(self, admin_id: int) -> None:
        await self.execute(
            """
            UPDATE admin_users
            SET last_login_at = NOW(), updated_at = NOW()
            WHERE id = $1
            """,
            admin_id,
        )

    async def update_admin_login(self, *, admin_id: int, login: str) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            UPDATE admin_users
            SET login = $2, updated_at = NOW()
            WHERE id = $1
            RETURNING id, login, password_hash, full_name, is_active, last_login_at, created_at, updated_at
            """,
            admin_id,
            login,
        )

    async def update_admin_password_hash(
        self,
        *,
        admin_id: int,
        password_hash: str,
    ) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            UPDATE admin_users
            SET password_hash = $2, updated_at = NOW()
            WHERE id = $1
            RETURNING id, login, password_hash, full_name, is_active, last_login_at, created_at, updated_at
            """,
            admin_id,
            password_hash,
        )

    # ========================
    # REQUESTS
    # ========================
    async def create_request(
        self,
        *,
        user_id: int,
        operation_type: str,
        branch: str,
        warehouse: str,
        branch_id: int | None = None,
        warehouse_id: int | None = None,
        transfer_type: str | None = None,
        from_branch_id: int | None = None,
        to_branch_id: int | None = None,
        from_warehouse_id: int | None = None,
        to_warehouse_id: int | None = None,
        transfer_kind: str | None = None,
        source_branch: str | None = None,
        source_branch_id: int | None = None,
        source_warehouse: str | None = None,
        source_warehouse_id: int | None = None,
        supplier_name: str | None = None,
        request_date: Any | None = None,
        comment: str | None = None,
        category: str | None = None,
        info_text: str | None = None,
        product_name: str | None = None,
        quantity: str | None = None,
        notification_status: str = "sent",
        photos: list[str | dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        pool = self._require_pool()

        async with pool.acquire() as connection:
            async with connection.transaction():
                inserted = await connection.fetchrow(
                    """
                    INSERT INTO requests (
                        operation_type,
                        branch,
                        warehouse,
                        branch_id,
                        warehouse_id,
                        transfer_type,
                        from_branch_id,
                        to_branch_id,
                        from_warehouse_id,
                        to_warehouse_id,
                        transfer_kind,
                        source_branch,
                        source_branch_id,
                        source_warehouse,
                        source_warehouse_id,
                        supplier_name,
                        date,
                        comment,
                        category,
                        info_text,
                        product_name,
                        quantity,
                        status,
                        notification_status,
                        source,
                        completed_at,
                        user_id,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                        $21, $22, 'completed', $23, 'bot', NOW(), $24, NOW(), NOW()
                    )
                    RETURNING *
                    """,
                    operation_type,
                    branch,
                    warehouse,
                    branch_id,
                    warehouse_id,
                    transfer_type,
                    from_branch_id,
                    to_branch_id,
                    from_warehouse_id,
                    to_warehouse_id,
                    transfer_kind,
                    source_branch,
                    source_branch_id,
                    source_warehouse,
                    source_warehouse_id,
                    supplier_name,
                    request_date,
                    comment,
                    category,
                    info_text,
                    product_name,
                    quantity,
                    notification_status,
                    user_id,
                )
                if inserted is None:
                    raise RuntimeError("Failed to create request")

                request_id = int(inserted["id"])
                request_code = _request_code(
                    operation_type=operation_type,
                    request_id=request_id,
                    created_at=inserted["created_at"],
                )

                updated_request = await connection.fetchrow(
                    """
                    UPDATE requests
                    SET code = $2, updated_at = NOW()
                    WHERE id = $1
                    RETURNING *
                    """,
                    request_id,
                    request_code,
                )
                if updated_request is None:
                    raise RuntimeError("Failed to finalize request code")

                photo_rows: list[tuple[Any, ...]] = []
                for index, photo in enumerate(photos or []):
                    if isinstance(photo, str):
                        file_id = photo
                        unique_id = None
                        width = None
                        height = None
                        file_size = None
                    else:
                        file_id = photo.get("telegram_file_id")
                        if not file_id:
                            continue
                        unique_id = photo.get("telegram_file_unique_id")
                        width = photo.get("width")
                        height = photo.get("height")
                        file_size = photo.get("file_size")

                    photo_rows.append(
                        (
                            request_id,
                            str(file_id),
                            unique_id,
                            width,
                            height,
                            file_size,
                            user_id,
                            index,
                        )
                    )

                if photo_rows:
                    await connection.executemany(
                        """
                        INSERT INTO request_photos (
                            request_id,
                            telegram_file_id,
                            telegram_file_unique_id,
                            width,
                            height,
                            file_size,
                            uploaded_by_user_id,
                            sort_order
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        photo_rows,
                    )

        return dict(updated_request)

    async def update_request_notification_status(
        self,
        *,
        request_id: int,
        notification_status: str,
    ) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            UPDATE requests
            SET notification_status = $2, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            request_id,
            notification_status,
        )

    async def get_request_photo_by_id(self, photo_id: int) -> dict[str, Any] | None:
        return await self.fetchrow(
            """
            SELECT
                rp.id,
                rp.request_id,
                rp.telegram_file_id,
                rp.telegram_file_unique_id,
                rp.width,
                rp.height,
                rp.file_size,
                rp.uploaded_by_user_id,
                rp.sort_order,
                rp.created_at,
                r.code AS operation_code
            FROM request_photos rp
            JOIN requests r ON r.id = rp.request_id
            WHERE rp.id = $1
            """,
            photo_id,
        )

    # ========================
    # LEGACY ADMIN HELPERS
    # ========================
    async def list_users(self, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self.fetch(
            """
            SELECT id, telegram_id, name, role, language, created_at, updated_at
            FROM users
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )

    async def list_requests(
        self,
        limit: int,
        offset: int,
        operation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                r.id,
                r.code,
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
        query += f" LIMIT ${len(params) - 1} OFFSET ${len(params)}"
        return await self.fetch(query, *params)

    async def list_logs(
        self,
        limit: int,
        offset: int,
        level: str | None = None,
    ) -> list[dict[str, Any]]:
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
        query += f" LIMIT ${len(params) - 1} OFFSET ${len(params)}"
        return await self.fetch(query, *params)

    async def get_stats(self) -> dict[str, Any]:
        row = await self.fetchrow(
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
        return row or {}
