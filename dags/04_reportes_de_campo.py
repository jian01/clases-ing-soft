"""
DAG 4 — Disparo por EVENTO EXTERNO (sensor) + tareas dinámicas
==============================================================
Concepto: esperar a que pase algo afuera de Airflow y procesar lo que llegue, sin saber
de antemano cuánto va a ser.

  - schedule="@continuous": apenas termina una ejecución arranca la siguiente.
    Siempre hay una "escuchando".
  - Sensor diferido (deferrable=True): mientras espera NO ocupa un worker; la espera la
    hace el triggerer. Un sensor común ocuparía un slot todo el tiempo sin hacer nada.
  - Dynamic task mapping: validar.expand(...) crea UNA tarea por archivo en tiempo de
    ejecución. Si soltás 4 archivos, hay 4 tareas en paralelo.
  - Los reportes válidos van al lake y actualizan el Asset → disparan el DAG 3.
    Los inválidos van a cuarentena con el motivo.

Para probarlo:  cp ejemplos/reportes/*.csv entrantes/
"""

import os
import shutil
from datetime import datetime

from airflow.providers.standard.sensors.filesystem import FileSensor
from airflow.sdk import Asset, dag, task
from airflow.sdk.exceptions import AirflowSkipException

ENTRANTES_DIR = os.environ["ENTRANTES_DIR"]
LAKE_DIR = os.environ["LAKE_DIR"]
CUARENTENA_DIR = os.path.join(LAKE_DIR, "cuarentena")
PRODUCCION = Asset("produccion")

COLUMNAS = ["anio", "mes", "idpozo", "empresa", "tipoextraccion", "tipopozo",
            "prod_pet", "prod_gas", "prod_agua", "tef", "profundidad"]


@dag(
    dag_id="04_reportes_de_campo",
    description="Espera reportes en entrantes/, los valida en paralelo y los sube al lake.",
    schedule="@continuous",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["clase", "4-evento"],
    doc_md=__doc__,
)
def reportes_de_campo():

    esperar = FileSensor(
        task_id="esperar_reportes",
        filepath=os.path.join(ENTRANTES_DIR, "*.csv"),
        deferrable=True,
        poke_interval=5,
        timeout=60 * 60,
        soft_fail=True,  # si en una hora no llega nada: "skipped" (no falla) y arranca otra espera
    )

    @task
    def listar():
        archivos = sorted(f for f in os.listdir(ENTRANTES_DIR) if f.endswith(".csv"))
        print(f"Llegaron {len(archivos)} archivo(s): {archivos}")
        return archivos

    @task(map_index_template="{{ archivo }}")
    def validar(archivo):
        import pandas as pd

        origen = os.path.join(ENTRANTES_DIR, archivo)
        df = pd.read_csv(origen)

        errores = []
        faltan = set(COLUMNAS) - set(df.columns)
        if faltan:
            errores.append(f"faltan columnas: {sorted(faltan)}")
        negativos = int((df.select_dtypes("number") < 0).sum().sum())
        if negativos:
            errores.append(f"{negativos} valores negativos")
        if df.empty:
            errores.append("archivo vacío")

        if errores:
            os.makedirs(CUARENTENA_DIR, exist_ok=True)
            shutil.move(origen, os.path.join(CUARENTENA_DIR, archivo))
            with open(os.path.join(CUARENTENA_DIR, archivo + ".motivo.txt"), "w") as f:
                f.write("\n".join(errores))
            print(f"❌ {archivo} → cuarentena: {'; '.join(errores)}")
            return {"archivo": archivo, "ok": False, "errores": errores}

        anio, mes = int(df["anio"].iloc[0]), int(df["mes"].iloc[0])
        particion = os.path.join(LAKE_DIR, "produccion", f"anio={anio}", f"mes={mes:02d}")
        os.makedirs(particion, exist_ok=True)
        df[COLUMNAS].to_csv(os.path.join(particion, f"campo_{archivo}"), index=False)
        os.remove(origen)
        print(f"✅ {archivo}: {len(df)} filas → {particion}")
        return {"archivo": archivo, "ok": True, "errores": []}

    @task(outlets=[PRODUCCION])
    def resumen(resultados, outlet_events=None):
        resultados = list(resultados)
        validos = [r["archivo"] for r in resultados if r["ok"]]
        print(f"Válidos: {validos}")
        print(f"En cuarentena: {[r['archivo'] for r in resultados if not r['ok']]}")
        if not validos:
            # Una tarea salteada no emite el evento del Asset: sin datos nuevos, no se reentrena.
            raise AirflowSkipException("Ningún reporte válido")
        outlet_events[PRODUCCION].extra = {"archivos": validos}

    archivos = listar()
    esperar >> archivos
    resumen(validar.expand(archivo=archivos))


reportes_de_campo()
