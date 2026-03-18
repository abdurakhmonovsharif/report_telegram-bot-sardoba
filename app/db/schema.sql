CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'staff',
    language VARCHAR(5),
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    phone_number TEXT,
    avatar_file_id TEXT,
    avatar_file_unique_id TEXT,
    avatar_width INTEGER,
    avatar_height INTEGER,
    avatar_file_size INTEGER,
    first_seen_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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
    slug TEXT,
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    group_chat_id BIGINT,
    group_chat_title TEXT,
    group_linked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS requests (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE,
    operation_type TEXT NOT NULL CHECK (operation_type IN ('arrival', 'transfer')),
    branch TEXT NOT NULL,
    warehouse TEXT NOT NULL,
    branch_id BIGINT REFERENCES branches (id) ON DELETE SET NULL,
    warehouse_id BIGINT REFERENCES warehouses (id) ON DELETE SET NULL,
    transfer_type TEXT CHECK (transfer_type IS NULL OR transfer_type IN ('warehouse', 'branch')),
    from_branch_id BIGINT REFERENCES branches (id) ON DELETE SET NULL,
    to_branch_id BIGINT REFERENCES branches (id) ON DELETE SET NULL,
    from_warehouse_id BIGINT REFERENCES warehouses (id) ON DELETE SET NULL,
    to_warehouse_id BIGINT REFERENCES warehouses (id) ON DELETE SET NULL,
    transfer_kind TEXT CHECK (transfer_kind IS NULL OR transfer_kind IN ('warehouse', 'branch')),
    source_branch TEXT,
    source_branch_id BIGINT REFERENCES branches (id) ON DELETE SET NULL,
    source_warehouse TEXT,
    source_warehouse_id BIGINT REFERENCES warehouses (id) ON DELETE SET NULL,
    supplier_name TEXT,
    date DATE,
    comment TEXT,
    category TEXT,
    info_text TEXT,
    product_name TEXT,
    quantity TEXT,
    line_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'completed',
    notification_status TEXT NOT NULL DEFAULT 'sent',
    source TEXT NOT NULL DEFAULT 'bot',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id BIGINT NOT NULL REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS request_photos (
    id BIGSERIAL PRIMARY KEY,
    request_id BIGINT NOT NULL REFERENCES requests (id) ON DELETE CASCADE,
    telegram_file_id TEXT NOT NULL,
    telegram_file_unique_id TEXT,
    width INTEGER,
    height INTEGER,
    file_size INTEGER,
    uploaded_by_user_id BIGINT REFERENCES users (id) ON DELETE SET NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    stack_trace TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_phone_number ON users (phone_number);
CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_last_seen_at ON users (last_seen_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouses_name_lower ON warehouses (LOWER(name));
CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouses_slug ON warehouses (slug) WHERE slug IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouses_group_chat_id ON warehouses (group_chat_id) WHERE group_chat_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_warehouses_active ON warehouses (is_active, sort_order, id);
CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_requests_operation_type ON requests (operation_type);
CREATE INDEX IF NOT EXISTS idx_requests_branch_id ON requests (branch_id);
CREATE INDEX IF NOT EXISTS idx_requests_warehouse_id ON requests (warehouse_id);
CREATE INDEX IF NOT EXISTS idx_requests_transfer_type ON requests (transfer_type);
CREATE INDEX IF NOT EXISTS idx_requests_from_branch_id ON requests (from_branch_id);
CREATE INDEX IF NOT EXISTS idx_requests_to_branch_id ON requests (to_branch_id);
CREATE INDEX IF NOT EXISTS idx_requests_from_warehouse_id ON requests (from_warehouse_id);
CREATE INDEX IF NOT EXISTS idx_requests_to_warehouse_id ON requests (to_warehouse_id);
CREATE INDEX IF NOT EXISTS idx_requests_source_branch_id ON requests (source_branch_id);
CREATE INDEX IF NOT EXISTS idx_requests_source_warehouse_id ON requests (source_warehouse_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests (status);
CREATE INDEX IF NOT EXISTS idx_requests_product_name ON requests (product_name);
CREATE INDEX IF NOT EXISTS idx_request_photos_request_id ON request_photos (request_id);
CREATE INDEX IF NOT EXISTS idx_request_photos_created_at ON request_photos (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs (level);
