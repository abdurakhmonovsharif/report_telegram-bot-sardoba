CREATE TABLE IF NOT EXISTS operation_group_bindings (
    operation_type TEXT PRIMARY KEY CHECK (operation_type IN ('act_razbora')),
    group_chat_id BIGINT NOT NULL,
    group_chat_title TEXT,
    group_linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operation_group_bindings_group_chat_id
    ON operation_group_bindings (group_chat_id);
