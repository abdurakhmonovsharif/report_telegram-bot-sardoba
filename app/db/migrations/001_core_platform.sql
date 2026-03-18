CREATE TABLE IF NOT EXISTS branches (
    id BIGSERIAL PRIMARY KEY,
    code BIGINT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    bot_name TEXT NOT NULL,
    admin_name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS warehouses (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouses_name_lower ON warehouses (LOWER(name));
CREATE INDEX IF NOT EXISTS idx_warehouses_active ON warehouses (is_active, sort_order, id);

CREATE TABLE IF NOT EXISTS admin_users (
    id BIGSERIAL PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_type TEXT NOT NULL,
    actor_user_id BIGINT REFERENCES users (id) ON DELETE SET NULL,
    actor_admin_id BIGINT REFERENCES admin_users (id) ON DELETE SET NULL,
    action_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id BIGINT,
    message TEXT NOT NULL,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS first_name TEXT,
    ADD COLUMN IF NOT EXISTS last_name TEXT,
    ADD COLUMN IF NOT EXISTS username TEXT,
    ADD COLUMN IF NOT EXISTS phone_number TEXT,
    ADD COLUMN IF NOT EXISTS avatar_file_id TEXT,
    ADD COLUMN IF NOT EXISTS avatar_file_unique_id TEXT,
    ADD COLUMN IF NOT EXISTS avatar_width INTEGER,
    ADD COLUMN IF NOT EXISTS avatar_height INTEGER,
    ADD COLUMN IF NOT EXISTS avatar_file_size INTEGER,
    ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;

ALTER TABLE requests
    ADD COLUMN IF NOT EXISTS code TEXT,
    ADD COLUMN IF NOT EXISTS branch_id BIGINT REFERENCES branches (id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS warehouse_id BIGINT REFERENCES warehouses (id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS category TEXT,
    ADD COLUMN IF NOT EXISTS info_text TEXT,
    ADD COLUMN IF NOT EXISTS product_name TEXT,
    ADD COLUMN IF NOT EXISTS quantity TEXT,
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'completed',
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'bot',
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE request_photos
    ADD COLUMN IF NOT EXISTS telegram_file_unique_id TEXT,
    ADD COLUMN IF NOT EXISTS width INTEGER,
    ADD COLUMN IF NOT EXISTS height INTEGER,
    ADD COLUMN IF NOT EXISTS file_size INTEGER,
    ADD COLUMN IF NOT EXISTS uploaded_by_user_id BIGINT REFERENCES users (id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_branches_sort_order ON branches (sort_order, id);
CREATE INDEX IF NOT EXISTS idx_users_phone_number ON users (phone_number);
CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_last_seen_at ON users (last_seen_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_requests_code ON requests (code) WHERE code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_requests_branch_id ON requests (branch_id);
CREATE INDEX IF NOT EXISTS idx_requests_warehouse_id ON requests (warehouse_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests (status);
CREATE INDEX IF NOT EXISTS idx_requests_product_name ON requests (product_name);
CREATE INDEX IF NOT EXISTS idx_requests_completed_at ON requests (completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_request_photos_created_at ON request_photos (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_type ON audit_logs (actor_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action_type ON audit_logs (action_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity_type, entity_id);

INSERT INTO branches (code, slug, bot_name, admin_name, sort_order)
VALUES
    (139235, 'geofizika', 'Geofizika', 'Геофизика', 1),
    (157757, 'gijdivon', 'Gijdivon', 'Гиждуван', 2),
    (139350, 'severniy', 'Severniy', 'Северный', 3),
    (139458, 'mk5', 'Mk5', 'МК-5', 4)
ON CONFLICT (code) DO UPDATE
SET
    slug = EXCLUDED.slug,
    bot_name = EXCLUDED.bot_name,
    admin_name = EXCLUDED.admin_name,
    sort_order = EXCLUDED.sort_order,
    is_active = TRUE,
    updated_at = NOW();

INSERT INTO warehouses (name, description, is_active, sort_order)
VALUES
    ('Bar', 'Основной барный склад', TRUE, 1),
    ('Kuxna', 'Кухонный склад', TRUE, 2),
    ('Go''sht', 'Склад мясной продукции', TRUE, 3)
ON CONFLICT (LOWER(name)) DO NOTHING;

UPDATE users
SET
    first_seen_at = COALESCE(first_seen_at, created_at),
    last_seen_at = COALESCE(last_seen_at, updated_at, created_at);

UPDATE requests
SET completed_at = COALESCE(completed_at, created_at),
    updated_at = COALESCE(updated_at, created_at);

UPDATE requests AS r
SET branch_id = b.id
FROM branches AS b
WHERE r.branch_id IS NULL
  AND r.branch = b.bot_name;

UPDATE requests AS r
SET warehouse_id = w.id
FROM warehouses AS w
WHERE r.warehouse_id IS NULL
  AND LOWER(r.warehouse) = LOWER(w.name);

UPDATE requests
SET code = CASE
    WHEN operation_type = 'arrival' THEN 'PRI-' || TO_CHAR(COALESCE(created_at, NOW()), 'YYYYMMDD') || '-' || LPAD(id::TEXT, 6, '0')
    ELSE 'PER-' || TO_CHAR(COALESCE(created_at, NOW()), 'YYYYMMDD') || '-' || LPAD(id::TEXT, 6, '0')
END
WHERE code IS NULL;
