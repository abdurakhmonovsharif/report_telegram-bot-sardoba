from __future__ import annotations

import traceback
from datetime import date as DateType

from app.db.database import Database
from app.services.report_sender import ReportSender


class ReportDeliveryError(Exception):
    def __init__(self, request_id: int) -> None:
        super().__init__(f"Report delivery failed for request_id={request_id}")
        self.request_id = request_id


class RequestService:
    def __init__(self, db: Database, report_sender: ReportSender) -> None:
        self.db = db
        self.report_sender = report_sender

    async def finalize_request(
        self,
        *,
        telegram_user_id: int,
        telegram_user_name: str,
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
        request_date: DateType | None = None,
        comment: str | None = None,
        category: str | None = None,
        info_text: str | None = None,
        product_name: str | None = None,
        quantity: str | None = None,
        photos: list[str | dict] | None = None,
    ) -> dict:
        try:
            user = await self.db.upsert_user(telegram_user_id, telegram_user_name)
            request_record = await self.db.create_request(
                user_id=user["id"],
                operation_type=operation_type,
                branch=branch,
                warehouse=warehouse,
                branch_id=branch_id,
                warehouse_id=warehouse_id,
                transfer_type=transfer_type,
                from_branch_id=from_branch_id,
                to_branch_id=to_branch_id,
                from_warehouse_id=from_warehouse_id,
                to_warehouse_id=to_warehouse_id,
                transfer_kind=transfer_kind,
                source_branch=source_branch,
                source_branch_id=source_branch_id,
                source_warehouse=source_warehouse,
                source_warehouse_id=source_warehouse_id,
                supplier_name=supplier_name,
                request_date=request_date,
                comment=comment,
                category=category,
                info_text=info_text,
                product_name=product_name,
                quantity=quantity,
                notification_status="failed",
                photos=photos or [],
            )
        except Exception:
            try:
                await self.db.log_event(
                    level="ERROR",
                    event_type="request_save_failed",
                    message="Failed to save warehouse request",
                    context={
                        "operation_type": operation_type,
                        "branch": branch,
                        "warehouse": warehouse,
                        "telegram_user_id": telegram_user_id,
                        "branch_id": branch_id,
                        "warehouse_id": warehouse_id,
                        "transfer_type": transfer_type or transfer_kind,
                        "from_branch_id": from_branch_id or source_branch_id,
                        "to_branch_id": to_branch_id or branch_id,
                        "from_warehouse_id": from_warehouse_id or source_warehouse_id,
                        "to_warehouse_id": to_warehouse_id or warehouse_id,
                        "transfer_kind": transfer_kind,
                        "source_branch_id": source_branch_id,
                        "source_warehouse_id": source_warehouse_id,
                    },
                    stack_trace=traceback.format_exc(),
                )
            except Exception:
                pass
            raise

        await self.db.log_event(
            level="INFO",
            event_type="request_saved",
            message="Warehouse request saved",
            context={
                "request_id": request_record["id"],
                "request_code": request_record["code"],
                "operation_type": operation_type,
                "branch": branch,
                "warehouse": warehouse,
                "telegram_user_id": telegram_user_id,
                "transfer_type": transfer_type or transfer_kind,
            },
        )
        await self.db.log_audit(
            actor_type="telegram_user",
            actor_user_id=user["id"],
            action_type="request_created",
            entity_type="request",
            entity_id=request_record["id"],
            message="Пользователь завершил операцию в Telegram-боте.",
            meta={
                "operation_type": operation_type,
                "request_code": request_record["code"],
                "branch": branch,
                "warehouse": warehouse,
                "transfer_type": transfer_type or transfer_kind,
                "from_branch_id": from_branch_id or source_branch_id,
                "to_branch_id": to_branch_id or branch_id,
                "from_warehouse_id": from_warehouse_id or source_warehouse_id,
                "to_warehouse_id": to_warehouse_id or warehouse_id,
                "source_branch": source_branch,
                "source_warehouse": source_warehouse,
                "product_name": product_name,
                "quantity": quantity,
            },
        )

        try:
            await self.report_sender.send_request_report(
                request_record=request_record,
                photos=photos or [],
                user_record=user,
            )
            request_record = await self.db.update_request_notification_status(
                request_id=int(request_record["id"]),
                notification_status="sent",
            ) or request_record
            await self.db.log_event(
                level="INFO",
                event_type="report_sent",
                message="Warehouse request report sent to Telegram group",
                context={
                    "request_id": request_record["id"],
                    "request_code": request_record["code"],
                    "branch": branch,
                    "warehouse": warehouse,
                },
            )
            await self.db.log_audit(
                actor_type="system",
                action_type="request_report_sent",
                entity_type="request",
                entity_id=request_record["id"],
                message="Системный отчет по операции отправлен в Telegram.",
                meta={"request_code": request_record["code"]},
            )
        except Exception:
            request_record = await self.db.update_request_notification_status(
                request_id=int(request_record["id"]),
                notification_status="failed",
            ) or request_record
            await self.db.log_event(
                level="ERROR",
                event_type="report_send_failed",
                message="Request was saved but failed to send report to Telegram group",
                context={
                    "request_id": request_record["id"],
                    "request_code": request_record["code"],
                    "branch": branch,
                    "warehouse": warehouse,
                },
                stack_trace=traceback.format_exc(),
            )
            await self.db.log_audit(
                actor_type="system",
                action_type="request_report_failed",
                entity_type="request",
                entity_id=request_record["id"],
                message="Системный отчет по операции не был отправлен в Telegram.",
                meta={
                    "request_code": request_record["code"],
                    "notification_status": "failed",
                },
            )
            raise ReportDeliveryError(request_record["id"])

        return request_record
