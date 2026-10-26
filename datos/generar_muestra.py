"""
Genera los datos de la clase a partir del dataset público de la Secretaría de Energía
("Producción de Pozos de Gas y Petróleo No Convencional", ~150 MB):

  datos/fuente/produccion_vaca_muerta.csv.gz   la "fuente oficial" que consultan los DAGs
  ejemplos/reportes/*.csv                      reportes de campo para soltar en entrantes/

Uso (no hace falta para la clase, los archivos ya están en el repo):
  curl -o /tmp/produccion.csv "<URL de abajo>"
  docker run --rm -v "$PWD":/repo -v /tmp:/in -w /repo --entrypoint python \
      apache/airflow:3.3.2 datos/generar_muestra.py /in/produccion.csv
"""

import sys

import numpy as np
import pandas as pd

URL = (
    "http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-1ad3543b407c/resource/"
    "b5b58cdc-9e07-41f9-b392-fb9ec68b0725/download/"
    "produccin-de-pozos-de-gas-y-petrleo-no-convencional.csv"
)
COLUMNAS = [
    "anio", "mes", "idpozo", "empresa", "tipoextraccion", "tipopozo",
    "prod_pet", "prod_gas", "prod_agua", "tef", "profundidad",
]

df = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else URL, usecols=COLUMNAS + ["formacion"])
df = df[
    (df["formacion"] == "vaca muerta")
    & (df["anio"] >= 2023)
    & df["tipopozo"].isin(["Petrolífero", "Gasífero"])
][COLUMNAS].sort_values(["anio", "mes", "idpozo"])
df.to_csv("datos/fuente/produccion_vaca_muerta.csv.gz", index=False)
print(f"fuente: {len(df)} filas, {df['anio'].min()}-{df['anio'].max()}")

# Reportes de campo del mes siguiente al último publicado: parten del último mes real
# con un poco de ruido, como si cada operadora mandara su planilla antes que el ministerio.
rng = np.random.default_rng(42)
ultimo = df[(df["anio"] == df["anio"].max())]
ultimo = ultimo[ultimo["mes"] == ultimo["mes"].max()]
anio, mes = int(ultimo["anio"].iloc[0]), int(ultimo["mes"].iloc[0]) + 1


def reporte(empresa):
    r = ultimo[ultimo["empresa"] == empresa].copy()
    r["mes"] = mes
    for col in ["prod_pet", "prod_gas", "prod_agua"]:
        r[col] = (r[col] * rng.uniform(0.9, 1.05, len(r))).round(3)
    return r


reporte("YPF S.A.").to_csv(f"ejemplos/reportes/{anio}-{mes:02d}_ypf.csv", index=False)
reporte("PLUSPETROL S.A.").to_csv(f"ejemplos/reportes/{anio}-{mes:02d}_pluspetrol.csv", index=False)
reporte("TECPETROL S.A.").to_csv(f"ejemplos/reportes/{anio}-{mes:02d}_tecpetrol.csv", index=False)

# Uno roto a propósito: falta una columna y hay producción negativa.
roto = reporte("SHELL ARGENTINA S.A.").drop(columns=["tef"])
roto.loc[roto.index[:5], "prod_pet"] = -100
roto.to_csv(f"ejemplos/reportes/{anio}-{mes:02d}_shell.csv", index=False)
print(f"reportes de campo para {anio}-{mes:02d}")
