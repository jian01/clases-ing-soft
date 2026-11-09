"""
Definicion del dashboard "Data Quality — Anomalias" para la clase de data quality.

Una tab por escenario de scripts/inject_anomalias.py. Cada tab muestra:
  - contadores (cuantas filas "malas" hay en cada capa)
  - las filas crudas tal cual estan en bronze, con su recorrido por silver/gold

Todas las queries son SQL nativo contra el warehouse. No dependen de _source_file:
detectan el problema por su condicion, asi que tambien muestran datos malos "reales".
"""

CATALOGO_PLATAFORMAS = "('Spotify', 'YouTube', 'Apple Music', 'Tidal', 'Amazon Music')"

# Bronze es append-only y todo texto: tomamos la ultima carga de cada stream_id
# (igual que hace silver) para que los conteos sean comparables entre capas.
BRONZE_STREAMS = """bronze_latest AS (
    SELECT DISTINCT ON (stream_id) *
    FROM bronze.streams_raw
    WHERE stream_id IS NOT NULL
    ORDER BY stream_id, _loaded_at DESC
)"""

BRONZE_PLATAFORMAS = """bronze_plat AS (
    SELECT DISTINCT ON (plataforma_id) *
    FROM bronze.plataformas_raw
    WHERE plataforma_id IS NOT NULL
    ORDER BY plataforma_id, _loaded_at DESC
)"""

PAIS_INVALIDO = "(pais_usuario IS NULL OR pais_usuario !~ '^[A-Z]{2}$')"
INVALIDO_SILENCIOSO = "(reproducciones::numeric <= 0 OR ingresos_usd::numeric < 0)"


def _scalar(name, sql):
    return {"name": name, "display": "scalar", "query": sql}


def _table(name, sql):
    return {"name": name, "display": "table", "query": sql}


def _line(name, sql, x, ys):
    return {"name": name, "display": "line", "query": sql,
            "viz": {"graph.dimensions": [x], "graph.metrics": ys}}


# ── 0 · Corridas del pipeline ─────────────────────────────────────────────────

Q_CORRIDAS_BRONZE = """
SELECT COUNT(DISTINCT _loaded_at) AS cargas
FROM bronze.streams_raw
WHERE _source_file NOT LIKE 'injected_%'
"""

Q_FILAS_BRONZE_CRUDAS = "SELECT COUNT(*) AS filas FROM bronze.streams_raw"

Q_STREAM_IDS_BRONZE = "SELECT COUNT(DISTINCT stream_id) AS stream_ids FROM bronze.streams_raw"

Q_FILAS_SILVER = "SELECT COUNT(*) AS filas FROM silver.stg_streams"

Q_FILAS_GOLD = "SELECT COUNT(*) AS filas FROM gold.fact_streams"

Q_CARGAS_BRONZE = """
SELECT _loaded_at AS carga, tabla,
       CASE WHEN _source_file LIKE 'injected_%' THEN 'inyectado' ELSE 'CSV' END AS origen,
       COUNT(*) AS filas
FROM (
  SELECT 'streams_raw'     AS tabla, _loaded_at, _source_file FROM bronze.streams_raw     UNION ALL
  SELECT 'artistas_raw',             _loaded_at, _source_file FROM bronze.artistas_raw    UNION ALL
  SELECT 'canciones_raw',            _loaded_at, _source_file FROM bronze.canciones_raw   UNION ALL
  SELECT 'plataformas_raw',          _loaded_at, _source_file FROM bronze.plataformas_raw
) t
GROUP BY 1, 2, 3
ORDER BY 1, 2
"""

