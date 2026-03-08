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
        supplier_name: str | None = None,
        request_date: DateType | None = None,
        comment: str | None = None,
        photos: list[str] | None = None,
    ) -> dict:
        try:
            user = await self.db.upsert_user(telegram_user_id, telegram_user_name)
            request_record = await self.db.create_request(
                user_id=user["id"],
                operation_type=operation_type,
                branch=branch,
                warehouse=warehouse,
                supplier_name=supplier_name,
                request_date=request_date,
                comment=comment,
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
                "operation_type": operation_type,
                "branch": branch,
                "warehouse": warehouse,
                "telegram_user_id": telegram_user_id,
            },
        )

        try:
            await self.report_sender.send_request_report(
                request_record=request_record,
                photos=photos or [],
                user_record=user,
            )
            await self.db.log_event(
                level="INFO",
                event_type="report_sent",
                message="Warehouse request report sent to Telegram group",
                context={
                    "request_id": request_record["id"],
                    "branch": branch,
                    "warehouse": warehouse,
                },
            )
        except Exception:
            await self.db.log_event(
                level="ERROR",
                event_type="report_send_failed",
                message="Request was saved but failed to send report to Telegram group",
                context={
                    "request_id": request_record["id"],
                    "branch": branch,
                    "warehouse": warehouse,
                },
                stack_trace=traceback.format_exc(),
            )
            raise ReportDeliveryError(request_record["id"])

        return request_record
