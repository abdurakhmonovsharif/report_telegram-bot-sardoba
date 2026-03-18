ALTER TABLE warehouses
    ADD COLUMN IF NOT EXISTS group_chat_id BIGINT,
    ADD COLUMN IF NOT EXISTS group_chat_title TEXT,
    ADD COLUMN IF NOT EXISTS group_linked_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouses_group_chat_id
    ON warehouses (group_chat_id)
    WHERE group_chat_id IS NOT NULL;