Q_UN_STREAM_POR_CAPA = """
SELECT capa, stream_id, fecha, pais_usuario, reproducciones, ingresos_usd, cargado_en
FROM (
  SELECT 1 AS orden, 'bronze' AS capa, stream_id, fecha, pais_usuario, reproducciones, ingresos_usd,
         _loaded_at::text AS cargado_en
  FROM bronze.streams_raw WHERE stream_id = '1'
  UNION ALL
  SELECT 2, 'silver', stream_id::text, fecha::text, pais_usuario, reproducciones::text, ingresos_usd::text, NULL
  FROM silver.stg_streams WHERE stream_id = 1
  UNION ALL
  SELECT 3, 'gold', stream_id::text, fecha::text, pais_usuario, reproducciones::text, ingresos_usd::text, NULL
  FROM gold.fact_streams WHERE stream_id = 1
) t
ORDER BY orden, cargado_en
"""

# ── Resumen ───────────────────────────────────────────────────────────────────

Q_INYECTADAS = """
SELECT
  (SELECT COUNT(*) FROM bronze.streams_raw     WHERE _source_file LIKE 'injected_%')
+ (SELECT COUNT(*) FROM bronze.plataformas_raw WHERE _source_file LIKE 'injected_%')
  AS filas_inyectadas
"""

Q_DIFF_BRONZE_SILVER = f"""
WITH {BRONZE_STREAMS}
SELECT (SELECT COUNT(*) FROM bronze_latest)
     - (SELECT COUNT(*) FROM silver.stg_streams) AS filas_perdidas
"""

Q_PROBLEMAS_POR_CAPA = f"""
WITH {BRONZE_STREAMS}, {BRONZE_PLATAFORMAS}
SELECT * FROM (VALUES
  ('1. País inválido (no ISO alpha-2)',
     (SELECT COUNT(*) FROM bronze_latest WHERE {PAIS_INVALIDO}),
     (SELECT COUNT(*) FROM silver.stg_streams WHERE {PAIS_INVALIDO}),
     (SELECT COUNT(*) FROM gold.fact_streams  WHERE {PAIS_INVALIDO}),
     'assert_stg_streams_valid_pais'),
  ('2. cancion_id NULL',
     (SELECT COUNT(*) FROM bronze_latest WHERE cancion_id IS NULL),
     (SELECT COUNT(*) FROM silver.stg_streams WHERE cancion_id IS NULL),
     (SELECT COUNT(*) FROM gold.fact_streams  WHERE sk_cancion IS NULL),
     'not_null_stg_streams_cancion_id'),
  ('3. Ingreso por play > $0.05',
     (SELECT COUNT(*) FROM bronze_latest
       WHERE reproducciones::numeric > 0 AND ingresos_usd::numeric / reproducciones::numeric > 0.05),
     (SELECT COUNT(*) FROM silver.stg_streams
       WHERE reproducciones > 0 AND ingresos_usd::numeric / reproducciones > 0.05),
     (SELECT COUNT(*) FROM gold.fact_streams
       WHERE reproducciones > 0 AND ingresos_usd::numeric / reproducciones > 0.05),
     'assert_fact_streams_ingreso_por_reproduccion_razonable'),
  ('4. Plataforma fuera de catálogo',
     (SELECT COUNT(*) FROM bronze_plat           WHERE TRIM(nombre) NOT IN {CATALOGO_PLATAFORMAS}),
     (SELECT COUNT(*) FROM silver.stg_plataformas WHERE nombre NOT IN {CATALOGO_PLATAFORMAS}),
     (SELECT COUNT(*) FROM gold.dim_plataforma    WHERE nombre NOT IN {CATALOGO_PLATAFORMAS}),
     'accepted_values_dim_plataforma_nombre'),
  ('5. Reproducciones <= 0 o ingresos < 0',
     (SELECT COUNT(*) FROM bronze_latest WHERE {INVALIDO_SILENCIOSO}),
     (SELECT COUNT(*) FROM silver.stg_streams WHERE reproducciones <= 0 OR ingresos_usd < 0),
     (SELECT COUNT(*) FROM gold.fact_streams  WHERE reproducciones <= 0 OR ingresos_usd < 0),
     'NINGUNO (silver las filtra en silencio)')
) AS t(problema, en_bronze, en_silver, en_gold, test_que_lo_detecta)
"""

