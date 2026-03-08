from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_db, verify_admin_token
from app.api.schemas import RequestOut, StatsOut, SystemLogOut, UserOut
from app.db.database import Database

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(verify_admin_token)])


@router.get("/users", response_model=list[UserOut])
async def get_users(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Database = Depends(get_db),
) -> list[UserOut]:
    return await db.list_users(limit=limit, offset=offset)


@router.get("/requests", response_model=list[RequestOut])
async def get_requests(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    operation_type: str | None = Query(default=None, pattern="^(arrival|transfer)$"),
    db: Database = Depends(get_db),
) -> list[RequestOut]:
    return await db.list_requests(limit=limit, offset=offset, operation_type=operation_type)


@router.get("/logs", response_model=list[SystemLogOut])
async def get_logs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    level: str | None = Query(default=None, pattern="^(INFO|ERROR|WARNING|DEBUG)$"),
    db: Database = Depends(get_db),
) -> list[SystemLogOut]:
    return await db.list_logs(limit=limit, offset=offset, level=level)


@router.get("/stats", response_model=StatsOut)
async def get_stats(db: Database = Depends(get_db)) -> StatsOut:
    return StatsOut(**await db.get_stats())
