-- Staging de streams desde bronze.
-- Dedup por stream_id tomando la carga mas reciente.
-- Filtramos filas con datos inválidos que no tienen sentido analítico.
WITH raw AS (
    SELECT
        stream_id::int                        AS stream_id,
        fecha::date                           AS fecha,
        cancion_id::int                       AS cancion_id,
        plataforma_id::int                    AS plataforma_id,
        UPPER(TRIM(pais_usuario))::varchar(2) AS pais_usuario,
        reproducciones::int                   AS reproducciones,
        ingresos_usd::numeric(10, 2)          AS ingresos_usd,
        _loaded_at,
        ROW_NUMBER() OVER (
            PARTITION BY stream_id
            ORDER BY _loaded_at DESC
        ) AS rn
    FROM {{ source('bronze', 'streams_raw') }}
    WHERE stream_id IS NOT NULL
)

SELECT
    stream_id,
    fecha,
    cancion_id,
    plataforma_id,
    pais_usuario,
    reproducciones,
    ingresos_usd
FROM raw
WHERE rn = 1
  AND reproducciones > 0
  AND ingresos_usd >= 0
