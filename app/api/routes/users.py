from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Path, Query

from app.api.dependencies import get_current_admin, get_db
from app.api.excel_export import excel_response
from app.api.responses import ok, paginated
from app.db.database import Database
from app.services.admin_service import AdminService

router = APIRouter(prefix="/api/v1/users", tags=["users"], dependencies=[Depends(get_current_admin)])


@router.get("")
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    items, total = await service.list_users(
        page=page,
        page_size=page_size,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )
    return paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/export")
async def export_users(
    search: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Database = Depends(get_db),
):
    service = AdminService(db)
    rows = await service.export_users(
        search=search,
        date_from=date_from,
        date_to=date_to,
    )
    return excel_response(
        filename="users.xlsx",
        columns=[
            ("Идентификатор", "id"),
            ("Телеграм ИД", "telegram_id"),
            ("Имя", "name"),
            ("Имя пользователя", "username"),
            ("Телефон", "phone_number"),
            ("Язык", "language"),
            ("Дата создания", "created_at"),
            ("Последний визит", "last_seen_at"),
            ("Операции", "operations_total"),
            ("Приходы", "arrivals_total"),
            ("Перемещения", "transfers_total"),
            ("Изображения", "images_total"),
        ],
        rows=rows,
    )


@router.get("/{user_id}")
async def user_detail(
    user_id: int = Path(..., ge=1),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    return ok(await service.get_user_detail(user_id))


@router.get("/{user_id}/operations")
async def user_operations(
    user_id: int = Path(..., ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    operation_type: str | None = Query(default=None, pattern="^(arrival|transfer)$"),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    items, total = await service.list_user_operations(
        user_id=user_id,
        page=page,
        page_size=page_size,
        operation_type=operation_type,
    )
    return paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/{user_id}/activity")
async def user_activity(
    user_id: int = Path(..., ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    items, total = await service.list_user_activity(user_id=user_id, page=page, page_size=page_size)
    return paginated(items=items, total=total, page=page, page_size=page_size)
