"""
DAG 2 — Disparo por CALENDARIO (schedule + catchup)
===================================================
Concepto: Airflow no corre "ahora", corre por INTERVALOS de datos.

  - Una ejecución por mes, con INTERVALO DE DATOS: la ejecución del 1/10 procesa
    septiembre [1/9, 1/10). `data_interval_start` dice QUÉ mes procesar, no cuándo corre.
    (En Airflow 3 un cron solo no tiene intervalo: por eso CronDataIntervalTimetable.)
  - catchup=True: al despausarlo, Airflow crea todas las ejecuciones que "faltaron"
    desde start_date hasta hoy (backfill automático).
  - Idempotencia: correr dos veces el mismo mes pisa la misma partición. Por eso se
    puede re-ejecutar cualquier mes sin duplicar datos.
  - Reintentos: la fuente "se cae" a veces. Airflow reintenta solo (retries).
    Pero un dato inválido no se arregla reintentando → AirflowFailException.
  - outlets=[PRODUCCION]: al escribir, avisa que el Asset se actualizó → dispara el DAG 3.
"""

import os
from datetime import datetime, timedelta

from airflow.sdk import Asset, CronDataIntervalTimetable, dag, task
from airflow.sdk.exceptions import AirflowFailException, AirflowSkipException

FUENTE_CSV = os.environ["FUENTE_CSV"]
LAKE_DIR = os.environ["LAKE_DIR"]
PRODUCCION = Asset("produccion")


@dag(
    dag_id="02_ingesta_mensual",
    description="Trae la producción de cada mes y la guarda en el lake. Corre una vez por mes.",
    schedule=CronDataIntervalTimetable("@monthly", timezone="UTC"),
    start_date=datetime(2025, 1, 1),
    catchup=True,
    max_active_runs=3,
    default_args={"retries": 3, "retry_delay": timedelta(seconds=5)},
    tags=["clase", "2-calendario"],
    doc_md=__doc__,
)
def ingesta_mensual():

    @task
    def extraer(data_interval_start=None, ti=None):
        import random

        import pandas as pd

        anio, mes = data_interval_start.year, data_interval_start.month
        print(f"Intervalo de datos: {data_interval_start:%Y-%m} (intento {ti.try_number})")

        # Simulamos una API inestable: el primer intento falla 1 de cada 3 veces.
        if ti.try_number == 1 and random.random() < 0.33:
            raise ConnectionError("La API del ministerio no responde (timeout)")

        df = pd.read_csv(FUENTE_CSV)
        df = df[(df["anio"] == anio) & (df["mes"] == mes)]
        if df.empty:
            raise AirflowSkipException(f"{anio}-{mes:02d} todavía no está publicado")

        salida = f"/tmp/02_crudo_{anio}_{mes:02d}.csv"
        df.to_csv(salida, index=False)
        return salida

    @task
    def validar(crudo):
        import pandas as pd

        df = pd.read_csv(crudo)
        invalidas = (df[["prod_pet", "prod_gas", "prod_agua", "tef"]] < 0).any(axis=1)
        print(f"filas: {len(df)}  |  con valores negativos (se descartan): {invalidas.sum()}")

        # Un dato roto no se arregla reintentando: AirflowFailException falla sin usar los retries.
        if invalidas.mean() > 0.01:
            raise AirflowFailException("Más del 1% de las filas son inválidas: revisar la fuente")

        df[~invalidas].to_csv(crudo, index=False)
        return crudo

    @task(outlets=[PRODUCCION])
    def guardar_particion(limpio, data_interval_start=None):
        import pandas as pd

        anio, mes = data_interval_start.year, data_interval_start.month
        particion = os.path.join(LAKE_DIR, "produccion", f"anio={anio}", f"mes={mes:02d}")
        os.makedirs(particion, exist_ok=True)

        # Mismo mes → mismo archivo: re-ejecutar pisa, no duplica (idempotente).
        destino = os.path.join(particion, "ministerio.csv")
        df = pd.read_csv(limpio)
        df.to_csv(destino, index=False)
        os.remove(limpio)
        print(f"{len(df)} filas → {destino}")

    guardar_particion(validar(extraer()))


ingesta_mensual()
