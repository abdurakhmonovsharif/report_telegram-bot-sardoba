from __future__ import annotations

import json
from datetime import date, datetime
from io import BytesIO
from typing import Any

from fastapi.responses import Response
import openpyxl


def _serialize_excel_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime):
        # Excel doesn't support timezone aware datetimes natively
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    # Openpyxl supports int, float, str natively
    return str(value) if not isinstance(value, (int, float, str)) else value


def excel_response(
    *,
    filename: str,
    columns: list[tuple[str, str]],
    rows: list[dict[str, Any]],
) -> Response:
    wb = openpyxl.Workbook()
    ws = wb.active
    
    # Write headers
    headers = [header for header, _ in columns]
    ws.append(headers)
    
    # Write data
    for row in rows:
        ws.append([_serialize_excel_value(row.get(key)) for _, key in columns])
        
    buffer = BytesIO()
    wb.save(buffer)
    
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
