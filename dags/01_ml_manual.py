"""
DAG 1 — Disparo MANUAL con parámetros
=====================================
Concepto: qué es un DAG, cómo se encadenan tareas y cómo viajan los datos entre ellas.

  - TaskFlow API: cada @task es una función de Python. Lo que devuelve viaja a la
    siguiente tarea por XCom (Airflow lo guarda en su base de metadatos).
  - Fan-out / fan-in: los dos modelos se entrenan EN PARALELO y después se juntan.
  - Params: al hacer "Trigger" la UI muestra un formulario armado con estos parámetros.
"""

import os
from datetime import datetime

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import Param, dag, task

FUENTE_CSV = os.environ["FUENTE_CSV"]
MODELOS_DIR = os.path.join(os.environ["LAKE_DIR"], "modelos_manual")
FEATURES = ["anio", "mes", "tef", "profundidad", "tipoextraccion"]
TIPOS_EXTRACCION = ["Surgencia Natural", "Gas Lift", "Bombeo Mecánico", "Plunger Lift"]


@dag(
    dag_id="01_ml_manual",
    description="Entrena dos modelos en paralelo. Se dispara a mano, con parámetros.",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    tags=["clase", "1-manual"],
    doc_md=__doc__,
    params={
        "fecha_desde": Param("2025-01-01", type="string", format="date",
                             title="Fecha desde", description="Entrenar con datos desde este mes"),
        "fecha_hasta": Param("2026-09-30", type="string", format="date",
                             title="Fecha hasta", description="... y hasta este mes"),
        "n_estimators": Param(50, type="integer", minimum=5, maximum=300,
                              title="Árboles del Random Forest"),
        "pozo_tef": Param(30.0, type="number", minimum=0, maximum=31,
                          title="Pozo a predecir: días en producción en el mes"),
        "pozo_profundidad": Param(3000, type="integer", minimum=500, maximum=6000,
                                  title="Pozo a predecir: profundidad (m)"),
        "pozo_extraccion": Param("Surgencia Natural", type="string", enum=TIPOS_EXTRACCION,
                                 title="Pozo a predecir: tipo de extracción"),
    },
)
def ml_manual():

    inicio = EmptyOperator(task_id="inicio")

    @task
    def preprocesar(params=None):
        import pandas as pd

        df = pd.read_csv(FUENTE_CSV)
        df["fecha"] = pd.to_datetime(dict(year=df["anio"], month=df["mes"], day=1))
        df = df[(df["fecha"] >= params["fecha_desde"]) & (df["fecha"] <= params["fecha_hasta"])]
        if df.empty:
            raise ValueError("No hay datos en ese rango de fechas")

        df = df[df["tipoextraccion"].isin(TIPOS_EXTRACCION)]
        df["tipoextraccion"] = df["tipoextraccion"].map(TIPOS_EXTRACCION.index)
        df = df[FEATURES + ["prod_pet", "prod_gas"]].dropna()

        # Por XCom viaja solo la ruta, no el dataframe: XCom es para mensajes chicos.
        salida = "/tmp/01_preprocesado.csv"
        df.to_csv(salida, index=False)
        print(f"{len(df)} filas entre {params['fecha_desde']} y {params['fecha_hasta']}")
        return salida

    @task
    def entrenar(datos, objetivo, params=None):
        import pickle

        import pandas as pd
        from sklearn.ensemble import RandomForestRegressor

        df = pd.read_csv(datos)
        modelo = RandomForestRegressor(n_estimators=params["n_estimators"], max_depth=12,
                                       n_jobs=1, random_state=42)
        modelo.fit(df[FEATURES], df[objetivo])

        os.makedirs(MODELOS_DIR, exist_ok=True)
        ruta = os.path.join(MODELOS_DIR, f"{objetivo}.pkl")
        with open(ruta, "wb") as f:
            pickle.dump(modelo, f)
        return {"objetivo": objetivo, "modelo": ruta, "filas": len(df)}

    @task
    def predecir(info, params=None):
        import pickle

        import pandas as pd

        with open(info["modelo"], "rb") as f:
            modelo = pickle.load(f)

        pozo = pd.DataFrame([{
            "anio": 2026,
            "mes": 10,
            "tef": params["pozo_tef"],
            "profundidad": params["pozo_profundidad"],
            "tipoextraccion": TIPOS_EXTRACCION.index(params["pozo_extraccion"]),
        }])
        return {**info, "prediccion": round(float(modelo.predict(pozo)[0]), 1)}

    @task
    def mostrar_resultados(resultados, params=None):
        print("===== RESULTADOS =====")
        print(f"Pozo: {params['pozo_extraccion']}, {params['pozo_profundidad']} m, "
              f"{params['pozo_tef']} días en producción")
        unidades = {"prod_pet": "m3 de petróleo", "prod_gas": "miles de m3 de gas"}
        for r in resultados:
            print(f"  {r['objetivo']:<9} → {r['prediccion']:>10} {unidades[r['objetivo']]}"
                  f"   (entrenado con {r['filas']} filas)")

    datos = preprocesar()
    inicio >> datos

    predicciones = [predecir(entrenar(datos, objetivo)) for objetivo in ["prod_pet", "prod_gas"]]
    mostrar_resultados(predicciones)


ml_manual()
