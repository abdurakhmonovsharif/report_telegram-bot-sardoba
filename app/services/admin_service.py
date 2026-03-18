from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.api.errors import APIError
from app.db.database import Database

STATIC_WAREHOUSE_SLUGS = ("bar", "kitchen", "supplies", "meat")


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 200)
    offset = (safe_page - 1) * safe_page_size
    return safe_page_size, offset


class AdminService:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _append(params: list[Any], value: Any) -> str:
        params.append(value)
        return f"${len(params)}"

    def _build_user_where(
        self,
        *,
        search: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[Any], str]:
        params: list[Any] = []
        conditions: list[str] = []

        if search and search.strip():
            token = f"%{search.strip()}%"
            placeholder = self._append(params, token)
            conditions.append(
                f"""
                (
                    COALESCE(u.name, '') ILIKE {placeholder}
                    OR COALESCE(u.username, '') ILIKE {placeholder}
                    OR COALESCE(u.phone_number, '') ILIKE {placeholder}
                    OR u.telegram_id::TEXT ILIKE {placeholder}
                )
                """
            )

        if date_from:
            conditions.append(f"u.created_at::DATE >= {self._append(params, date_from)}")

        if date_to:
            conditions.append(f"u.created_at::DATE <= {self._append(params, date_to)}")

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return params, where_sql

    def _build_operation_where(self, *, filters: dict[str, Any] | None = None) -> tuple[list[Any], str]:
        filters = filters or {}
        params: list[Any] = []
        conditions: list[str] = []

        if operation_type := filters.get("operation_type"):
            conditions.append(f"r.operation_type = {self._append(params, operation_type)}")
        if transfer_type := filters.get("transfer_type"):
            conditions.append(
                f"COALESCE(r.transfer_type, r.transfer_kind) = {self._append(params, transfer_type)}"
            )
        if branch_id := filters.get("branch_id"):
            conditions.append(f"r.branch_id = {self._append(params, int(branch_id))}")
        if warehouse_id := filters.get("warehouse_id"):
            conditions.append(f"r.warehouse_id = {self._append(params, int(warehouse_id))}")
        if user_id := filters.get("user_id"):
            conditions.append(f"r.user_id = {self._append(params, int(user_id))}")
        if status := filters.get("status"):
            conditions.append(f"r.status = {self._append(params, status)}")
        if date_from := filters.get("date_from"):
            conditions.append(f"r.created_at::DATE >= {self._append(params, date_from)}")
        if date_to := filters.get("date_to"):
            conditions.append(f"r.created_at::DATE <= {self._append(params, date_to)}")
        if product_name := filters.get("product_name"):
            token = product_name.strip()
            if token:
                conditions.append(f"COALESCE(r.product_name, '') ILIKE {self._append(params, f'%{token}%')}")
        if filters.get("with_images"):
            conditions.append("EXISTS (SELECT 1 FROM request_photos rp2 WHERE rp2.request_id = r.id)")
        if user_query := filters.get("user_query"):
            token = user_query.strip()
            if token:
                placeholder = self._append(params, f"%{token}%")
                conditions.append(
                    f"""
                    (
                        COALESCE(u.name, '') ILIKE {placeholder}
                        OR COALESCE(u.username, '') ILIKE {placeholder}
                        OR COALESCE(u.phone_number, '') ILIKE {placeholder}
                        OR u.telegram_id::TEXT ILIKE {placeholder}
                    )
                    """
                )

        if search := filters.get("search"):
            token = search.strip()
            if token:
                placeholder = self._append(params, f"%{token}%")
                conditions.append(
                    f"""
                    (
                        COALESCE(r.code, '') ILIKE {placeholder}
                        OR COALESCE(r.product_name, '') ILIKE {placeholder}
                        OR COALESCE(r.comment, '') ILIKE {placeholder}
                        OR COALESCE(r.info_text, '') ILIKE {placeholder}
                        OR COALESCE(r.supplier_name, '') ILIKE {placeholder}
                        OR COALESCE(u.phone_number, '') ILIKE {placeholder}
                        OR u.telegram_id::TEXT ILIKE {placeholder}
                        OR COALESCE(u.name, '') ILIKE {placeholder}
                    )
                    """
                )

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return params, where_sql

    def _build_audit_where(
        self,
        *,
        actor_type: str | None = None,
        actor_id: int | None = None,
        action_type: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[Any], str]:
        params: list[Any] = []
        conditions: list[str] = []

        if actor_type:
            conditions.append(f"al.actor_type = {self._append(params, actor_type)}")
        if actor_id:
            placeholder = self._append(params, actor_id)
            conditions.append(f"(al.actor_user_id = {placeholder} OR al.actor_admin_id = {placeholder})")
        if action_type:
            conditions.append(f"al.action_type = {self._append(params, action_type)}")
        if entity_type:
            conditions.append(f"al.entity_type = {self._append(params, entity_type)}")
        if entity_id:
            conditions.append(f"al.entity_id = {self._append(params, entity_id)}")
        if date_from:
            conditions.append(f"al.created_at::DATE >= {self._append(params, date_from)}")
        if date_to:
            conditions.append(f"al.created_at::DATE <= {self._append(params, date_to)}")

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return params, where_sql

    async def list_users(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        limit, offset = _pagination(page, page_size)
        params, where_sql = self._build_user_where(
            search=search,
            date_from=date_from,
            date_to=date_to,
        )

        count_query = f"SELECT COUNT(*)::INT FROM users u {where_sql}"
        total = int(await self.db.fetchval(count_query, *params) or 0)

        params.extend([limit, offset])
        items_query = f"""
            SELECT
                u.id,
                u.telegram_id,
                u.name,
                u.first_name,
                u.last_name,
                u.username,
                u.phone_number,
                u.language,
                u.avatar_file_id,
                u.created_at,
                u.updated_at,
                u.first_seen_at,
                u.last_seen_at,
                COUNT(r.id)::INT AS operations_total,
                COUNT(r.id) FILTER (WHERE r.operation_type = 'arrival')::INT AS arrivals_total,
                COUNT(r.id) FILTER (WHERE r.operation_type = 'transfer')::INT AS transfers_total,
                COUNT(rp.id)::INT AS images_total
            FROM users u
            LEFT JOIN requests r ON r.user_id = u.id
            LEFT JOIN request_photos rp ON rp.request_id = r.id
            {where_sql}
            GROUP BY u.id
            ORDER BY u.last_seen_at DESC NULLS LAST, u.created_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """
        items = await self.db.fetch(items_query, *params)
        return items, total

    async def export_users(
        self,
        *,
        search: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        params, where_sql = self._build_user_where(
            search=search,
            date_from=date_from,
            date_to=date_to,
        )
        return await self.db.fetch(
            f"""
            SELECT
                u.id,
                u.name,
                u.first_name,
                u.last_name,
                u.username,
                u.phone_number,
                u.telegram_id,
                u.language,
                u.created_at,
                u.first_seen_at,
                u.last_seen_at,
                COUNT(r.id)::INT AS operations_total,
                COUNT(r.id) FILTER (WHERE r.operation_type = 'arrival')::INT AS arrivals_total,
                COUNT(r.id) FILTER (WHERE r.operation_type = 'transfer')::INT AS transfers_total,
                COUNT(rp.id)::INT AS images_total
            FROM users u
            LEFT JOIN requests r ON r.user_id = u.id
            LEFT JOIN request_photos rp ON rp.request_id = r.id
            {where_sql}
            GROUP BY u.id
            ORDER BY u.last_seen_at DESC NULLS LAST, u.created_at DESC
            """,
            *params,
        )

    async def get_user_detail(self, user_id: int) -> dict[str, Any]:
        user = await self.db.fetchrow(
            """
            SELECT
                u.id,
                u.telegram_id,
                u.name,
                u.first_name,
                u.last_name,
                u.username,
                u.phone_number,
                u.language,
                u.avatar_file_id,
                u.avatar_file_unique_id,
                u.avatar_width,
                u.avatar_height,
                u.avatar_file_size,
                u.created_at,
                u.updated_at,
                u.first_seen_at,
                u.last_seen_at,
                COUNT(r.id)::INT AS operations_total,
                COUNT(r.id) FILTER (WHERE r.operation_type = 'arrival')::INT AS arrivals_total,
                COUNT(r.id) FILTER (WHERE r.operation_type = 'transfer')::INT AS transfers_total,
                COUNT(rp.id)::INT AS images_total
            FROM users u
            LEFT JOIN requests r ON r.user_id = u.id
            LEFT JOIN request_photos rp ON rp.request_id = r.id
            WHERE u.id = $1
            GROUP BY u.id
            """,
            user_id,
        )
        if user is None:
            raise APIError(status_code=404, code="user_not_found", message="Пользователь не найден.")

        frequent_branches = await self.db.fetch(
            """
            SELECT r.branch_id, COALESCE(b.admin_name, r.branch) AS name, COUNT(*)::INT AS operations_total
            FROM requests r
            LEFT JOIN branches b ON b.id = r.branch_id
            WHERE r.user_id = $1
            GROUP BY r.branch_id, COALESCE(b.admin_name, r.branch)
            ORDER BY operations_total DESC, name
            LIMIT 10
            """,
            user_id,
        )

        frequent_warehouses = await self.db.fetch(
            """
            SELECT r.warehouse_id, COALESCE(w.name, r.warehouse) AS name, COUNT(*)::INT AS operations_total
            FROM requests r
            LEFT JOIN warehouses w ON w.id = r.warehouse_id
            WHERE r.user_id = $1
            GROUP BY r.warehouse_id, COALESCE(w.name, r.warehouse)
            ORDER BY operations_total DESC, name
            LIMIT 10
            """,
            user_id,
        )

        last_operations = await self.db.fetch(
            """
            SELECT
                r.id,
                r.code,
                r.operation_type,
                COALESCE(b.admin_name, r.branch) AS branch_name,
                COALESCE(w.name, r.warehouse) AS warehouse_name,
                r.product_name,
                r.quantity,
                r.created_at,
                COUNT(rp.id)::INT AS photos_count
            FROM requests r
            LEFT JOIN branches b ON b.id = r.branch_id
            LEFT JOIN warehouses w ON w.id = r.warehouse_id
            LEFT JOIN request_photos rp ON rp.request_id = r.id
            WHERE r.user_id = $1
            GROUP BY
                r.id,
                COALESCE(b.admin_name, r.branch),
                COALESCE(w.name, r.warehouse)
            ORDER BY r.created_at DESC
            LIMIT 20
            """,
            user_id,
        )

        recent_activity = await self.db.fetch(
            """
            SELECT
                id,
                actor_type,
                action_type,
                entity_type,
                entity_id,
                message,
                meta,
                created_at
            FROM audit_logs
            WHERE actor_user_id = $1
            ORDER BY created_at DESC
            LIMIT 50
            """,
            user_id,
        )

        return {
            **user,
            "frequent_branches": frequent_branches,
            "frequent_warehouses": frequent_warehouses,
            "recent_operations": last_operations,
            "recent_activity": recent_activity,
        }

    async def list_user_operations(
        self,
        *,
        user_id: int,
        page: int,
        page_size: int,
        operation_type: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = {"user_id": user_id, "operation_type": operation_type}
        return await self.list_operations(page=page, page_size=page_size, filters=filters)

    async def list_user_activity(
        self,
        *,
        user_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        limit, offset = _pagination(page, page_size)
        total = int(
            await self.db.fetchval(
                "SELECT COUNT(*)::INT FROM audit_logs WHERE actor_user_id = $1",
                user_id,
            )
            or 0
        )
        items = await self.db.fetch(
            """
            SELECT
                id,
                actor_type,
                action_type,
                entity_type,
                entity_id,
                message,
                meta,
                created_at
            FROM audit_logs
            WHERE actor_user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )
        return items, total

    async def list_operations(
        self,
        *,
        page: int,
        page_size: int,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        limit, offset = _pagination(page, page_size)
        params, where_sql = self._build_operation_where(filters=filters)

        total = int(
            await self.db.fetchval(
                f"""
                SELECT COUNT(*)::INT
                FROM requests r
                JOIN users u ON u.id = r.user_id
                {where_sql}
                """,
                *params,
            )
            or 0
        )

        params.extend([limit, offset])
        items = await self.db.fetch(
            f"""
            SELECT
                r.id,
                r.code,
                r.operation_type,
                COALESCE(r.transfer_type, r.transfer_kind) AS transfer_type,
                COALESCE(r.transfer_type, r.transfer_kind) AS transfer_kind,
                r.status,
                r.notification_status,
                r.product_name,
                r.quantity,
                r.comment,
                r.info_text,
                r.supplier_name,
                r.created_at,
                r.completed_at,
                r.user_id,
                u.name AS user_name,
                u.phone_number AS user_phone,
                u.telegram_id AS user_telegram_id,
                COALESCE(tb.admin_name, b.admin_name, r.branch) AS branch_name,
                COALESCE(tw.name, w.name, r.warehouse) AS warehouse_name,
                COALESCE(fb.admin_name, r.source_branch) AS source_branch_name,
                COALESCE(fw.name, r.source_warehouse) AS source_warehouse_name,
                COALESCE(tb.admin_name, b.admin_name, r.branch) AS destination_branch_name,
                COALESCE(tw.name, w.name, r.warehouse) AS destination_warehouse_name,
                COUNT(rp.id)::INT AS photos_count
            FROM requests r
            JOIN users u ON u.id = r.user_id
            LEFT JOIN branches b ON b.id = r.branch_id
            LEFT JOIN warehouses w ON w.id = r.warehouse_id
            LEFT JOIN branches fb ON fb.id = COALESCE(r.from_branch_id, r.source_branch_id)
            LEFT JOIN branches tb ON tb.id = COALESCE(r.to_branch_id, r.branch_id)
            LEFT JOIN warehouses fw ON fw.id = COALESCE(r.from_warehouse_id, r.source_warehouse_id)
            LEFT JOIN warehouses tw ON tw.id = COALESCE(r.to_warehouse_id, r.warehouse_id)
            LEFT JOIN request_photos rp ON rp.request_id = r.id
            {where_sql}
            GROUP BY
                r.id,
                u.id,
                COALESCE(r.transfer_type, r.transfer_kind),
                COALESCE(tb.admin_name, b.admin_name, r.branch),
                COALESCE(tw.name, w.name, r.warehouse),
                COALESCE(fb.admin_name, r.source_branch),
                COALESCE(fw.name, r.source_warehouse)
            ORDER BY r.created_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """,
            *params,
        )
        return items, total

    async def export_operations(
        self,
        *,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        params, where_sql = self._build_operation_where(filters=filters)
        return await self.db.fetch(
            f"""
            SELECT
                r.id,
                r.code,
                r.operation_type,
                COALESCE(r.transfer_type, r.transfer_kind) AS transfer_type,
                COALESCE(r.transfer_type, r.transfer_kind) AS transfer_kind,
                r.status,
                r.notification_status,
                COALESCE(tb.admin_name, b.admin_name, r.branch) AS branch_name,
                COALESCE(tw.name, w.name, r.warehouse) AS warehouse_name,
                COALESCE(fb.admin_name, r.source_branch) AS source_branch_name,
                COALESCE(fw.name, r.source_warehouse) AS source_warehouse_name,
                COALESCE(tb.admin_name, b.admin_name, r.branch) AS destination_branch_name,
                COALESCE(tw.name, w.name, r.warehouse) AS destination_warehouse_name,
                r.product_name,
                r.quantity,
                r.supplier_name,
                r.comment,
                r.info_text,
                r.date,
                u.name AS user_name,
                u.username AS user_username,
                u.phone_number AS user_phone,
                u.telegram_id AS user_telegram_id,
                r.created_at,
                r.completed_at,
                COUNT(rp.id)::INT AS photos_count
            FROM requests r
            JOIN users u ON u.id = r.user_id
            LEFT JOIN branches b ON b.id = r.branch_id
            LEFT JOIN warehouses w ON w.id = r.warehouse_id
            LEFT JOIN branches fb ON fb.id = COALESCE(r.from_branch_id, r.source_branch_id)
            LEFT JOIN branches tb ON tb.id = COALESCE(r.to_branch_id, r.branch_id)
            LEFT JOIN warehouses fw ON fw.id = COALESCE(r.from_warehouse_id, r.source_warehouse_id)
            LEFT JOIN warehouses tw ON tw.id = COALESCE(r.to_warehouse_id, r.warehouse_id)
            LEFT JOIN request_photos rp ON rp.request_id = r.id
            {where_sql}
            GROUP BY
                r.id,
                u.id,
                COALESCE(r.transfer_type, r.transfer_kind),
                COALESCE(tb.admin_name, b.admin_name, r.branch),
                COALESCE(tw.name, w.name, r.warehouse),
                COALESCE(fb.admin_name, r.source_branch),
                COALESCE(fw.name, r.source_warehouse)
            ORDER BY r.created_at DESC
            """,
            *params,
        )

    async def get_operation_detail(self, operation_id: int) -> dict[str, Any]:
        operation = await self.db.fetchrow(
            """
            SELECT
                r.id,
                r.code,
                r.operation_type,
                COALESCE(r.transfer_type, r.transfer_kind) AS transfer_type,
                COALESCE(r.transfer_type, r.transfer_kind) AS transfer_kind,
                r.status,
                r.notification_status,
                COALESCE(r.to_branch_id, r.branch_id) AS branch_id,
                COALESCE(r.to_warehouse_id, r.warehouse_id) AS warehouse_id,
                COALESCE(r.from_branch_id, r.source_branch_id) AS from_branch_id,
                COALESCE(r.to_branch_id, r.branch_id) AS to_branch_id,
                COALESCE(r.from_warehouse_id, r.source_warehouse_id) AS from_warehouse_id,
                COALESCE(r.to_warehouse_id, r.warehouse_id) AS to_warehouse_id,
                COALESCE(r.from_branch_id, r.source_branch_id) AS source_branch_id,
                COALESCE(r.from_warehouse_id, r.source_warehouse_id) AS source_warehouse_id,
                COALESCE(tb.admin_name, b.admin_name, r.branch) AS branch_name,
                COALESCE(tw.name, w.name, r.warehouse) AS warehouse_name,
                COALESCE(fb.admin_name, r.source_branch) AS source_branch_name,
                COALESCE(fw.name, r.source_warehouse) AS source_warehouse_name,
                COALESCE(tb.admin_name, b.admin_name, r.branch) AS destination_branch_name,
                COALESCE(tw.name, w.name, r.warehouse) AS destination_warehouse_name,
                r.product_name,
                r.quantity,
                r.category,
                r.info_text,
                r.comment,
                r.supplier_name,
                r.date,
                r.source,
                r.created_at,
                r.completed_at,
                r.updated_at,
                u.id AS user_id,
                u.name AS user_name,
                u.phone_number AS user_phone,
                u.username AS user_username,
                u.telegram_id AS user_telegram_id,
                u.avatar_file_id AS user_avatar_file_id
            FROM requests r
            JOIN users u ON u.id = r.user_id
            LEFT JOIN branches b ON b.id = r.branch_id
            LEFT JOIN warehouses w ON w.id = r.warehouse_id
            LEFT JOIN branches fb ON fb.id = COALESCE(r.from_branch_id, r.source_branch_id)
            LEFT JOIN branches tb ON tb.id = COALESCE(r.to_branch_id, r.branch_id)
            LEFT JOIN warehouses fw ON fw.id = COALESCE(r.from_warehouse_id, r.source_warehouse_id)
            LEFT JOIN warehouses tw ON tw.id = COALESCE(r.to_warehouse_id, r.warehouse_id)
            WHERE r.id = $1
            """,
            operation_id,
        )
        if operation is None:
            raise APIError(status_code=404, code="operation_not_found", message="Операция не найдена.")

        photos = await self.db.fetch(
            """
            SELECT
                id,
                telegram_file_id,
                telegram_file_unique_id,
                width,
                height,
                file_size,
                uploaded_by_user_id,
                created_at,
                sort_order
            FROM request_photos
            WHERE request_id = $1
            ORDER BY sort_order, id
            """,
            operation_id,
        )
        audit = await self.db.fetch(
            """
            SELECT
                id,
                actor_type,
                actor_user_id,
                actor_admin_id,
                action_type,
                entity_type,
                entity_id,
                message,
                meta,
                created_at
            FROM audit_logs
            WHERE entity_type = 'request' AND entity_id = $1
            ORDER BY created_at DESC
            """,
            operation_id,
        )
        operation["photos"] = photos
        operation["audit"] = audit
        return operation

    async def delete_operation(self, operation_id: int, admin_id: int) -> dict[str, Any]:
        result = await self.db.fetchrow(
            """
            UPDATE requests
            SET status = 'deleted', updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            operation_id,
        )
        if not result:
            raise APIError(status_code=404, code="operation_not_found", message="Операция не найдена.")

        await self.db.log_audit(
            actor_type="admin",
            actor_admin_id=admin_id,
            action_type="delete",
            entity_type="request",
            entity_id=operation_id,
            message="Операция удалена (переведена в статус удалено)",
        )

        return result

    async def list_warehouses(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        limit, offset = _pagination(page, page_size)
        params: list[Any] = []
        conditions: list[str] = []

        if search:
            conditions.append(f"name ILIKE {self._append(params, f'%{search.strip()}%')}")
        if is_active is not None:
            conditions.append(f"is_active = {self._append(params, is_active)}")
        conditions.append(f"slug = ANY({self._append(params, list(STATIC_WAREHOUSE_SLUGS))}::TEXT[])")

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        total = int(await self.db.fetchval(f"SELECT COUNT(*)::INT FROM warehouses {where_sql}", *params) or 0)
        params.extend([limit, offset])
        items = await self.db.fetch(
            f"""
            SELECT
                w.id,
                w.slug,
                w.name,
                w.description,
                w.is_active,
                w.sort_order,
                w.group_chat_id,
                w.group_chat_title,
                w.group_linked_at,
                w.created_at,
                w.updated_at,
                COUNT(r.id)::INT AS operations_total
            FROM warehouses w
            LEFT JOIN requests r ON r.warehouse_id = w.id
            {where_sql}
            GROUP BY w.id
            ORDER BY w.sort_order, w.id
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """,
            *params,
        )
        return items, total

    async def create_warehouse(
        self,
        *,
        name: str,
        description: str | None,
        is_active: bool,
    ) -> dict[str, Any]:
        trimmed = name.strip()
        if not trimmed:
            raise APIError(status_code=400, code="invalid_name", message="Название склада обязательно.")

        exists = await self.db.fetchval(
            "SELECT id FROM warehouses WHERE LOWER(name) = LOWER($1)",
            trimmed,
        )
        if exists:
            raise APIError(status_code=409, code="warehouse_exists", message="Склад с таким названием уже существует.")

        created = await self.db.fetchrow(
            """
            INSERT INTO warehouses (name, description, is_active)
            VALUES ($1, $2, $3)
            RETURNING id, name, description, is_active, sort_order, created_at, updated_at
            """,
            trimmed,
            description.strip() if description else None,
            is_active,
        )
        if created is None:
            raise APIError(status_code=500, code="warehouse_create_failed", message="Не удалось создать склад.")
        return created

    async def update_warehouse(
        self,
        *,
        warehouse_id: int,
        name: str,
        description: str | None,
        is_active: bool,
    ) -> dict[str, Any]:
        existing = await self.db.get_warehouse_by_id(warehouse_id)
        if existing is None:
            raise APIError(status_code=404, code="warehouse_not_found", message="Склад не найден.")

        trimmed = name.strip()
        if not trimmed:
            raise APIError(status_code=400, code="invalid_name", message="Название склада обязательно.")

        duplicate = await self.db.fetchval(
            "SELECT id FROM warehouses WHERE LOWER(name) = LOWER($1) AND id <> $2",
            trimmed,
            warehouse_id,
        )
        if duplicate:
            raise APIError(status_code=409, code="warehouse_exists", message="Склад с таким названием уже существует.")

        updated = await self.db.fetchrow(
            """
            UPDATE warehouses
            SET
                name = $2,
                description = $3,
                is_active = $4,
                updated_at = NOW()
            WHERE id = $1
            RETURNING id, name, description, is_active, sort_order, created_at, updated_at
            """,
            warehouse_id,
            trimmed,
            description.strip() if description else None,
            is_active,
        )
        if updated is None:
            raise APIError(status_code=500, code="warehouse_update_failed", message="Не удалось обновить склад.")
        return updated

    async def list_branches(self) -> list[dict[str, Any]]:
        return await self.db.fetch(
            """
            SELECT
                b.id,
                b.code,
                b.slug,
                b.bot_name,
                b.admin_name,
                b.sort_order,
                b.is_active,
                b.created_at,
                b.updated_at,
                COUNT(r.id)::INT AS operations_total
            FROM branches b
            LEFT JOIN requests r ON r.branch_id = b.id
            GROUP BY b.id
            ORDER BY b.sort_order, b.id
            """
        )

    async def get_branch_detail(self, branch_id: int) -> dict[str, Any]:
        branch = await self.db.fetchrow(
            """
            SELECT
                b.id,
                b.code,
                b.slug,
                b.bot_name,
                b.admin_name,
                b.sort_order,
                b.is_active,
                b.created_at,
                b.updated_at,
                COUNT(r.id)::INT AS operations_total,
                COUNT(r.id) FILTER (WHERE r.operation_type = 'arrival')::INT AS arrivals_total,
                COUNT(r.id) FILTER (WHERE r.operation_type = 'transfer')::INT AS transfers_total
            FROM branches b
            LEFT JOIN requests r ON r.branch_id = b.id
            WHERE b.id = $1
            GROUP BY b.id
            """,
            branch_id,
        )
        if branch is None:
            raise APIError(status_code=404, code="branch_not_found", message="Филиал не найден.")

        top_warehouses = await self.db.fetch(
            """
            SELECT
                COALESCE(w.name, r.warehouse) AS warehouse_name,
                COUNT(*)::INT AS operations_total
            FROM requests r
            LEFT JOIN warehouses w ON w.id = r.warehouse_id
            WHERE r.branch_id = $1
            GROUP BY COALESCE(w.name, r.warehouse)
            ORDER BY operations_total DESC, warehouse_name
            LIMIT 10
            """,
            branch_id,
        )
        branch["top_warehouses"] = top_warehouses
        return branch

    async def get_dashboard_summary(self) -> dict[str, Any]:
        today = datetime.now(timezone.utc).date()
        summary = await self.db.fetchrow(
            """
            SELECT
                (SELECT COUNT(*)::INT FROM users) AS total_users,
                (SELECT COUNT(*)::INT FROM users WHERE last_seen_at::DATE = CURRENT_DATE) AS today_active_users,
                (SELECT COUNT(*)::INT FROM requests WHERE operation_type = 'arrival') AS total_arrivals,
                (SELECT COUNT(*)::INT FROM requests WHERE operation_type = 'transfer') AS total_transfers,
                (SELECT COUNT(*)::INT FROM requests WHERE created_at::DATE = CURRENT_DATE) AS today_operations,
                (SELECT COUNT(*)::INT FROM request_photos) AS total_images,
                (SELECT COUNT(*)::INT FROM requests WHERE EXISTS (SELECT 1 FROM request_photos rp WHERE rp.request_id = requests.id)) AS operations_with_images
            """
        )
        return summary or {"today": today}

    async def get_branch_breakdown(self) -> list[dict[str, Any]]:
        return await self.db.fetch(
            """
            SELECT
                COALESCE(b.admin_name, r.branch) AS branch_name,
                COUNT(*)::INT AS operations_total,
                COUNT(*) FILTER (WHERE r.operation_type = 'arrival')::INT AS arrivals_total,
                COUNT(*) FILTER (WHERE r.operation_type = 'transfer')::INT AS transfers_total
            FROM requests r
            LEFT JOIN branches b ON b.id = r.branch_id
            GROUP BY COALESCE(b.admin_name, r.branch)
            ORDER BY operations_total DESC, branch_name
            """
        )

    async def get_warehouse_breakdown(self) -> list[dict[str, Any]]:
        return await self.db.fetch(
            """
            SELECT
                COALESCE(w.name, r.warehouse) AS warehouse_name,
                COUNT(*)::INT AS operations_total,
                COUNT(*) FILTER (WHERE r.operation_type = 'arrival')::INT AS arrivals_total,
                COUNT(*) FILTER (WHERE r.operation_type = 'transfer')::INT AS transfers_total
            FROM requests r
            LEFT JOIN warehouses w ON w.id = r.warehouse_id
            GROUP BY COALESCE(w.name, r.warehouse)
            ORDER BY operations_total DESC, warehouse_name
            """
        )

    async def get_user_activity_breakdown(self, *, limit: int = 10) -> list[dict[str, Any]]:
        return await self.db.fetch(
            """
            SELECT
                u.id AS user_id,
                u.name AS user_name,
                u.phone_number AS phone_number,
                u.avatar_file_id,
                COUNT(r.id)::INT AS operations_total,
                COUNT(r.id) FILTER (WHERE r.operation_type = 'arrival')::INT AS arrivals_total,
                COUNT(r.id) FILTER (WHERE r.operation_type = 'transfer')::INT AS transfers_total
            FROM users u
            JOIN requests r ON r.user_id = u.id
            GROUP BY u.id
            ORDER BY operations_total DESC, user_name
            LIMIT $1
            """,
            limit,
        )

    async def get_recent_operations(self, *, limit: int = 10) -> list[dict[str, Any]]:
        return await self.db.fetch(
            """
            SELECT
                r.id,
                r.code,
                r.operation_type,
                r.product_name,
                r.quantity,
                COALESCE(b.admin_name, r.branch) AS branch_name,
                COALESCE(w.name, r.warehouse) AS warehouse_name,
                u.name AS user_name,
                r.created_at,
                COUNT(rp.id)::INT AS photos_count
            FROM requests r
            JOIN users u ON u.id = r.user_id
            LEFT JOIN branches b ON b.id = r.branch_id
            LEFT JOIN warehouses w ON w.id = r.warehouse_id
            LEFT JOIN request_photos rp ON rp.request_id = r.id
            GROUP BY
                r.id,
                u.id,
                COALESCE(b.admin_name, r.branch),
                COALESCE(w.name, r.warehouse)
            ORDER BY r.created_at DESC
            LIMIT $1
            """,
            limit,
        )

    async def get_operation_dynamics(
        self,
        *,
        period: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        safe_period = period if period in {"day", "week", "month"} else "day"
        interval = max(days, 1)
        return await self.db.fetch(
            f"""
            SELECT
                TO_CHAR(DATE_TRUNC('{safe_period}', created_at), 'YYYY-MM-DD') AS period_label,
                COUNT(*)::INT AS operations_total,
                COUNT(*) FILTER (WHERE operation_type = 'arrival')::INT AS arrivals_total,
                COUNT(*) FILTER (WHERE operation_type = 'transfer')::INT AS transfers_total
            FROM requests
            WHERE created_at >= NOW() - ($1::INT || ' days')::INTERVAL
            GROUP BY DATE_TRUNC('{safe_period}', created_at)
            ORDER BY DATE_TRUNC('{safe_period}', created_at)
            """,
            interval,
        )

    async def get_top_products(self, *, limit: int = 10) -> list[dict[str, Any]]:
        return await self.db.fetch(
            """
            SELECT
                product_name,
                COUNT(*)::INT AS operations_total,
                COUNT(*) FILTER (WHERE operation_type = 'arrival')::INT AS arrivals_total,
                COUNT(*) FILTER (WHERE operation_type = 'transfer')::INT AS transfers_total
            FROM requests
            WHERE COALESCE(product_name, '') <> ''
            GROUP BY product_name
            ORDER BY operations_total DESC, product_name
            LIMIT $1
            """,
            limit,
        )

    async def get_top_users(self, *, limit: int = 10) -> list[dict[str, Any]]:
        return await self.db.fetch(
            """
            SELECT
                u.id AS user_id,
                u.name AS user_name,
                u.phone_number,
                u.avatar_file_id,
                COUNT(r.id)::INT AS operations_total
            FROM users u
            JOIN requests r ON r.user_id = u.id
            GROUP BY u.id
            ORDER BY operations_total DESC, user_name
            LIMIT $1
            """,
            limit,
        )

    async def get_branch_heatmap(self) -> list[dict[str, Any]]:
        return await self.db.fetch(
            """
            SELECT
                COALESCE(b.admin_name, r.branch) AS branch_name,
                COALESCE(w.name, r.warehouse) AS warehouse_name,
                COUNT(*)::INT AS operations_total
            FROM requests r
            LEFT JOIN branches b ON b.id = r.branch_id
            LEFT JOIN warehouses w ON w.id = r.warehouse_id
            GROUP BY
                COALESCE(b.admin_name, r.branch),
                COALESCE(w.name, r.warehouse)
            ORDER BY branch_name, operations_total DESC, warehouse_name
            """
        )

    async def list_audit_logs(
        self,
        *,
        page: int,
        page_size: int,
        actor_type: str | None = None,
        actor_id: int | None = None,
        action_type: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        limit, offset = _pagination(page, page_size)
        params, where_sql = self._build_audit_where(
            actor_type=actor_type,
            actor_id=actor_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            date_from=date_from,
            date_to=date_to,
        )
        total = int(await self.db.fetchval(f"SELECT COUNT(*)::INT FROM audit_logs al {where_sql}", *params) or 0)

        params.extend([limit, offset])
        items = await self.db.fetch(
            f"""
            SELECT
                al.id,
                al.actor_type,
                al.actor_user_id,
                al.actor_admin_id,
                al.action_type,
                al.entity_type,
                al.entity_id,
                al.message,
                al.meta,
                al.created_at,
                u.name AS actor_user_name,
                au.login AS actor_admin_login
            FROM audit_logs al
            LEFT JOIN users u ON u.id = al.actor_user_id
            LEFT JOIN admin_users au ON au.id = al.actor_admin_id
            {where_sql}
            ORDER BY al.created_at DESC
            LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """,
            *params,
        )
        return items, total

    async def export_audit_logs(
        self,
        *,
        actor_type: str | None = None,
        actor_id: int | None = None,
        action_type: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        params, where_sql = self._build_audit_where(
            actor_type=actor_type,
            actor_id=actor_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            date_from=date_from,
            date_to=date_to,
        )
        return await self.db.fetch(
            f"""
            SELECT
                al.id,
                al.actor_type,
                al.actor_user_id,
                al.actor_admin_id,
                al.action_type,
                al.entity_type,
                al.entity_id,
                al.message,
                al.meta,
                al.created_at,
                u.name AS actor_user_name,
                au.login AS actor_admin_login
            FROM audit_logs al
            LEFT JOIN users u ON u.id = al.actor_user_id
            LEFT JOIN admin_users au ON au.id = al.actor_admin_id
            {where_sql}
            ORDER BY al.created_at DESC
            """,
            *params,
        )
