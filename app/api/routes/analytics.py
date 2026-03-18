from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_admin, get_db
from app.api.responses import ok
from app.db.database import Database
from app.services.admin_service import AdminService

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"], dependencies=[Depends(get_current_admin)])


@router.get("/overview")
async def analytics_overview(db: Database = Depends(get_db)) -> dict:
    service = AdminService(db)
    return ok(
        {
            "summary": await service.get_dashboard_summary(),
            "branches": await service.get_branch_breakdown(),
            "warehouses": await service.get_warehouse_breakdown(),
            "top_products": await service.get_top_products(),
            "top_users": await service.get_top_users(),
            "heatmap": await service.get_branch_heatmap(),
        }
    )


@router.get("/dynamics")
async def analytics_dynamics(
    period: str = Query(default="day", pattern="^(day|week|month)$"),
    days: int = Query(default=90, ge=1, le=365),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    return ok(await service.get_operation_dynamics(period=period, days=days))


@router.get("/top-products")
async def analytics_top_products(
    limit: int = Query(default=10, ge=1, le=50),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    return ok(await service.get_top_products(limit=limit))


@router.get("/top-users")
async def analytics_top_users(
    limit: int = Query(default=10, ge=1, le=50),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    return ok(await service.get_top_users(limit=limit))


@router.get("/heatmap")
async def analytics_heatmap(db: Database = Depends(get_db)) -> dict:
    service = AdminService(db)
    return ok(await service.get_branch_heatmap())
