#!/usr/bin/env python3
"""
Herramienta de inyección de datos anómalos para la demo de data quality.

Flujo de clase:
  1. docker compose up  →  correr pipeline en Dagster  →  dbt test TODO verde
  2. python scripts/inject_anomalias.py --scenario <nombre>
  3. Volver a Dagster y re-correr el pipeline
  4. Ver qué alarmas saltan (¡y cuáles NO saltan en 'silencioso'!)
  5. python scripts/inject_anomalias.py --cleanup
  6. Re-correr pipeline  →  todo vuelve a verde

Puede correrse desde el host (POSTGRES_HOST=localhost por defecto)
o desde adentro del container: docker compose exec dagster python /workspace/scripts/inject_anomalias.py
"""
import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone

import psycopg2

# Fecha usada en todos los streams inyectados: ayer (para que el run incremental los levante)
FECHA_INYECCION = (date.today() - timedelta(days=1)).isoformat()

# IDs reservados para cada escenario (bien por encima de los 50.000 reales)
ID_BASE = {
    "pais_invalido":        900_001,
    "ingreso_sospechoso":   910_001,
    "null_en_cancion":      920_001,
    "plataforma_nueva":     930_001,
    "silencioso":           940_001,
    "column_anomaly":       950_002,
}


# ── conexión ──────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "warehouse"),
        user=os.getenv("POSTGRES_USER", "dwh"),
        password=os.getenv("POSTGRES_PASSWORD", "dwh"),
    )


# ── helper ────────────────────────────────────────────────────────────────────

