from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from app.api.dependencies import get_current_admin, get_db
from app.api.responses import ok, paginated
from app.db.database import Database
from app.services.admin_service import AdminService

router = APIRouter(prefix="/api/v1", tags=["catalog"], dependencies=[Depends(get_current_admin)])


@router.get("/warehouses")
async def list_warehouses(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    items, total = await service.list_warehouses(
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
    )
    return paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/branches")
async def list_branches(db: Database = Depends(get_db)) -> dict:
    service = AdminService(db)
    return ok(await service.list_branches())


@router.get("/branches/{branch_id}")
async def branch_detail(
    branch_id: int = Path(..., ge=1),
    db: Database = Depends(get_db),
) -> dict:
    service = AdminService(db)
    return ok(await service.get_branch_detail(branch_id))
