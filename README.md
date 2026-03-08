# Restaurant Warehouse Telegram Bot (aiogram + FastAPI + PostgreSQL)

Production-ready backend for restaurant warehouse control with:
- `Приход` (Arrival) workflow
- `Перемещение` (Transfer) workflow
- multilingual Telegram bot (`Uzbek`, `Russian`, `English`)
- PostgreSQL persistence with `asyncpg`
- admin REST API with FastAPI and Swagger
- full event/error logging to `system_logs`

## 1. Tech stack
- Python `3.11`
- `aiogram 3.x`
- `FastAPI`
- `asyncpg`
- PostgreSQL

## 2. Features implemented
- `/start` first asks for language via Telegram buttons before main functionality.
- Uzbek is the default system language, but user must explicitly choose/confirm language first.
- Chosen language is stored in `users.language`.
- Language can be changed later via `/language` or menu button.
- Strict FSM step-by-step workflows using Telegram buttons/inline keyboards.

### Arrival (`Приход`) flow
1. Select branch
2. Select warehouse
3. Upload unlimited invoice photos (`file_id`) OR choose `No invoice photo`
4. If no invoice photo: enter manual text (products + total price)
5. Enter supplier
6. Enter date
7. Request is saved and report is sent to mapped Telegram group

### Transfer (`Перемещение`) flow
1. Select branch
2. Select warehouse
3. Enter comment (moved products)
4. Optional photo upload (or skip)
5. Request is saved and report is sent to mapped Telegram group

## 3. Database schema
Schema file: `app/db/schema.sql`

Tables:
- `users`: `telegram_id`, `name`, `role`, `language`, timestamps
- `requests`: `id`, `operation_type`, `branch`, `warehouse`, `supplier_name`, `date`, `comment`, `created_at`, `user_id`
- `request_photos`: `id`, `request_id`, `telegram_file_id`
- `system_logs`: all success/error events, backend exceptions, Telegram API errors

## 4. Configuration
Copy `.env.example` to `.env` and update values.

Required:
- `BOT_TOKEN`
- `DATABASE_URL`
- `ROUTING_MAP_JSON` (branch/warehouse -> Telegram group ID map)

Example routing map:
```json
{"Sardoba":{"Asosiy":-1001111111111,"Sovutkich":-1002222222222},"Chilonzor":{"Asosiy":-1003333333333}}
```

`ROUTING_MAP_JSON` determines:
- which branches and warehouses appear in bot buttons
- which Telegram group receives each report

## 5. Installation
```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 6. Run

### A) Run bot only (long polling)
```bash
python -m app.bot.run
```

### B) Run admin API only
```bash
uvicorn app.api.app:app --host 0.0.0.0 --port 8000
```

### C) Run bot + admin API together (single process)
```bash
python -m app.main
```

## 7. Admin API and Swagger
Default base URL:
- `http://localhost:8000`

Swagger UI:
- `http://localhost:8000/docs`

OpenAPI schema:
- `http://localhost:8000/openapi.json`

Health endpoint:
- `GET /health`

Admin endpoints:
- `GET /admin/users`
- `GET /admin/requests`
- `GET /admin/logs`
- `GET /admin/stats`

If `ADMIN_TOKEN` is set in `.env`, include header:
- `X-Admin-Token: <your_token>`

## 8. How administrators/developers connect to Admin API
Use any HTTP client (`curl`, Postman, Insomnia, browser for Swagger).

Example prompt/instruction for developers:

```text
Connect to the warehouse admin API at http://localhost:8000.
If authentication is enabled, add header X-Admin-Token.
Use /docs for Swagger UI and /openapi.json for schema.
Read requests via GET /admin/requests and logs via GET /admin/logs.
```

Example `curl`:
```bash
curl -H "X-Admin-Token: replace_with_secure_token" http://localhost:8000/admin/stats
```

## 9. Error handling behavior
- Internal exceptions are not exposed to Telegram users.
- Users receive safe fallback messages.
- Exceptions and failures are written to `system_logs`.
- Telegram API delivery failures are logged and surfaced to user safely.
- FSM state remains controlled and does not jump across steps.

## 10. Deployment notes (VPS)
- Run bot and API as separate systemd services for best isolation, or use `app.main` in one process.
- Put PostgreSQL and bot/API credentials in environment variables.
- Restrict admin API access by firewall and `ADMIN_TOKEN`.
- Keep `AUTO_MIGRATE=true` for bootstrap, then consider controlled migrations for production.
