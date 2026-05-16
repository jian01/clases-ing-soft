-- Test personalizado: no debe haber ingresos negativos en fact_streams.
-- Si esta query retorna filas, el test falla.
SELECT stream_id
FROM {{ ref('fact_streams') }}
WHERE ingresos_usd < 0
