-- Staging de artistas desde bronze.
-- Mantenemos TODAS las versiones (no dedup por artista_id) para que dim_artista
-- pueda construir el historial SCD2.
-- Solo eliminamos duplicados exactos usando la carga mas reciente.
WITH raw AS (
    SELECT
        artista_id::int                   AS artista_id,
        TRIM(nombre)::varchar             AS nombre,
        TRIM(genero)::varchar             AS genero,
        UPPER(TRIM(pais))::varchar(2)     AS pais,
        anio_debut::int                   AS anio_debut,
        fecha_registro::date              AS fecha_registro,
        _loaded_at,
        ROW_NUMBER() OVER (
            PARTITION BY artista_id, fecha_registro
            ORDER BY _loaded_at DESC
        ) AS rn
    FROM {{ source('bronze', 'artistas_raw') }}
    WHERE artista_id IS NOT NULL
)

SELECT
    artista_id,
    nombre,
    genero,
    pais,
    anio_debut,
    fecha_registro
FROM raw
WHERE rn = 1
