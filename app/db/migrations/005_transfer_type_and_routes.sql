ALTER TABLE requests
    ADD COLUMN IF NOT EXISTS transfer_type TEXT,
    ADD COLUMN IF NOT EXISTS from_branch_id BIGINT REFERENCES branches (id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS to_branch_id BIGINT REFERENCES branches (id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS from_warehouse_id BIGINT REFERENCES warehouses (id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS to_warehouse_id BIGINT REFERENCES warehouses (id) ON DELETE SET NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'requests_transfer_type_check'
    ) THEN
        ALTER TABLE requests
            ADD CONSTRAINT requests_transfer_type_check
            CHECK (transfer_type IS NULL OR transfer_type IN ('warehouse', 'branch'));
    END IF;
END $$;

UPDATE requests
SET transfer_type = COALESCE(transfer_type, transfer_kind)
WHERE operation_type = 'transfer'
  AND transfer_kind IS NOT NULL;

UPDATE requests
SET transfer_type = 'warehouse'
WHERE operation_type = 'transfer'
  AND transfer_type IS NULL;

UPDATE requests
SET from_branch_id = COALESCE(from_branch_id, source_branch_id),
    to_branch_id = COALESCE(to_branch_id, branch_id),
    from_warehouse_id = COALESCE(from_warehouse_id, source_warehouse_id),
    to_warehouse_id = COALESCE(to_warehouse_id, warehouse_id)
WHERE operation_type = 'transfer';

CREATE INDEX IF NOT EXISTS idx_requests_transfer_type ON requests (transfer_type);
CREATE INDEX IF NOT EXISTS idx_requests_from_branch_id ON requests (from_branch_id);
CREATE INDEX IF NOT EXISTS idx_requests_to_branch_id ON requests (to_branch_id);
CREATE INDEX IF NOT EXISTS idx_requests_from_warehouse_id ON requests (from_warehouse_id);
CREATE INDEX IF NOT EXISTS idx_requests_to_warehouse_id ON requests (to_warehouse_id);