Q_NULOS_POR_COLUMNA = f"""
WITH {BRONZE_STREAMS},
b AS (
  SELECT COUNT(*) FILTER (WHERE fecha          IS NULL) AS fecha,
         COUNT(*) FILTER (WHERE cancion_id     IS NULL) AS cancion_id,
         COUNT(*) FILTER (WHERE plataforma_id  IS NULL) AS plataforma_id,
         COUNT(*) FILTER (WHERE pais_usuario   IS NULL) AS pais_usuario,
         COUNT(*) FILTER (WHERE reproducciones IS NULL) AS reproducciones,
         COUNT(*) FILTER (WHERE ingresos_usd   IS NULL) AS ingresos_usd
  FROM bronze_latest
),
s AS (
  SELECT COUNT(*) FILTER (WHERE fecha          IS NULL) AS fecha,
         COUNT(*) FILTER (WHERE cancion_id     IS NULL) AS cancion_id,
         COUNT(*) FILTER (WHERE plataforma_id  IS NULL) AS plataforma_id,
         COUNT(*) FILTER (WHERE pais_usuario   IS NULL) AS pais_usuario,
         COUNT(*) FILTER (WHERE reproducciones IS NULL) AS reproducciones,
         COUNT(*) FILTER (WHERE ingresos_usd   IS NULL) AS ingresos_usd
  FROM silver.stg_streams
),
g AS (
  SELECT COUNT(*) FILTER (WHERE fecha          IS NULL) AS fecha,
         COUNT(*) FILTER (WHERE sk_cancion     IS NULL) AS cancion_id,
         COUNT(*) FILTER (WHERE sk_plataforma  IS NULL) AS plataforma_id,
         COUNT(*) FILTER (WHERE pais_usuario   IS NULL) AS pais_usuario,
         COUNT(*) FILTER (WHERE reproducciones IS NULL) AS reproducciones,
         COUNT(*) FILTER (WHERE ingresos_usd   IS NULL) AS ingresos_usd
  FROM gold.fact_streams
)
SELECT 'fecha'          AS columna, b.fecha          AS nulos_bronze, s.fecha          AS nulos_silver, g.fecha          AS nulos_gold FROM b, s, g UNION ALL
SELECT 'cancion_id',     b.cancion_id,     s.cancion_id,     g.cancion_id     FROM b, s, g UNION ALL
SELECT 'plataforma_id',  b.plataforma_id,  s.plataforma_id,  g.plataforma_id  FROM b, s, g UNION ALL
SELECT 'pais_usuario',   b.pais_usuario,   s.pais_usuario,   g.pais_usuario   FROM b, s, g UNION ALL
SELECT 'reproducciones', b.reproducciones, s.reproducciones, g.reproducciones FROM b, s, g UNION ALL
SELECT 'ingresos_usd',   b.ingresos_usd,   s.ingresos_usd,   g.ingresos_usd   FROM b, s, g
"""

Q_INYECTADAS_RAW = """
SELECT _source_file, stream_id, fecha, cancion_id, plataforma_id,
       quote_nullable(pais_usuario) AS pais_usuario_literal,
       reproducciones, ingresos_usd, _loaded_at
FROM bronze.streams_raw
WHERE _source_file LIKE 'injected_%'
ORDER BY stream_id::int
LIMIT 500
"""

# ── 1 · País inválido ─────────────────────────────────────────────────────────

Q_PAIS_BRONZE = f"""
WITH {BRONZE_STREAMS}
SELECT COUNT(*) FROM bronze_latest WHERE {PAIS_INVALIDO}
"""

Q_PAIS_SILVER = f"SELECT COUNT(*) FROM silver.stg_streams WHERE pais_usuario IS NOT NULL AND pais_usuario !~ '^[A-Z]{{2}}$'"

