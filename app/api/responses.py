from __future__ import annotations

from math import ceil
from typing import Any


def ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"success": True, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return payload


def paginated(
    *,
    items: list[Any],
    total: int,
    page: int,
    page_size: int,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total_pages = ceil(total / page_size) if page_size else 1
    meta = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
    if extra_meta:
        meta.update(extra_meta)
    return ok(items, meta=meta)


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> tuple[int, dict[str, Any]]:
    return (
        status_code,
        {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
        },
    )
