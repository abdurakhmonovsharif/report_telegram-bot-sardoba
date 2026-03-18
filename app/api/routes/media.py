from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from fastapi.responses import Response

from app.api.dependencies import get_current_admin, get_db, get_settings
from app.config import Settings
from app.db.database import Database
from app.services.media_service import MediaService

router = APIRouter(prefix="/api/v1/media", tags=["media"], dependencies=[Depends(get_current_admin)])


@router.get("/photos/{photo_id}")
async def operation_photo(
    photo_id: int = Path(..., ge=1),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    media_service = MediaService(db=db, settings=settings)
    media = await media_service.get_operation_photo(photo_id)
    return Response(
        content=media["content"],
        media_type=media["content_type"],
        headers={"Content-Disposition": f"inline; filename={media['filename']}"},
    )


@router.get("/users/{user_id}/avatar")
async def user_avatar(
    user_id: int = Path(..., ge=1),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    media_service = MediaService(db=db, settings=settings)
    media = await media_service.get_user_avatar(user_id)
    return Response(
        content=media["content"],
        media_type=media["content_type"],
        headers={"Content-Disposition": f"inline; filename={media['filename']}"},
    )