Q_PAIS_RAW = f"""
WITH {BRONZE_STREAMS}
SELECT b.stream_id,
       quote_nullable(b.pais_usuario) AS pais_en_bronze,
       LENGTH(b.pais_usuario)         AS largo_bronze,
       quote_nullable(s.pais_usuario) AS pais_en_silver,
       CASE
         WHEN s.stream_id IS NULL                 THEN 'no llegó a silver'
         WHEN s.pais_usuario ~ '^[A-Z]{{2}}$'     THEN 'pasa el test (¡fue transformado!)'
         ELSE 'FALLA el test'
       END AS resultado_test,
       b._source_file
FROM bronze_latest b
LEFT JOIN silver.stg_streams s ON s.stream_id = b.stream_id::int
WHERE {PAIS_INVALIDO.replace('pais_usuario', 'b.pais_usuario')}
ORDER BY b.stream_id::int
LIMIT 500
"""

# ── 2 · cancion_id NULL ───────────────────────────────────────────────────────

Q_NULL_BRONZE = f"""
WITH {BRONZE_STREAMS}
SELECT COUNT(*) FROM bronze_latest WHERE cancion_id IS NULL
"""

Q_NULL_SILVER = "SELECT COUNT(*) FROM silver.stg_streams WHERE cancion_id IS NULL"

Q_NULL_GOLD = f"""
WITH {BRONZE_STREAMS}
SELECT COUNT(*)
FROM bronze_latest b
JOIN gold.fact_streams f ON f.stream_id = b.stream_id::int
WHERE b.cancion_id IS NULL
"""

Q_NULL_RAW = f"""
WITH {BRONZE_STREAMS}
SELECT b.stream_id,
       quote_nullable(b.cancion_id) AS cancion_id_literal,
       b.plataforma_id, b.pais_usuario, b.reproducciones, b.ingresos_usd,
       (s.stream_id IS NOT NULL) AS llego_a_silver,
       (f.stream_id IS NOT NULL) AS llego_a_gold,
       b._source_file
FROM bronze_latest b
LEFT JOIN silver.stg_streams s ON s.stream_id = b.stream_id::int
LEFT JOIN gold.fact_streams  f ON f.stream_id = b.stream_id::int
WHERE b.cancion_id IS NULL
ORDER BY b.stream_id::int
LIMIT 500
"""

# ── 3 · Ingreso sospechoso ────────────────────────────────────────────────────

Q_RATIO_GOLD = """
SELECT COUNT(*) FROM gold.fact_streams
WHERE reproducciones > 0 AND ingresos_usd::numeric / reproducciones > 0.05
"""

Q_RATIO_MAX_NORMAL = """
SELECT ROUND(MAX(ingresos_usd::numeric / reproducciones), 4) AS max_usd_por_play
FROM gold.fact_streams
WHERE reproducciones > 0 AND ingresos_usd::numeric / reproducciones <= 0.05
"""

Q_RATIO_RAW = """
SELECT f.stream_id, f.fecha, p.nombre AS plataforma, f.pais_usuario,
       f.reproducciones, f.ingresos_usd,
       ROUND(f.ingresos_usd::numeric / f.reproducciones, 4) AS usd_por_play,
       ROUND(f.ingresos_usd::numeric / f.reproducciones / 0.012, 0) AS veces_el_maximo_real
FROM gold.fact_streams f
JOIN gold.dim_plataforma p ON p.sk_plataforma = f.sk_plataforma
WHERE f.reproducciones > 0 AND f.ingresos_usd::numeric / f.reproducciones > 0.05
ORDER BY usd_por_play DESC, f.stream_id
LIMIT 500
"""

# ── 4 · Plataforma nueva ──────────────────────────────────────────────────────

Q_PLAT_GOLD = f"SELECT COUNT(*) FROM gold.dim_plataforma WHERE nombre NOT IN {CATALOGO_PLATAFORMAS}"

Q_PLAT_STREAMS_GOLD = f"""
SELECT COUNT(*)
FROM gold.fact_streams f
JOIN gold.dim_plataforma p ON p.sk_plataforma = f.sk_plataforma
WHERE p.nombre NOT IN {CATALOGO_PLATAFORMAS}
"""

