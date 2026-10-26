"""
DAG 3 — Disparo por DATOS (Assets)
==================================
Concepto: este DAG no tiene horario. Corre cuando ALGUIEN actualiza el Asset "produccion".

  - schedule=[PRODUCCION]: lo dispara el DAG 2 (ingesta mensual) o el DAG 4 (reportes de
    campo). Este DAG no sabe ni le importa quién escribió: solo depende del dato.
  - Si llegan varios eventos mientras está corriendo, se juntan en UNA ejecución.
  - Branching: entrena un modelo nuevo (retador) y lo compara contra el actual (campeón)
    sobre el último mes. Solo lo promueve si es mejor.
  - Registro: cada ejecución deja una fila con datos, hiperparámetros, métricas y decisión.
    Disparalo a mano con otros hiperparámetros y compará en el log de "registrar".
"""

import json
import os
import shutil
from datetime import datetime

from airflow.sdk import Asset, Param, TriggerRule, dag, task
from airflow.sdk.exceptions import AirflowSkipException

LAKE_DIR = os.environ["LAKE_DIR"]
MODELOS_DIR = os.path.join(LAKE_DIR, "modelos")
REGISTRO_CSV = os.path.join(MODELOS_DIR, "registro.csv")
CAMPEON_JSON = os.path.join(MODELOS_DIR, "campeon.json")
PRODUCCION = Asset("produccion")

FEATURES = ["tef", "profundidad", "es_gasifero", "surgencia_natural",
            "prod_pet_mes_anterior", "prod_gas_mes_anterior"]
OBJETIVO = "prod_pet"


