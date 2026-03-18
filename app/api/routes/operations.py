from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, Path, Query

from app.api.excel_export import excel_response
from app.api.dependencies import get_current_admin, get_db
from app.api.responses import ok, paginated
from app.db.database import Database
from app.services.admin_service import AdminService
from typing import Any

router = APIRouter(prefix="/api/v1/operations", tags=["operations"], dependencies=[Depends(get_current_admin)])

OPERATION_TYPE_LABELS = {
    "arrival": "Приход",
    "transfer": "Перемещение",
}

STATUS_LABELS = {
    "completed": "Завершено",
    "draft": "Черновик",
    "failed": "Ошибка",
    "deleted": "Удалено",
}

NOTIFICATION_STATUS_LABELS = {
    "sent": "Отправлено",
    "failed": "Не отправлено",
}

TRANSFER_TYPE_LABELS = {
    "warehouse": "Между складами",
    "branch": "Между филиалами",
}


def _extract_line_items(row: dict[str, Any]) -> list[dict[str, str]]:
    raw_items = row.get("line_items") or []
    if isinstance(raw_items, str):
        try:
            raw_items = json.loads(raw_items)
        except json.JSONDecodeError:
            raw_items = []

    if not isinstance(raw_items, list):
        return []

    line_items: list[dict[str, str]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue

        product_name = str(raw_item.get("product_name") or "").strip()
        quantity = str(raw_item.get("quantity") or "").strip()
        unit_price = str(raw_item.get("unit_price") or "").strip()
        if not product_name or not quantity:
            continue

        item = {
            "product_name": product_name,
            "quantity": quantity,
        }
        if unit_price:
            item["unit_price"] = unit_price
        line_items.append(item)
    return line_items


def _format_line_items_summary(row: dict[str, Any], *, separator: str = "\n") -> str:
    line_items = _extract_line_items(row)
    if line_items:
        return separator.join(
            f"{item['product_name']}: {item['quantity']}*{item['unit_price']}"
            if item.get("unit_price")
            else f"{item['product_name']}: {item['quantity']}"
            for item in line_items
        )

    product_name = str(row.get("product_name") or "").strip()
    quantity = str(row.get("quantity") or "").strip()
    if product_name and quantity:
        return f"{product_name}: {quantity}"
    if product_name:
        return product_name
    return "Нет данных"


async def _list_operations(
    *,
    db: Database,
    page: int,
    page_size: int,
    operation_type: str | None = None,
    search: str | None = None,
    branch_id: int | None = None,
    warehouse_id: int | None = None,
    transfer_type: str | None = None,
    user_id: int | None = None,
    user_query: str | None = None,
    product_name: str | None = None,
    status: str | None = None,
    with_images: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    service = AdminService(db)
    items, total = await service.list_operations(
        page=page,
        page_size=page_size,
        filters={
            "operation_type": operation_type,
            "search": search,
            "branch_id": branch_id,
            "warehouse_id": warehouse_id,
            "transfer_type": transfer_type,
            "user_id": user_id,
            "user_query": user_query,
            "product_name": product_name,
            "status": status,
            "with_images": with_images,
            "date_from": date_from,
            "date_to": date_to,
        },
    )
    for item in items:
        item["line_items"] = _extract_line_items(item)
    return paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("")
async def list_operations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None),
    branch_id: int | None = Query(default=None, ge=1),
    warehouse_id: int | None = Query(default=None, ge=1),
    transfer_type: str | None = Query(default=None, pattern="^(warehouse|branch)$"),
    user_id: int | None = Query(default=None, ge=1),
    user_query: str | None = Query(default=None),
    product_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    with_images: bool = Query(default=False),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Database = Depends(get_db),
) -> dict:
    return await _list_operations(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        transfer_type=transfer_type,
        user_id=user_id,
        user_query=user_query,
        product_name=product_name,
        status=status,
        with_images=with_images,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/arrivals")
async def list_arrivals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None),
    branch_id: int | None = Query(default=None, ge=1),
    warehouse_id: int | None = Query(default=None, ge=1),
    transfer_type: str | None = Query(default=None, pattern="^(warehouse|branch)$"),
    user_id: int | None = Query(default=None, ge=1),
    user_query: str | None = Query(default=None),
    product_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    with_images: bool = Query(default=False),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Database = Depends(get_db),
) -> dict:
    return await _list_operations(
        db=db,
        page=page,
        page_size=page_size,
        operation_type="arrival",
        search=search,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        transfer_type=transfer_type,
        user_id=user_id,
        user_query=user_query,
        product_name=product_name,
        status=status,
        with_images=with_images,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/transfers")
async def list_transfers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None),
    branch_id: int | None = Query(default=None, ge=1),
    warehouse_id: int | None = Query(default=None, ge=1),
    transfer_type: str | None = Query(default=None, pattern="^(warehouse|branch)$"),
    user_id: int | None = Query(default=None, ge=1),
    user_query: str | None = Query(default=None),
    product_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    with_images: bool = Query(default=False),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Database = Depends(get_db),
) -> dict:
    return await _list_operations(
        db=db,
        page=page,
        page_size=page_size,
        operation_type="transfer",
        search=search,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        transfer_type=transfer_type,
        user_id=user_id,
        user_query=user_query,
        product_name=product_name,
        status=status,
        with_images=with_images,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/export")
async def export_operations(
    mode: str = Query(default="all", pattern="^(all|arrival|transfer)$"),
    search: str | None = Query(default=None),
    branch_id: int | None = Query(default=None, ge=1),
    warehouse_id: int | None = Query(default=None, ge=1),
    transfer_type: str | None = Query(default=None, pattern="^(warehouse|branch)$"),
    user_id: int | None = Query(default=None, ge=1),
    user_query: str | None = Query(default=None),
    product_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    with_images: bool = Query(default=False),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Database = Depends(get_db),
):
    service = AdminService(db)
    operation_type = None if mode == "all" else mode
    rows = await service.export_operations(
        filters={
            "operation_type": operation_type,
            "search": search,
            "branch_id": branch_id,
            "warehouse_id": warehouse_id,
            "transfer_type": transfer_type,
            "user_id": user_id,
            "user_query": user_query,
            "product_name": product_name,
            "status": status,
            "with_images": with_images,
            "date_from": date_from,
            "date_to": date_to,
        }
    )
    normalized_rows = []
    for row in rows:
        normalized = dict(row)
        normalized["line_items"] = _extract_line_items(normalized)
        normalized["line_items_summary"] = _format_line_items_summary(normalized, separator="; ")
        normalized["operation_type"] = OPERATION_TYPE_LABELS.get(normalized.get("operation_type"), "Операция")
        normalized["status"] = STATUS_LABELS.get(normalized.get("status"), "Неизвестно")
        normalized["notification_status"] = NOTIFICATION_STATUS_LABELS.get(
            normalized.get("notification_status"),
            "Неизвестно",
        )
        normalized["transfer_type"] = TRANSFER_TYPE_LABELS.get(
            normalized.get("transfer_type"),
            "Не указано",
        )
        normalized_rows.append(normalized)
    return excel_response(
        filename=f"operations-{mode}.xlsx",
        columns=[
            ("Идентификатор", "id"),
            ("Код", "code"),
            ("Тип", "operation_type"),
            ("Вид перемещения", "transfer_type"),
            ("Статус", "status"),
            ("Статус уведомления", "notification_status"),
            ("Филиал", "branch_name"),
            ("Склад", "warehouse_name"),
            ("Источник филиал", "source_branch_name"),
            ("Источник склад", "source_warehouse_name"),
            ("Получатель филиал", "destination_branch_name"),
            ("Получатель склад", "destination_warehouse_name"),
            ("Номенклатура", "line_items_summary"),
            ("Продукт", "product_name"),
            ("Количество", "quantity"),
            ("Поставщик", "supplier_name"),
            ("Комментарий", "comment"),
            ("Инфо текст", "info_text"),
            ("Дата документа", "date"),
            ("Пользователь", "user_name"),
            ("Имя пользователя", "user_username"),
            ("Телефон", "user_phone"),
            ("Идентификатор Телеграм", "user_telegram_id"),
            ("Изображений", "photos_count"),
            ("Создано", "created_at"),
            ("Завершено", "completed_at"),
        ],
        rows=normalized_rows,
    )


@router.get("/{operation_id}/items")
async def operation_items(
    operation_id: int = Path(..., ge=1),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    detail = await service.get_operation_detail(operation_id)
    return ok(_extract_line_items(detail))


@router.get("/{operation_id}")
async def operation_detail(
    operation_id: int = Path(..., ge=1),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    detail = await service.get_operation_detail(operation_id)
    detail["line_items"] = _extract_line_items(detail)
    return ok(detail)


@router.delete("/{operation_id}")
async def delete_operation(
    operation_id: int = Path(..., ge=1),
    db: Database = Depends(get_db),
    admin: dict[str, Any] = Depends(get_current_admin),
) -> dict:
    service = AdminService(db)
    return ok(await service.delete_operation(operation_id, admin["id"]))
