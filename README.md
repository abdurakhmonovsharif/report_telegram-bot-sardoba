# Sardoba Warehouse Platform

Telegram bot + FastAPI backend + Material UI admin panel for warehouse operations.

## Stack

- Python 3.11+
- `aiogram 3.x`
- `FastAPI`
- `asyncpg`
- PostgreSQL
- React + TypeScript + Vite + Material UI

## What is included

- Telegram bot with mandatory phone share on first start
- two bot flows: `Приход` and `Перемещение`
- static seeded branches
- four static warehouses with per-warehouse Telegram notification routing
- rich operation model: product, quantity, info text, comment, photos, supplier, date
- operation notification status: `sent` / `failed`
- admin authentication with login/password and JWT
- Russian-only admin UI
- dashboard, users, operations, arrivals, transfers, warehouses, branches, analytics, audit, profile pages
- CSV export for users, operations, and audit logs
- audit trail for bot/admin/system actions
- media preview endpoints for operation photos and user avatars
- SQL migrations + seed data

## Static branches

Seeded automatically in this order:

1. `Geofizika` / code `139235`
2. `Gijdivon` / code `157757`
3. `Severniy` / code `139350`
4. `Mk5` / code `139458`

The bot shows bot labels, while admin API/UI uses Russian admin labels.

## Static warehouses

- `Бар`
- `Кухня`
- `Средства`
- `Мясо`

These warehouses are fixed by the system. The admin panel exposes them in read-only mode and the bot uses only these four options.

## Group binding

Warehouse Telegram groups are normally linked directly from Telegram, not from `.env`.

1. Add the bot to the target group.
2. Make the bot or the user who runs the command an administrator of that group.
3. In the group run one of:
   - `/setgroup bar`
   - `/setgroup kitchen`
   - `/setgroup supplies`
   - `/setgroup meat`

The bot stores `chat_id` in the database on the corresponding warehouse row and starts using that group for notifications.

## Backend API groups

- `/api/v1/auth/*`
- `/api/v1/dashboard/*`
- `/api/v1/users/*`
- `/api/v1/operations/*`
- `/api/v1/warehouses*`
- `/api/v1/branches*`
- `/api/v1/analytics/*`
- `/api/v1/audit`
- `/api/v1/media/*`

Export endpoints:

- `/api/v1/users/export`
- `/api/v1/operations/export`
- `/api/v1/audit/export`

Legacy minimal endpoints are still available under `/admin/*`.

## Database migrations

SQL migrations live in:

- `app/db/migrations/`

They are applied automatically when `AUTO_MIGRATE=true`.

Main schema snapshot:

- `app/db/schema.sql`

## Environment

Copy `.env.example` to `.env`.

Important variables:

- `BOT_TOKEN`
- `DATABASE_URL`
- `JWT_SECRET`
- `ADMIN_SEED_LOGIN`
- `ADMIN_SEED_PASSWORD`
- `ADMIN_SEED_NAME`
- `FRONTEND_ORIGIN`
- `WAREHOUSE_BAR_CHAT_ID`
- `WAREHOUSE_KITCHEN_CHAT_ID`
- `WAREHOUSE_SUPPLIES_CHAT_ID`
- `WAREHOUSE_MEAT_CHAT_ID`
- `DEFAULT_REPORT_CHAT_ID` optional fallback
- `ROUTING_MAP_JSON` optional legacy Telegram routing map

Normally the `WAREHOUSE_*_CHAT_ID` variables are not required because group binding is stored in the database via `/setgroup`. They remain only as compatibility fallback.

## Admin auth rules

Login:

- minimum 8 characters
- minimum 1 uppercase Latin letter
- minimum 5 lowercase Latin letters
- minimum 2 digits
- only Latin letters and digits

Password:

- minimum 8 characters
- only Latin letters and digits
- stored only as hash

## Run backend

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

Backend URLs:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Run frontend in dev

```bash
cd frontend
npm install
npm run dev
```

Dev URL:

- `http://localhost:5173/panel`

## Build frontend

```bash
cd frontend
npm run build
```

If `frontend/dist` exists, FastAPI serves the admin panel at:

- `http://localhost:8000/panel`

## Developer notes

- Telegram users are upserted by `telegram_id`, so duplicates are not created on re-entry.
- Bot photos are stored as Telegram file ids + metadata in `request_photos`.
- User avatar is fetched from Telegram profile photos when possible and exposed through backend media endpoints.
- Operations receive unique codes like `PRI-YYYYMMDD-000001` and `PER-YYYYMMDD-000001`.
- Each operation stores `notification_status`, while Telegram delivery failures are preserved in audit/system logs and do not roll back the saved operation.
- Dashboard/analytics cards in the frontend are backed by real backend endpoints, no mock data is used.