@dag(
    dag_id="03_reentrenamiento",
    description="Reentrena el modelo cada vez que llegan datos nuevos al lake.",
    schedule=[PRODUCCION],
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["clase", "3-datos"],
    doc_md=__doc__,
    params={
        "n_estimators": Param(50, type="integer", minimum=5, maximum=300,
                              title="Árboles del Random Forest"),
        "max_depth": Param(8, type="integer", minimum=2, maximum=30,
                           title="Profundidad máxima de cada árbol"),
    },
)
def reentrenamiento():

    @task
    def armar_dataset(triggering_asset_events=None, run_id=None):
        import glob

        import pandas as pd

        eventos = [e for evs in (triggering_asset_events or {}).values() for e in evs]
        print(f"Disparado por {len(eventos)} evento(s) del Asset:")
        for e in eventos:
            print(f"   {e.source_dag_id} / {e.source_run_id}")

        archivos = sorted(glob.glob(os.path.join(LAKE_DIR, "produccion", "*", "*", "*.csv")))
        if not archivos:
            raise ValueError("El lake está vacío: corré primero el DAG 02_ingesta_mensual")
        df = pd.concat([pd.read_csv(a) for a in archivos], ignore_index=True)

        # Feature clave: lo que produjo el mismo pozo el mes anterior.
        df["periodo"] = df["anio"] * 12 + df["mes"]
        df = df.sort_values(["idpozo", "periodo"])
        anterior = df.groupby("idpozo")[["periodo", "prod_pet", "prod_gas"]].shift(1)
        df["prod_pet_mes_anterior"] = anterior["prod_pet"]
        df["prod_gas_mes_anterior"] = anterior["prod_gas"]
        df = df[anterior["periodo"] == df["periodo"] - 1]
        df["es_gasifero"] = (df["tipopozo"] == "Gasífero").astype(int)
        df["surgencia_natural"] = (df["tipoextraccion"] == "Surgencia Natural").astype(int)

        if df["periodo"].nunique() < 2:
            raise AirflowSkipException("Todavía hay pocos meses en el lake para entrenar y evaluar")

        # Evaluamos siempre sobre el ÚLTIMO mes: el modelo nunca lo vio al entrenar.
        ultimo = int(df["periodo"].max())
        carpeta = os.path.join("/tmp", run_id.replace(":", "_"))
        os.makedirs(carpeta, exist_ok=True)
        df[df["periodo"] < ultimo].to_csv(f"{carpeta}/train.csv", index=False)
        df[df["periodo"] == ultimo].to_csv(f"{carpeta}/test.csv", index=False)

        info = {
            "carpeta": carpeta,
            "meses": int(df["periodo"].nunique()),
            "mes_evaluacion": f"{(ultimo - 1) // 12}-{(ultimo - 1) % 12 + 1:02d}",
            "filas_train": int((df["periodo"] < ultimo).sum()),
            "filas_test": int((df["periodo"] == ultimo).sum()),
        }
        print(info)
        return info

    @task
    def entrenar_retador(info, params=None, run_id=None):
        import pickle

        import pandas as pd
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error

        train = pd.read_csv(f"{info['carpeta']}/train.csv")
        test = pd.read_csv(f"{info['carpeta']}/test.csv")
        modelo = RandomForestRegressor(n_estimators=params["n_estimators"],
                                       max_depth=params["max_depth"], n_jobs=1, random_state=42)
        modelo.fit(train[FEATURES], train[OBJETIVO])
        mae = mean_absolute_error(test[OBJETIVO], modelo.predict(test[FEATURES]))

        # Cada modelo con su propio archivo: nunca se pisa una versión anterior.
        version = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(MODELOS_DIR, exist_ok=True)
        ruta = os.path.join(MODELOS_DIR, f"modelo_{version}.pkl")
        with open(ruta, "wb") as f:
            pickle.dump(modelo, f)

        print(f"Retador {version}: MAE = {mae:.1f} m3/mes sobre {info['mes_evaluacion']}")
        return {"version": version, "ruta": ruta, "mae": round(float(mae), 1),
                "n_estimators": params["n_estimators"], "max_depth": params["max_depth"]}

    @task
    def evaluar_campeon(info):
        import pickle

        import pandas as pd
        from sklearn.metrics import mean_absolute_error

        if not os.path.exists(CAMPEON_JSON):
            print("Todavía no hay campeón")
            return None

        with open(CAMPEON_JSON) as f:
            campeon = json.load(f)
        with open(campeon["ruta"], "rb") as f:
            modelo = pickle.load(f)
        test = pd.read_csv(f"{info['carpeta']}/test.csv")
        mae = mean_absolute_error(test[OBJETIVO], modelo.predict(test[FEATURES]))
        print(f"Campeón {campeon['version']}: MAE = {mae:.1f} m3/mes sobre {info['mes_evaluacion']}")
        return {**campeon, "mae": round(float(mae), 1)}

    @task.branch
    def decidir(retador, campeon):
        if campeon is None or retador["mae"] < campeon["mae"]:
            return "promover"
        return "descartar"

    @task
    def promover(retador):
        with open(CAMPEON_JSON, "w") as f:
            json.dump({"version": retador["version"], "ruta": retador["ruta"]}, f)
        shutil.copy(retador["ruta"], os.path.join(MODELOS_DIR, "campeon.pkl"))
        print(f"🏆 Nuevo campeón: {retador['version']}")

    @task
    def descartar(retador, campeon):
        print(f"El retador ({retador['mae']}) no supera al campeón ({campeon['mae']}). "
              f"Queda guardado en {retador['ruta']} pero no se usa.")

    @task(trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)
    def registrar(info, retador, campeon, run_id=None):
        import pandas as pd

        with open(CAMPEON_JSON) as f:
            promovido = json.load(f)["version"] == retador["version"]

        fila = pd.DataFrame([{
            "version": retador["version"],
            "run_id": run_id,
            "meses": info["meses"],
            "filas_train": info["filas_train"],
            "mes_evaluacion": info["mes_evaluacion"],
            "n_estimators": retador["n_estimators"],
            "max_depth": retador["max_depth"],
            "mae_retador": retador["mae"],
            "mae_campeon": campeon["mae"] if campeon else None,
            "decision": "PROMOVIDO" if promovido else "descartado",
        }])
        fila.to_csv(REGISTRO_CSV, mode="a", index=False, header=not os.path.exists(REGISTRO_CSV))
        shutil.rmtree(info["carpeta"], ignore_errors=True)

        print("===== REGISTRO DE MODELOS =====")
        with pd.option_context("display.width", 200, "display.max_columns", None):
            print(pd.read_csv(REGISTRO_CSV).drop(columns=["run_id"]).to_string(index=False))

    info = armar_dataset()
    retador = entrenar_retador(info)
    campeon = evaluar_campeon(info)
    decision = decidir(retador, campeon)
    decision >> [promover(retador), descartar(retador, campeon)] >> registrar(info, retador, campeon)


reentrenamiento()
