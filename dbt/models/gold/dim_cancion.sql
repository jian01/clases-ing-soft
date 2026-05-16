-- Dimensión cancion. SCD tipo 1 (se sobreescribe con la version mas reciente).
SELECT
    {{ dbt_utils.generate_surrogate_key(['cancion_id']) }} AS sk_cancion,
    cancion_id,
    artista_id,
    titulo,
    album,
    duracion_seg,
    anio_lanzamiento
FROM {{ ref('stg_canciones') }}
