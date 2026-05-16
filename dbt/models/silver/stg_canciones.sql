-- Staging de canciones desde bronze.
-- Dedup: para cada cancion_id tomamos la carga mas reciente.
WITH raw AS (
    SELECT
        cancion_id::int           AS cancion_id,
        artista_id::int           AS artista_id,
        TRIM(titulo)::varchar     AS titulo,
        TRIM(album)::varchar      AS album,
        duracion_seg::int         AS duracion_seg,
        anio_lanzamiento::int     AS anio_lanzamiento,
        _loaded_at,
        ROW_NUMBER() OVER (
            PARTITION BY cancion_id
            ORDER BY _loaded_at DESC
        ) AS rn
    FROM {{ source('bronze', 'canciones_raw') }}
    WHERE cancion_id IS NOT NULL
)

SELECT
    cancion_id,
    artista_id,
    titulo,
    album,
    duracion_seg,
    anio_lanzamiento
FROM raw
WHERE rn = 1