Q_PLAT_RAW = f"""
WITH {BRONZE_PLATAFORMAS}
SELECT b.plataforma_id,
       quote_nullable(b.nombre)               AS nombre_en_bronze,
       (TRIM(b.nombre) IN {CATALOGO_PLATAFORMAS}) AS en_catalogo,
       (s.plataforma_id IS NOT NULL)          AS llego_a_silver,
       (g.plataforma_id IS NOT NULL)          AS llego_a_gold,
       (SELECT COUNT(*) FROM gold.fact_streams f WHERE f.sk_plataforma = g.sk_plataforma) AS streams_en_gold,
       b._source_file
FROM bronze_plat b
LEFT JOIN silver.stg_plataformas s ON s.plataforma_id = b.plataforma_id::int
LEFT JOIN gold.dim_plataforma    g ON g.plataforma_id = b.plataforma_id::int
ORDER BY b.plataforma_id::int
"""

# ── 5 · Silencioso ────────────────────────────────────────────────────────────

Q_SIL_BRONZE = f"""
WITH {BRONZE_STREAMS}
SELECT COUNT(*) FROM bronze_latest WHERE {INVALIDO_SILENCIOSO}
"""

Q_SIL_SILVER = "SELECT COUNT(*) FROM silver.stg_streams WHERE reproducciones <= 0 OR ingresos_usd < 0"

Q_SIL_RAW = f"""
WITH {BRONZE_STREAMS}
SELECT b.stream_id, b.fecha, b.pais_usuario,
       b.reproducciones, b.ingresos_usd,
       CASE WHEN b.ingresos_usd::numeric < 0 THEN 'ingresos negativos'
            ELSE 'reproducciones = 0' END AS motivo,
       (s.stream_id IS NOT NULL) AS llego_a_silver,
       (f.stream_id IS NOT NULL) AS llego_a_gold,
       b._source_file
FROM bronze_latest b
LEFT JOIN silver.stg_streams s ON s.stream_id = b.stream_id::int
LEFT JOIN gold.fact_streams  f ON f.stream_id = b.stream_id::int
WHERE {INVALIDO_SILENCIOSO.replace('reproducciones', 'b.reproducciones').replace('ingresos_usd', 'b.ingresos_usd')}
ORDER BY b.stream_id::int
LIMIT 500
"""

Q_CONTEOS_POR_FECHA = f"""
WITH {BRONZE_STREAMS},
bz AS (SELECT fecha::date AS fecha, COUNT(*) AS n FROM bronze_latest GROUP BY 1),
sv AS (SELECT fecha, COUNT(*) AS n FROM silver.stg_streams GROUP BY 1),
gd AS (SELECT fecha, COUNT(*) AS n FROM gold.fact_streams  GROUP BY 1)
SELECT bz.fecha,
       bz.n               AS bronze,
       COALESCE(sv.n, 0)  AS silver,
       COALESCE(gd.n, 0)  AS gold,
       bz.n - COALESCE(sv.n, 0) AS perdidas_bronze_a_silver
FROM bz
LEFT JOIN sv ON sv.fecha = bz.fecha
LEFT JOIN gd ON gd.fecha = bz.fecha
ORDER BY bz.fecha DESC
LIMIT 15
"""

# ── 6 · Column anomaly ────────────────────────────────────────────────────────
# El test de Elementary que alerta es sobre silver.stg_streams.ingresos_usd (average).
# En ese run Dagster no actualiza fact_streams, asi que todo se mira en silver + elementary.

ELEM_AVG_SILVER = """
FROM elementary.data_monitoring_metrics
WHERE full_table_name ILIKE '%.silver.stg_streams'
  AND column_name = 'ingresos_usd'
  AND metric_name = 'average'
"""

