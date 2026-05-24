ALTER TABLE requests
    DROP CONSTRAINT IF EXISTS requests_operation_type_check;

UPDATE requests
SET
    operation_type = 'act_razbora',
    warehouse = COALESCE(NULLIF(warehouse, ''), 'Без склада'),
    warehouse_id = NULL,
    transfer_type = NULL,
    transfer_kind = NULL,
    from_branch_id = NULL,
    to_branch_id = NULL,
    from_warehouse_id = NULL,
    to_warehouse_id = NULL,
    source_branch = NULL,
    source_branch_id = NULL,
    source_warehouse = NULL,
    source_warehouse_id = NULL,
    code = 'AKT-' || TO_CHAR(COALESCE(created_at, NOW()), 'YYYYMMDD') || '-' || LPAD(id::TEXT, 6, '0'),
    updated_at = NOW()
WHERE operation_type = 'transfer';

ALTER TABLE requests
    ADD CONSTRAINT requests_operation_type_check
    CHECK (operation_type IN ('arrival', 'act_razbora'));
