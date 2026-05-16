{{ config(
    materialized='incremental',
    unique_key='stream_id',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
) }}

-- Fact table de streams.
-- Incremental: en corridas parciales solo procesa el dia indicado por run_date.
-- Full refresh: procesa todos los registros.
SELECT
    s.stream_id,
    s.fecha,
    dc.sk_cancion,
    da.sk_artista,
    dp.sk_plataforma,
    dt.sk_tiempo,
    s.pais_usuario,
    s.reproducciones,
    s.ingresos_usd
FROM {{ ref('stg_streams') }} s
JOIN {{ ref('dim_cancion') }}    dc  ON s.cancion_id    = dc.cancion_id
JOIN {{ ref('dim_artista') }}    da  ON dc.artista_id   = da.artista_id
                                    AND s.fecha >= da.valid_from
                                    AND s.fecha  < da.valid_to
JOIN {{ ref('dim_plataforma') }} dp  ON s.plataforma_id = dp.plataforma_id
JOIN {{ ref('dim_tiempo') }}     dt  ON s.fecha         = dt.fecha

{% if is_incremental() %}
WHERE s.fecha = '{{ var("run_date", (modules.datetime.date.today() - modules.datetime.timedelta(days=1)) | string) }}'::date
{% endif %}