Q_AVG_SILVER_AHORA = "SELECT ROUND(AVG(ingresos_usd), 2) AS average_ingresos_usd FROM silver.stg_streams"

Q_AVG_SILVER_BASELINE = f"""
SELECT ROUND(AVG(metric_value)::numeric, 2) AS average_historico
{ELEM_AVG_SILVER}
  AND created_at < (SELECT MAX(created_at) {ELEM_AVG_SILVER})
"""

Q_STATS_SILVER = """
SELECT COUNT(*)                    AS filas,
       MIN(ingresos_usd)           AS min_ingresos,
       ROUND(AVG(ingresos_usd), 2) AS avg_ingresos,
       MAX(ingresos_usd)           AS max_ingresos,
       COUNT(*) FILTER (WHERE ingresos_usd::numeric / NULLIF(reproducciones, 0) BETWEEN 0.04 AND 0.05)
                                   AS filas_cerca_del_limite_005
FROM silver.stg_streams
"""

Q_ELEM_HISTORIAL_AVG = f"""
SELECT created_at AS corrida,
       ROUND(metric_value::numeric, 3) AS average_ingresos_usd
{ELEM_AVG_SILVER}
ORDER BY created_at
"""

Q_ELEM_ANOMALY_RESULTS = """
SELECT detected_at,
       table_name,
       column_name,
       test_sub_type AS metrica,
       status,
       TRIM(REGEXP_REPLACE(test_results_description, '\\s+', ' ', 'g')) AS descripcion
FROM elementary.elementary_test_results
WHERE test_type = 'anomaly_detection'
ORDER BY detected_at DESC, table_name, column_name, test_sub_type
LIMIT 50
"""

# ── 7 · Elementary ────────────────────────────────────────────────────────────

Q_ELEM_METRICAS = """
SELECT LOWER(full_table_name) AS tabla,
       COALESCE(column_name, '(tabla)') AS columna,
       metric_name AS metrica,
       COUNT(*) AS puntos_guardados,
       MAX(created_at) AS ultima_medicion
FROM elementary.data_monitoring_metrics
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3
"""

Q_ELEM_CORRIDAS = """
SELECT COUNT(DISTINCT invocation_id) AS corridas_dbt
FROM elementary.dbt_invocations
"""

Q_ELEM_FALLOS = """
SELECT COUNT(*) AS tests_fallidos
FROM elementary.elementary_test_results
WHERE status IN ('fail', 'error')
"""

Q_ELEM_TEST_RESULTS = """
SELECT detected_at,
       status,
       COALESCE(test_alias, test_short_name) AS test,
       table_name,
       column_name,
       failures
FROM elementary.elementary_test_results
ORDER BY detected_at DESC, (status = 'pass'), table_name, test
LIMIT 300
"""


# ── Layout ────────────────────────────────────────────────────────────────────
# Grilla de Metabase: 24 columnas. Cada tab es una lista de filas; cada fila es
# una lista de (item, ancho, alto). item es un dict de card o un str (texto markdown).

