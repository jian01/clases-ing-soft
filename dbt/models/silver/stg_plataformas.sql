-- Staging de plataformas desde bronze.
-- Tabla pequeña y estable; dedup por plataforma_id.
WITH raw AS (
    SELECT
        plataforma_id::int        AS plataforma_id,
        TRIM(nombre)::varchar     AS nombre,
        _loaded_at,
        ROW_NUMBER() OVER (
            PARTITION BY plataforma_id
            ORDER BY _loaded_at DESC
        ) AS rn
    FROM {{ source('bronze', 'plataformas_raw') }}
    WHERE plataforma_id IS NOT NULL
)

SELECT
    plataforma_id,
    nombre
FROM raw
WHERE rn = 1
