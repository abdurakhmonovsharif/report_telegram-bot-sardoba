ALTER TABLE requests
    ADD COLUMN IF NOT EXISTS transfer_kind TEXT,
    ADD COLUMN IF NOT EXISTS source_branch TEXT,
    ADD COLUMN IF NOT EXISTS source_branch_id BIGINT REFERENCES branches (id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS source_warehouse TEXT,
    ADD COLUMN IF NOT EXISTS source_warehouse_id BIGINT REFERENCES warehouses (id) ON DELETE SET NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'requests_transfer_kind_check'
    ) THEN
        ALTER TABLE requests
            ADD CONSTRAINT requests_transfer_kind_check
            CHECK (transfer_kind IS NULL OR transfer_kind IN ('warehouse', 'branch'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_requests_source_branch_id ON requests (source_branch_id);
CREATE INDEX IF NOT EXISTS idx_requests_source_warehouse_id ON requests (source_warehouse_id);
