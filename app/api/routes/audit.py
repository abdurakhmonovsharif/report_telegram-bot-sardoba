from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.excel_export import excel_response
from app.api.dependencies import get_current_admin, get_db
from app.api.responses import ok, paginated
from app.db.database import Database
from app.services.admin_service import AdminService

router = APIRouter(prefix="/api/v1/audit", tags=["audit"], dependencies=[Depends(get_current_admin)])

ACTOR_TYPE_LABELS = {
    "telegram_user": "Пользователь Телеграм",
    "admin": "Администратор",
    "system": "Система",
}

ENTITY_TYPE_LABELS = {
    "user": "Пользователь",
    "request": "Операция",
    "warehouse": "Склад",
    "admin_user": "Администратор",
    "branch": "Филиал",
    "photo": "Изображение",
}

ACTION_TYPE_LABELS = {
    "bot_start": "Запуск бота",
    "phone_shared": "Передача телефона",
    "language_selected": "Выбор языка",
    "arrival_flow_started": "Начало прихода",
    "transfer_flow_started": "Начало перемещения",
    "request_photo_uploaded": "Загрузка изображения",
    "request_created": "Создание операции",
    "request_report_sent": "Отправка отчета",
    "request_report_failed": "Ошибка отправки отчета",
    "admin_login": "Вход администратора",
    "admin_login_changed": "Смена логина",
    "admin_password_changed": "Смена пароля",
    "warehouse_created": "Создание склада",
    "warehouse_updated": "Обновление склада",
    "warehouse_group_bound": "Привязка группы к складу",
}


@router.get("")
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    actor_type: str | None = Query(default=None),
    actor_id: int | None = Query(default=None, ge=1),
    action_type: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    items, total = await service.list_audit_logs(
        page=page,
        page_size=page_size,
        actor_type=actor_type,
        actor_id=actor_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
    )
    return paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/export")
async def export_audit_logs(
    actor_type: str | None = Query(default=None),
    actor_id: int | None = Query(default=None, ge=1),
    action_type: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Database = Depends(get_db),
):
    service = AdminService(db)
    rows = await service.export_audit_logs(
        actor_type=actor_type,
        actor_id=actor_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
    )
    normalized_rows = []
    for row in rows:
        normalized = dict(row)
        normalized["actor_type"] = ACTOR_TYPE_LABELS.get(normalized.get("actor_type"), "Неизвестный тип")
        normalized["action_type"] = ACTION_TYPE_LABELS.get(normalized.get("action_type"), "Системное действие")
        normalized["entity_type"] = ENTITY_TYPE_LABELS.get(normalized.get("entity_type"), "Неизвестная сущность")
        normalized_rows.append(normalized)
    return excel_response(
        filename="audit.xlsx",
        columns=[
            ("Идентификатор", "id"),
            ("Тип актора", "actor_type"),
            ("Пользователь ИД", "actor_user_id"),
            ("Имя пользователя актора", "actor_user_name"),
            ("Админ ИД", "actor_admin_id"),
            ("Имя админа", "actor_admin_name"),
            ("Действие", "action_type"),
            ("Тип сущности", "entity_type"),
            ("ИД сущности", "entity_id"),
            ("Сообщение", "message"),
            ("Дополнительно", "meta"),
            ("Время", "created_at"),
        ],
        rows=normalized_rows,
    )
