-- Dimensión artista con SCD tipo 2.
-- Cada cambio de género genera una nueva fila con valid_from / valid_to.
-- El registro vigente tiene valid_to = '9999-12-31' e is_current = TRUE.
WITH base AS (
    SELECT
        artista_id,
        nombre,
        genero,
        pais,
        anio_debut,
        fecha_registro                                    AS valid_from,
        LEAD(fecha_registro) OVER (
            PARTITION BY artista_id
            ORDER BY fecha_registro
        )                                                 AS valid_to_raw
    FROM {{ ref('stg_artistas') }}
),

scd AS (
    SELECT
        artista_id,
        nombre,
        genero,
        pais,
        anio_debut,
        valid_from,
        COALESCE(valid_to_raw, '9999-12-31'::date)       AS valid_to
    FROM base
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['artista_id', 'valid_from']) }} AS sk_artista,
    artista_id,
    nombre,
    genero,
    pais,
    anio_debut,
    valid_from,
    valid_to,
    (valid_to = '9999-12-31'::date)                                       AS is_current
FROM scd
