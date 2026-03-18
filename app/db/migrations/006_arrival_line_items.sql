ALTER TABLE requests
    ADD COLUMN IF NOT EXISTS line_items JSONB NOT NULL DEFAULT '[]'::jsonb;

UPDATE requests
SET line_items = jsonb_build_array(
    jsonb_build_object(
        'product_name', product_name,
        'quantity', quantity
    )
)
WHERE operation_type = 'arrival'
  AND COALESCE(product_name, '') <> ''
  AND COALESCE(quantity, '') <> ''
  AND COALESCE(line_items, '[]'::jsonb) = '[]'::jsonb;
