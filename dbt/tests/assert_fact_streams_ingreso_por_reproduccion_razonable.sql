-- El ratio ingreso/reproducción no debe superar $0.05 por play.
-- El máximo real es $0.012 (Tidal). Si algún evento supera $0.05/play, hay un error de datos.
-- Este test complementa assert_fact_streams_positive_revenue: uno caza negativos, este caza outliers altos.
SELECT stream_id
FROM {{ ref('fact_streams') }}
WHERE reproducciones > 0
  AND ingresos_usd::numeric / reproducciones > 0.05
