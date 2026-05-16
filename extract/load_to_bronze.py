"""
Carga todos los CSVs de /workspace/data a la capa bronze de Postgres.
Modo append-only: cada corrida agrega filas con _loaded_at nuevo para auditoria.
La capa silver se encarga de deduplicar usando business_key + max(_loaded_at).
"""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

DATA_DIR = Path(os.getenv("DATA_DIR", "/workspace/data"))

# Mapeo: nombre de archivo CSV → nombre de tabla en bronze
TABLE_MAP = {
    "artistas.csv": "artistas_raw",
    "canciones.csv": "canciones_raw",
    "plataformas.csv": "plataformas_raw",
    "streams.csv": "streams_raw",
}


def build_engine():
    host = os.environ["POSTGRES_HOST"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def load_csv_to_bronze(engine, csv_path: Path, table_name: str, loaded_at: datetime, logger=None) -> int:
    log = logger or logging.getLogger(__name__)
    df = pd.read_csv(csv_path, dtype=str)  # todo como texto en bronze

    df["_loaded_at"] = loaded_at
    df["_source_file"] = csv_path.name

    df.to_sql(
        name=table_name,
        con=engine,
        schema="bronze",
        if_exists="append",
        index=False,
    )
    log.info("Cargado %s → bronze.%s (%d filas)", csv_path.name, table_name, len(df))
    return len(df)


def load_all_csvs(logger=None) -> int:
    """
    Punto de entrada reutilizable desde Dagster u otros orquestadores.
    Retorna el total de filas cargadas.
    """
    log = logger or logging.getLogger(__name__)
    engine = build_engine()
    loaded_at = datetime.now(timezone.utc)
    total = 0

    for filename, table_name in TABLE_MAP.items():
        csv_path = DATA_DIR / filename
        if not csv_path.exists():
            log.warning("Archivo no encontrado, saltando: %s", csv_path)
            continue
        n = load_csv_to_bronze(engine, csv_path, table_name, loaded_at, logger=log)
        total += n

    log.info("Total filas cargadas a bronze: %d", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_all_csvs()