TABS = [
    ("0 · Corridas del pipeline", [
        [("**Qué deja cada corrida del pipeline.** "
          "(1) **Bronze es append-only**: cada corrida recarga los CSV con un `_loaded_at` nuevo, así que bronze tiene "
          "cada fila una vez por corrida; silver se queda con la última carga de cada `stream_id`. "
          "(2) **Elementary guarda una foto por corrida** (métricas como el promedio de `ingresos_usd`), no filas: "
          "con 2 fotos ya tiene un historial contra el cual comparar.", 24, 2)],
        [(_scalar("Corridas del pipeline (cargas en bronze)", Q_CORRIDAS_BRONZE), 5, 3),
         (_scalar("Filas en bronze.streams_raw", Q_FILAS_BRONZE_CRUDAS), 5, 3),
         (_scalar("stream_id distintos en bronze", Q_STREAM_IDS_BRONZE), 5, 3),
         (_scalar("Filas en silver.stg_streams", Q_FILAS_SILVER), 5, 3),
         (_scalar("Filas en gold.fact_streams", Q_FILAS_GOLD), 4, 3)],
        [(_table("Cargas en bronze (una por corrida y tabla)", Q_CARGAS_BRONZE), 12, 6),
         (_table("Un mismo stream (stream_id = 1) en cada capa", Q_UN_STREAM_POR_CAPA), 12, 6)],
        [(_scalar("Corridas de dbt registradas por Elementary", Q_ELEM_CORRIDAS), 6, 6),
         (_line("Historial de Elementary: average de ingresos_usd en silver (un punto por corrida)",
                Q_ELEM_HISTORIAL_AVG, "corrida", ["average_ingresos_usd"]), 18, 6)],
        [(_table("Métricas que guarda Elementary (puntos de historial por métrica)", Q_ELEM_METRICAS), 24, 6)],
    ]),
    ("Resumen", [
        [("**Data Quality — vista por capa.** Cada escenario de `inject_anomalias.py` tiene su tab. "
          "Bronze se cuenta sobre la última carga de cada `stream_id` (igual que silver). "
          "Después de inyectar, re-correr el pipeline en Dagster y refrescar este dashboard.", 24, 2)],
        [(_scalar("Filas inyectadas en bronze", Q_INYECTADAS), 8, 3),
         (_scalar("Filas que desaparecieron entre bronze y silver", Q_DIFF_BRONZE_SILVER), 8, 3),
         (_scalar("Streams con país inválido en silver", Q_PAIS_SILVER), 8, 3)],
        [(_table("Problemas por capa", Q_PROBLEMAS_POR_CAPA), 24, 6)],
        [(_table("Valores nulos por columna y capa", Q_NULOS_POR_COLUMNA), 24, 6)],
        [(_table("Filas inyectadas (crudas, en bronze)", Q_INYECTADAS_RAW), 24, 8)],
    ]),
    ("1 · País inválido", [
        [("**Escenario `pais_invalido`.** Test: `assert_stg_streams_valid_pais` (regex `^[A-Z]{2}$` en silver). "
          "Los valores se muestran entre comillas para ver espacios y mayúsculas. "
          "Comparar `pais_en_bronze` contra `pais_en_silver`: silver aplica `UPPER(TRIM(...))::varchar(2)`.", 24, 2)],
        [(_scalar("Países inválidos en bronze", Q_PAIS_BRONZE), 12, 3),
         (_scalar("Países inválidos en silver (lo que ve el test)", Q_PAIS_SILVER), 12, 3)],
        [(_table("País: bronze vs silver (filas crudas)", Q_PAIS_RAW), 24, 8)],
    ]),
    ("2 · cancion_id NULL", [
        [("**Escenario `null_en_cancion`.** Test: `not_null_stg_streams_cancion_id`. "
          "Las filas llegan a silver pero el JOIN con `dim_cancion` las descarta en gold: "
          "si solo testeáramos gold no las veríamos.", 24, 2)],
        [(_scalar("cancion_id NULL en bronze", Q_NULL_BRONZE), 8, 3),
         (_scalar("cancion_id NULL en silver", Q_NULL_SILVER), 8, 3),
         (_scalar("De esas, cuántas llegaron a gold", Q_NULL_GOLD), 8, 3)],
        [(_table("cancion_id NULL (filas crudas)", Q_NULL_RAW), 24, 8)],
    ]),
    ("3 · Ingreso sospechoso", [
        [("**Escenario `ingreso_sospechoso`.** Test: `assert_fact_streams_ingreso_por_reproduccion_razonable` "
          "(umbral $0.05/play; máximo real del dataset ≈ $0.012/play, Tidal). "
          "Ni `not_null` ni `unique` lo detectan: hace falta un test que conozca el negocio.", 24, 2)],
        [(_scalar("Streams en gold con > $0.05 por play", Q_RATIO_GOLD), 12, 3),
         (_scalar("Máximo USD/play de los streams normales", Q_RATIO_MAX_NORMAL), 12, 3)],
        [(_table("Ingreso por play sospechoso (filas crudas en gold)", Q_RATIO_RAW), 24, 8)],
    ]),
    ("4 · Plataforma nueva", [
        [("**Escenario `plataforma_nueva`.** Test: `accepted_values` en `dim_plataforma.nombre`. "
          "Una fila en una tabla de catálogo chica viaja bronze → silver → gold y arrastra sus streams a la fact.", 24, 2)],
        [(_scalar("Plataformas fuera de catálogo en gold", Q_PLAT_GOLD), 12, 3),
         (_scalar("Streams en gold de esas plataformas", Q_PLAT_STREAMS_GOLD), 12, 3)],
        [(_table("Plataformas: recorrido bronze → silver → gold", Q_PLAT_RAW), 24, 6)],
    ]),
    ("5 · Silencioso", [
        [("**Escenario `silencioso`.** Ningún test falla: silver tiene "
          "`WHERE reproducciones > 0 AND ingresos_usd >= 0` y las filas desaparecen sin aviso. "
          "La única forma de verlo es comparar conteos entre capas.", 24, 2)],
        [(_scalar("Filas inválidas en bronze", Q_SIL_BRONZE), 8, 3),
         (_scalar("Filas inválidas en silver", Q_SIL_SILVER), 8, 3),
         (_scalar("Filas que desaparecieron entre bronze y silver", Q_DIFF_BRONZE_SILVER), 8, 3)],
        [(_table("Filas filtradas en silencio (crudas, en bronze)", Q_SIL_RAW), 24, 7)],
        [(_table("Conteos por fecha y capa (últimas 15 fechas)", Q_CONTEOS_POR_FECHA), 24, 7)],
    ]),
    ("6 · Column anomaly", [
        [("**Escenario `column_anomaly`.** Cada fila es válida ($0.048/play < $0.05) y ningún test declarativo falla, "
          "pero el promedio de `ingresos_usd` en silver se dispara. Lo detecta `elementary.column_anomalies` comparando "
          "contra el historial que guardó en cada corrida. Como el test es de silver, Dagster no actualiza la fact: todo se mira en silver.", 24, 2)],
        [(_scalar("Average ingresos_usd en silver — ahora", Q_AVG_SILVER_AHORA), 12, 3),
         (_scalar("Average histórico según Elementary (corridas anteriores)", Q_AVG_SILVER_BASELINE), 12, 3)],
        [(_line("Historial de Elementary: average de ingresos_usd en silver (un punto por corrida)",
                Q_ELEM_HISTORIAL_AVG, "corrida", ["average_ingresos_usd"]), 14, 6),
         (_table("Historial de Elementary (valores)", Q_ELEM_HISTORIAL_AVG), 10, 6)],
        [(_table("Silver ahora: estadísticas de ingresos_usd", Q_STATS_SILVER), 24, 3)],
        [(_table("Resultados de los tests de anomalías (Elementary)", Q_ELEM_ANOMALY_RESULTS), 24, 7)],
    ]),
    ("7 · Elementary", [
        [("**Qué guarda Elementary.** En cada corrida de dbt, Elementary guarda métricas de las tablas monitoreadas "
          "(`elementary.data_monitoring_metrics`) y el resultado de cada test (`elementary.elementary_test_results`). "
          "Los monitores de anomalías comparan la última medición contra ese historial: con `min_training_set_size: 2` "
          "necesitan al menos dos corridas previas.", 24, 2)],
        [(_scalar("Corridas de dbt registradas", Q_ELEM_CORRIDAS), 12, 3),
         (_scalar("Tests fallidos en el historial", Q_ELEM_FALLOS), 12, 3)],
        [(_table("Métricas que guarda Elementary", Q_ELEM_METRICAS), 24, 6)],
        [(_table("Historial de resultados de tests (todas las corridas)", Q_ELEM_TEST_RESULTS), 24, 9)],
    ]),
]
