
from app.api.routes.analytics import router as analytics_router
from app.api.routes.audit import router as audit_router
from app.api.routes.auth import router as auth_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.media import router as media_router
from app.api.routes.operations import router as operations_router
from app.api.routes.users import router as users_router

__all__ = [
    "analytics_router",
    "audit_router",
    "auth_router",
    "catalog_router",
    "dashboard_router",
    "media_router",
    "operations_router",
    "users_router",
]
