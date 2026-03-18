ALTER TABLE warehouses
    ADD COLUMN IF NOT EXISTS slug TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouses_slug
    ON warehouses (slug)
    WHERE slug IS NOT NULL;

ALTER TABLE requests
    ADD COLUMN IF NOT EXISTS notification_status TEXT NOT NULL DEFAULT 'sent';

UPDATE warehouses
SET
    slug = 'bar',
    name = 'Бар',
    description = 'Барный склад',
    is_active = TRUE,
    sort_order = 1,
    updated_at = NOW()
WHERE slug = 'bar'
   OR LOWER(name) = 'бар';

UPDATE warehouses
SET
    slug = 'kitchen',
    name = 'Кухня',
    description = 'Кухонный склад',
    is_active = TRUE,
    sort_order = 2,
    updated_at = NOW()
WHERE slug = 'kitchen'
   OR LOWER(name) = 'кухня';

UPDATE warehouses
SET
    slug = 'supplies',
    name = 'Средства',
    description = 'Склад расходных средств',
    is_active = TRUE,
    sort_order = 3,
    updated_at = NOW()
WHERE slug = 'supplies'
   OR LOWER(name) = 'средства';

UPDATE warehouses
SET
    slug = 'meat',
    name = 'Мясо',
    description = 'Мясной склад',
    is_active = TRUE,
    sort_order = 4,
    updated_at = NOW()
WHERE slug = 'meat'
   OR LOWER(name) = 'мясо';

INSERT INTO warehouses (slug, name, description, is_active, sort_order)
SELECT 'bar', 'Бар', 'Барный склад', TRUE, 1
WHERE NOT EXISTS (SELECT 1 FROM warehouses WHERE slug = 'bar');

INSERT INTO warehouses (slug, name, description, is_active, sort_order)
SELECT 'kitchen', 'Кухня', 'Кухонный склад', TRUE, 2
WHERE NOT EXISTS (SELECT 1 FROM warehouses WHERE slug = 'kitchen');

INSERT INTO warehouses (slug, name, description, is_active, sort_order)
SELECT 'supplies', 'Средства', 'Склад расходных средств', TRUE, 3
WHERE NOT EXISTS (SELECT 1 FROM warehouses WHERE slug = 'supplies');

INSERT INTO warehouses (slug, name, description, is_active, sort_order)
SELECT 'meat', 'Мясо', 'Мясной склад', TRUE, 4
WHERE NOT EXISTS (SELECT 1 FROM warehouses WHERE slug = 'meat');

UPDATE requests
SET warehouse = 'Бар'
WHERE LOWER(REPLACE(REPLACE(REPLACE(warehouse, '‘', ''''), '’', ''''), '`', '''')) IN ('bar', 'бар');

UPDATE requests
SET warehouse = 'Кухня'
WHERE LOWER(REPLACE(REPLACE(REPLACE(warehouse, '‘', ''''), '’', ''''), '`', '''')) IN ('kuxna', 'кухня');

UPDATE requests
SET warehouse = 'Средства'
WHERE LOWER(REPLACE(REPLACE(REPLACE(warehouse, '‘', ''''), '’', ''''), '`', '''')) IN ('sredstva', 'средства');

UPDATE requests
SET warehouse = 'Мясо'
WHERE LOWER(REPLACE(REPLACE(REPLACE(warehouse, '‘', ''''), '’', ''''), '`', '''')) IN ('go''sht', 'go‘sht', 'gosht', 'мясо');

UPDATE requests AS r
SET warehouse_id = w.id
FROM warehouses AS w
WHERE w.slug = 'bar'
  AND LOWER(REPLACE(REPLACE(REPLACE(r.warehouse, '‘', ''''), '’', ''''), '`', '''')) IN ('bar', 'бар');

UPDATE requests AS r
SET warehouse_id = w.id
FROM warehouses AS w
WHERE w.slug = 'kitchen'
  AND LOWER(REPLACE(REPLACE(REPLACE(r.warehouse, '‘', ''''), '’', ''''), '`', '''')) IN ('kuxna', 'кухня');

UPDATE requests AS r
SET warehouse_id = w.id
FROM warehouses AS w
WHERE w.slug = 'supplies'
  AND LOWER(REPLACE(REPLACE(REPLACE(r.warehouse, '‘', ''''), '’', ''''), '`', '''')) IN ('sredstva', 'средства');

UPDATE requests AS r
SET warehouse_id = w.id
FROM warehouses AS w
WHERE w.slug = 'meat'
  AND LOWER(REPLACE(REPLACE(REPLACE(r.warehouse, '‘', ''''), '’', ''''), '`', '''')) IN ('go''sht', 'go‘sht', 'gosht', 'мясо');

UPDATE requests AS r
SET warehouse_id = target.id,
    warehouse = target.name
FROM warehouses AS current_warehouse
JOIN warehouses AS target ON target.slug = 'bar'
WHERE r.warehouse_id = current_warehouse.id
  AND current_warehouse.slug IS DISTINCT FROM 'bar'
  AND LOWER(REPLACE(REPLACE(REPLACE(current_warehouse.name, '‘', ''''), '’', ''''), '`', '''')) IN ('bar', 'бар');

UPDATE requests AS r
SET warehouse_id = target.id,
    warehouse = target.name
FROM warehouses AS current_warehouse
JOIN warehouses AS target ON target.slug = 'kitchen'
WHERE r.warehouse_id = current_warehouse.id
  AND current_warehouse.slug IS DISTINCT FROM 'kitchen'
  AND LOWER(REPLACE(REPLACE(REPLACE(current_warehouse.name, '‘', ''''), '’', ''''), '`', '''')) IN ('kuxna', 'кухня');

UPDATE requests AS r
SET warehouse_id = target.id,
    warehouse = target.name
FROM warehouses AS current_warehouse
JOIN warehouses AS target ON target.slug = 'supplies'
WHERE r.warehouse_id = current_warehouse.id
  AND current_warehouse.slug IS DISTINCT FROM 'supplies'
  AND LOWER(REPLACE(REPLACE(REPLACE(current_warehouse.name, '‘', ''''), '’', ''''), '`', '''')) IN ('sredstva', 'средства');

UPDATE requests AS r
SET warehouse_id = target.id,
    warehouse = target.name
FROM warehouses AS current_warehouse
JOIN warehouses AS target ON target.slug = 'meat'
WHERE r.warehouse_id = current_warehouse.id
  AND current_warehouse.slug IS DISTINCT FROM 'meat'
  AND LOWER(REPLACE(REPLACE(REPLACE(current_warehouse.name, '‘', ''''), '’', ''''), '`', '''')) IN ('go''sht', 'go‘sht', 'gosht', 'мясо');

UPDATE warehouses
SET is_active = FALSE, updated_at = NOW()
WHERE COALESCE(slug, '') NOT IN ('bar', 'kitchen', 'supplies', 'meat');

UPDATE requests
SET notification_status = 'failed'
WHERE EXISTS (
    SELECT 1
    FROM audit_logs al
    WHERE al.entity_type = 'request'
      AND al.entity_id = requests.id
      AND al.action_type = 'request_report_failed'
)
OR EXISTS (
    SELECT 1
    FROM system_logs sl
    WHERE sl.event_type = 'report_send_failed'
      AND COALESCE(sl.context->>'request_id', '') ~ '^[0-9]+$'
      AND (sl.context->>'request_id')::BIGINT = requests.id
);

UPDATE requests
SET notification_status = 'sent'
WHERE notification_status NOT IN ('sent', 'failed');
