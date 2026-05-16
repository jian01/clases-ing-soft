{{ config(materialized='table') }}

-- Dimensión tiempo: una fila por día desde 2024-01-01 hasta hoy.
-- Se regenera completa en cada corrida (es determinista y barata).
WITH fechas AS (
    SELECT
        generate_series(
            '2024-01-01'::date,
            CURRENT_DATE,
            '1 day'::interval
        )::date AS fecha
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['fecha']) }} AS sk_tiempo,
    fecha,
    EXTRACT(YEAR  FROM fecha)::int                    AS anio,
    EXTRACT(MONTH FROM fecha)::int                    AS mes,
    EXTRACT(DAY   FROM fecha)::int                    AS dia,
    EXTRACT(QUARTER FROM fecha)::int                  AS trimestre,
    EXTRACT(ISODOW FROM fecha)::int                   AS dia_semana,  -- 1=lunes, 7=domingo
    TO_CHAR(fecha, 'TMMonth')                         AS nombre_mes,
    EXTRACT(ISODOW FROM fecha) IN (6, 7)              AS es_fin_de_semana
FROM fechas