STREAM_SQL = """
    INSERT INTO bronze.streams_raw
        (stream_id, fecha, cancion_id, plataforma_id, pais_usuario,
         reproducciones, ingresos_usd, _loaded_at, _source_file)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

def stream_row(sid, cancion_id, plataforma_id, pais, plays, ingresos, tag):
    return (sid, FECHA_INYECCION, cancion_id, plataforma_id, pais,
            plays, ingresos, datetime.now(timezone.utc), f"injected_{tag}")


# ── escenarios ────────────────────────────────────────────────────────────────

def inyectar_pais_invalido(cur):
    """
    Inserta streams con código de país malformado.

    stg_streams NO filtra por país → pasan a silver con el valor roto.
    Test que falla: assert_stg_streams_valid_pais
    (el test verifica que pais_usuario sea exactamente 2 letras mayúsculas)
    """
    paises_rotos = ["ARG", "ar", "USA", "00", "NONE", "  ", "XX1"]
    rows = [
        stream_row(ID_BASE["pais_invalido"] + i, 1, 1, pais, 1_000, 4.0, "pais_invalido")
        for i, pais in enumerate(paises_rotos)
    ]
    cur.executemany(STREAM_SQL, rows)
    return len(rows)


def inyectar_ingreso_sospechoso(cur):
    """
    Inserta streams con ratio ingreso/reproducción muy por encima del máximo real.
    Máximo real del dataset: $0.012/play (Tidal). Aquí: $10/play (833x el máximo).

    stg_streams NO filtra por ratio → pasan a gold.
    Test que falla: assert_fact_streams_ingreso_por_reproduccion_razonable
    (threshold del test: $0.05/play)
    """
    rows = [
        stream_row(ID_BASE["ingreso_sospechoso"] + i, (i % 1000) + 1, 1, "AR", 100, 1_000.0, "ingreso_sospechoso")
        for i in range(10)
    ]
    cur.executemany(STREAM_SQL, rows)
    return len(rows)


def inyectar_null_en_cancion(cur):
    """
    Inserta streams con cancion_id = NULL.

    stg_streams solo filtra WHERE stream_id IS NOT NULL, no cancion_id.
    Los NULL pasan a silver intactos.
    Test que falla: not_null_stg_streams_cancion_id
    (nota: en gold estos streams se pierden en el JOIN con dim_cancion,
     pero el test de silver los atrapa antes)
    """
    rows = [
        stream_row(ID_BASE["null_en_cancion"] + i, None, 1, "AR", 500, 2.0, "null_en_cancion")
        for i in range(5)
    ]
    cur.executemany(STREAM_SQL, rows)
    return len(rows)


def inyectar_plataforma_nueva(cur):
    """
    Inserta una plataforma desconocida ("TikTok Music") en plataformas_raw
    + streams que la referencian.

    Cadena de propagación:
      bronze.plataformas_raw  →  silver.stg_plataformas (dedup, la nueva aparece)
      →  gold.dim_plataforma  →  test accepted_values falla ("TikTok Music" no está en la lista)

    Test que falla: accepted_values_dim_plataforma_nombre
    """
    loaded_at = datetime.now(timezone.utc)

    # Nueva plataforma en bronze
    cur.execute(
        "INSERT INTO bronze.plataformas_raw (plataforma_id, nombre, _loaded_at, _source_file) "
        "VALUES (%s, %s, %s, %s)",
        (9, "TikTok Music", loaded_at, "injected_plataforma_nueva"),
    )

    # Streams que referencian plataforma_id=9
    rows = [
        stream_row(ID_BASE["plataforma_nueva"] + i, (i % 1000) + 1, 9, "MX", 5_000, 25.0, "plataforma_nueva")
        for i in range(8)
    ]
    cur.executemany(STREAM_SQL, rows)
    return 1 + len(rows)


def inyectar_silencioso(cur):
    """
    Inserta datos inválidos que silver FILTRA SILENCIOSAMENTE.

    silver/stg_streams tiene: WHERE reproducciones > 0 AND ingresos_usd >= 0
    → estas filas se eliminan sin dejar rastro ni alarma.
    NINGÚN test de dbt falla.

    Enseñanza: los tests declarativos no son suficientes.
    Necesitás comparar conteos entre capas (bronze vs silver) para detectar pérdidas.
    Corré --counts después del pipeline para ver el efecto.
    """
    rows = []
    # Ingresos negativos (8 filas)
    for i in range(8):
        rows.append(stream_row(ID_BASE["silencioso"] + i, (i % 1000) + 1, 1, "CO", 1_000, -50.0, "silencioso"))
    # Reproducciones = 0 (8 filas)
    for i in range(8):
        rows.append(stream_row(ID_BASE["silencioso"] + 100 + i, (i % 1000) + 1, 2, "BR", 0, 0.0, "silencioso"))
    cur.executemany(STREAM_SQL, rows)
    return len(rows)


def inyectar_column_anomaly(cur):
    """
    Inserta streams con ingresos altos pero dentro del umbral de ratio ($0.048/play < $0.05).

    Ningún test declarativo falla:
      - not_null ✓               → tiene valor
      - positive_revenue ✓       → ingresos > 0
      - ingreso_por_reproduccion_razonable ✓  → $0.048/play < $0.05 límite

    Pero las estadísticas de ingresos_usd se disparan:
      - max_value: de ~$60 normales a $2.400
      - average:   sube varios órdenes de magnitud respecto al baseline

    Test que alerta: elementary.column_anomalies (max_value, average) en stg_streams y fact_streams.
    IMPORTANTE: requiere al menos 2 runs previos para que Elementary tenga baseline.
    Si es el primer run del día, corré el pipeline una vez limpio antes de inyectar.
    """
    rows = [
        stream_row(
            ID_BASE["column_anomaly"] + i,
            (i % 1000) + 1,
            1,
            "BR",
            5000000,   # reproducciones = máximo del dataset
            2_400.0,  # ingresos = $2400 → ratio $0.048/play (justo bajo el límite de $0.05)
            "column_anomaly2",
        )
        for i in range(5000)
    ]
    cur.executemany(STREAM_SQL, rows)
    return len(rows)


# ── registro de escenarios ────────────────────────────────────────────────────

ESCENARIOS = {
    "pais_invalido": {
        "descripcion": "Streams con código de país malformado (ARG, ar, USA, 00...)",
        "alarma":      "assert_stg_streams_valid_pais  [FALLA]",
        "fn":          inyectar_pais_invalido,
    },
    "ingreso_sospechoso": {
        "descripcion": "Streams con $1000 de ingreso en 100 plays ($10/play vs máximo real $0.012)",
        "alarma":      "assert_fact_streams_ingreso_por_reproduccion_razonable  [FALLA]",
        "fn":          inyectar_ingreso_sospechoso,
    },
    "null_en_cancion": {
        "descripcion": "Streams con cancion_id = NULL (campo requerido)",
        "alarma":      "not_null_stg_streams_cancion_id  [FALLA]",
        "fn":          inyectar_null_en_cancion,
    },
    "plataforma_nueva": {
        "descripcion": 'Nueva plataforma "TikTok Music" que no está en la lista permitida',
        "alarma":      "accepted_values_dim_plataforma_nombre  [FALLA]",
        "fn":          inyectar_plataforma_nueva,
    },
    "silencioso": {
        "descripcion": "Ingresos negativos + reproducciones=0 (silver los filtra sin avisar)",
        "alarma":      "ningún test falla  ← este es el punto",
        "fn":          inyectar_silencioso,
    },
    "column_anomaly": {
        "descripcion": "20 streams con $2400 de ingreso en 50.000 plays ($0.048/play, bajo el límite de $0.05)",
        "alarma":      "elementary.column_anomalies en ingresos_usd (max_value, average)  [ALERTA]",
        "fn":          inyectar_column_anomaly,
    },
}


# ── comandos ──────────────────────────────────────────────────────────────────

def cmd_list():
    print("\nEscenarios disponibles:")
    print(f"  {'NOMBRE':<25}  {'DESCRIPCIÓN'}")
    print(f"  {'-'*25}  {'-'*55}")
    for nombre, meta in ESCENARIOS.items():
        print(f"  {nombre:<25}  {meta['descripcion']}")
        print(f"  {'':<25}  → {meta['alarma']}")
        print()
    print(f"Fecha usada en todos los inserts: {FECHA_INYECCION}")
    print("(ayer, para que el run incremental de Dagster los levante)\n")


def cmd_run(nombre):
    if nombre not in ESCENARIOS:
        print(f"Error: escenario '{nombre}' no existe. Usa --list para ver los disponibles.")
        sys.exit(1)

    meta = ESCENARIOS[nombre]
    print(f"\n── Escenario: {nombre} ──")
    print(f"   {meta['descripcion']}")
    print(f"   Alarma esperada: {meta['alarma']}")
    print(f"   Fecha de datos: {FECHA_INYECCION}")

    try:
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                n = meta["fn"](cur)
        conn.close()
        print(f"\n   {n} filas insertadas en bronze. ✓")
        print("\n   Próximo paso: re-correr el pipeline en Dagster (localhost:3000)")
        print("   y observar cuáles tests fallan en el log de dbt test.\n")
        if nombre == "silencioso":
            print("   ATENCIÓN: con este escenario NO va a fallar ningún test.")
            print("   Después del pipeline, corré:")
            print("     python scripts/inject_anomalias.py --counts")
            print("   para ver cuántas filas desaparecieron silenciosamente.\n")
    except Exception as e:
        print(f"\nError al conectar a Postgres: {e}")
        print("Variables de entorno usadas:")
        print(f"  POSTGRES_HOST={os.getenv('POSTGRES_HOST', 'localhost')}")
        print(f"  POSTGRES_PORT={os.getenv('POSTGRES_PORT', '5432')}")
        print(f"  POSTGRES_DB={os.getenv('POSTGRES_DB', 'warehouse')}")
        sys.exit(1)


def cmd_cleanup():
    print("\nLimpiando filas inyectadas de bronze...")
    try:
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM bronze.streams_raw WHERE _source_file LIKE 'injected_%'")
                streams = cur.rowcount
                cur.execute("DELETE FROM bronze.plataformas_raw WHERE _source_file LIKE 'injected_%'")
                plataformas = cur.rowcount
        conn.close()
        print(f"   bronze.streams_raw:    {streams} filas eliminadas")
        print(f"   bronze.plataformas_raw: {plataformas} filas eliminadas")
        print("\n   Próximo paso: re-correr el pipeline en Dagster.")
        print("   Con --full-refresh para que gold se reconstruya limpio.\n")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_counts():
    """
    Muestra conteos por capa para la fecha inyectada.
    Ideal para demostrar el escenario 'silencioso': las filas existen en bronze
    pero no en silver ni gold.
    """
    print(f"\nConteos de streams para fecha {FECHA_INYECCION}:")
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM bronze.streams_raw WHERE fecha::date = %s",
                (FECHA_INYECCION,)
            )
            bronze_count = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM silver.stg_streams WHERE fecha = %s",
                (FECHA_INYECCION,)
            )
            silver_count = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM gold.fact_streams WHERE fecha = %s",
                (FECHA_INYECCION,)
            )
            gold_count = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM bronze.streams_raw "
                "WHERE fecha::date = %s AND _source_file LIKE 'injected_%'",
                (FECHA_INYECCION,)
            )
            inyectadas = cur.fetchone()[0]

        conn.close()

        print(f"   bronze.streams_raw  : {bronze_count:>6}  (incluye {inyectadas} inyectadas)")
        print(f"   silver.stg_streams  : {silver_count:>6}")
        print(f"   gold.fact_streams   : {gold_count:>6}")
        perdidas = bronze_count - silver_count
        if perdidas > 0:
            print(f"\n   Diferencia bronze→silver: {perdidas} filas desaparecieron en silver.")
            print("   Ningún test lo reportó. Eso es exactamente el problema del escenario 'silencioso'.\n")
        else:
            print("\n   No hay diferencia entre capas para esta fecha.\n")
    except psycopg2.errors.UndefinedTable:
        print("   (Alguna tabla no existe aún — corré el pipeline primero)\n")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Inyección de anomalías en bronze para demo de data quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list",     action="store_true",  help="Listar escenarios disponibles")
    group.add_argument("--scenario", metavar="NOMBRE",     help="Inyectar un escenario")
    group.add_argument("--cleanup",  action="store_true",  help="Eliminar todas las filas inyectadas")
    group.add_argument("--counts",   action="store_true",  help="Mostrar conteos bronze/silver/gold")
    args = parser.parse_args()

    if args.list:
        cmd_list()
    elif args.scenario:
        cmd_run(args.scenario)
    elif args.cleanup:
        cmd_cleanup()
    elif args.counts:
        cmd_counts()


if __name__ == "__main__":
    main()
