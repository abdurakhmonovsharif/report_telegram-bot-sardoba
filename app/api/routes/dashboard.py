from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_admin, get_db
from app.api.responses import ok
from app.db.database import Database
from app.services.admin_service import AdminService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_admin)])


@router.get("/summary")
async def dashboard_summary(db: Database = Depends(get_db)) -> dict:
    service = AdminService(db)
    return ok(await service.get_dashboard_summary())


@router.get("/branches")
async def branch_breakdown(db: Database = Depends(get_db)) -> dict:
    service = AdminService(db)
    return ok(await service.get_branch_breakdown())


@router.get("/warehouses")
async def warehouse_breakdown(db: Database = Depends(get_db)) -> dict:
    service = AdminService(db)
    return ok(await service.get_warehouse_breakdown())


@router.get("/users")
async def user_activity_breakdown(
    limit: int = Query(default=10, ge=1, le=50),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    return ok(await service.get_user_activity_breakdown(limit=limit))


@router.get("/recent")
async def recent_operations(
    limit: int = Query(default=10, ge=1, le=50),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    return ok(await service.get_recent_operations(limit=limit))


@router.get("/dynamics")
async def dashboard_dynamics(
    period: str = Query(default="day", pattern="^(day|week|month)$"),
    days: int = Query(default=30, ge=1, le=365),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    return ok(await service.get_operation_dynamics(period=period, days=days))
