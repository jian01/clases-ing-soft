# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.3
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Escenarios de inferencia + detección de drift
#
# Cada escenario:
# 1. Vacía `pred_log/`
# 2. Envía filas a la API via `POST /predict`
# 3. Lee los logs con DuckDB SQL y corre los detectores de drift vs el reference set (train.csv)
#
# **Prerequisito**: la API debe estar corriendo en otra terminal:
# ```bash
# cd forecast_api && python app.py
# ```

# %% [markdown]
# ## Setup

# %%
import shutil
import warnings
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import evidently
import numpy as np
import pandas as pd
import requests
from evidently.metrics import DriftedColumnsCount, ValueDrift
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

warnings.filterwarnings("ignore")

API_URL  = "http://127.0.0.1:5000/predict"
LOG_DIR  = Path("pred_log")
FEATURES = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount"]
N_ROWS   = 1000
P_VAL    = 0.05

# %% [markdown]
# ## Reference set

# %%
ref_df = pd.read_csv("data/train.csv")[FEATURES]
print(f"Reference: {ref_df.shape}")

# %% [markdown]
# ## Helpers

# %%
def clear_logs():
    if LOG_DIR.exists():
        shutil.rmtree(LOG_DIR)
    LOG_DIR.mkdir()


def send_scenario(df: pd.DataFrame, n: int = N_ROWS) -> datetime:
    sample   = df[FEATURES].sample(min(n, len(df)), random_state=42)
    start_ts = datetime.now(timezone.utc)
    for _, row in sample.iterrows():
        requests.post(API_URL, json=row.to_dict())
    return start_ts


def _drift_report(method: str, cur: pd.DataFrame) -> dict:
    per_col = [ValueDrift(column=col, method=method, threshold=0.05) for col in FEATURES]
    snap = evidently.Report(metrics=[DriftedColumnsCount(method=method, drift_share=0.05), *per_col]).run(
        current_data=cur, reference_data=ref_df
    )
    d      = snap.dict()["metrics"]
    scores = {FEATURES[i]: m["value"] for i, m in enumerate(d[1:])}
    drifted_scores = {f: p for f, p in scores.items() if p < P_VAL}
    return {
        "is_drift":         d[0]["value"]["share"] >= 0.5,
        "drifted_share":    d[0]["value"]["share"],
        "drifted_features": sorted(drifted_scores, key=drifted_scores.get),
        "scores":           scores,
    }


def run_detectors(since: datetime) -> pd.DataFrame:
    since_str = since.isoformat()
    recent = duckdb.sql(f"""
        SELECT *
        FROM read_json_auto('pred_log/*.json')
        WHERE datetime >= '{since_str}'
    """).df()

    if len(recent) == 0:
        print("  Sin predicciones en el log.")
        return pd.DataFrame()

    cur = recent[FEATURES]
    print(f"  Filas leídas del log: {len(cur)}")

    rows = []

    # KSDrift
    ks = _drift_report("ks", cur)
    rows.append({"método": "KSDrift", "drift": ks["is_drift"],
                 "share drifted": ks["drifted_share"],
                 "features drifteados (p-value)": ", ".join(
                     f"{f} ({ks['scores'][f]:.2e})" for f in ks["drifted_features"]
                 ) or "—"})

    # CVMDrift
    cvm = _drift_report("cramer_von_mises", cur)
    rows.append({"método": "CVMDrift", "drift": cvm["is_drift"],
                 "share drifted": cvm["drifted_share"],
                 "features drifteados (p-value)": ", ".join(
                     f"{f} ({cvm['scores'][f]:.2e})" for f in cvm["drifted_features"]
                 ) or "—"})

    # ClassifierDrift manual (RandomForest)
    X_ref_sub = ref_df.sample(len(cur), random_state=42).values
    X_combined = np.vstack([X_ref_sub, cur.values])
    y_combined = np.array([0] * len(X_ref_sub) + [1] * len(cur))
    acc = cross_val_score(
        RandomForestClassifier(n_estimators=50, random_state=42),
        X_combined, y_combined, cv=5, scoring="accuracy"
    ).mean()
    rows.append({"método": "ClassifierDrift (RF)", "drift": acc > 0.55,
                 "share drifted": f"acc={acc:.3f}",
                 "features drifteados (p-value)": "—"})

    summary = pd.DataFrame(rows)
    summary["drift"] = summary["drift"].map({True: "✓ SI", False: "✗ NO"})
    return summary


def run_scenario(label: str, df: pd.DataFrame):
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"{'='*65}")
    clear_logs()
    since = send_scenario(df)
    summary = run_detectors(since)
    print()
    print(summary.to_string(index=False))
    return summary

# %% [markdown]
# ---
# # Escenario 1 — Baseline: `test.csv`
#
# Enviamos filas del mismo set de test que proviene de la **misma distribución** que el reference (train).
#
# <details><summary>Esperado</summary>
#
# Todos los detectores en `✗ NO` — no hay drift, es el sanity check del pipeline.
#
# </details>

# %%
test_df = pd.read_csv("data/test.csv")
run_scenario("Escenario 1 — Baseline: test.csv (sin drift)", test_df)

# %% [markdown]
# ---
# # Escenario 2 — Drift quirúrgico: `test_v3_bad.csv`
#
# Solo el feature **V3** tiene ruido gaussiano de 10× su desvío estándar. El resto intacto.
#
# <details><summary>Esperado</summary>
#
# Flag global `✗ NO` en KS y CVM porque 1/30 features está por debajo del `drift_share=0.5`. Sin embargo, **V3 aparece en la columna de p-values** con un valor cercano a cero — los tests por-feature te dicen dónde está el problema aunque no salte el flag global. ClassifierDrift `✓ SI` porque el RF detecta el cambio en V3 directamente.
#
# </details>

# %%
v3_bad_df = pd.read_csv("data/test_v3_bad.csv")
run_scenario("Escenario 2 — Drift quirúrgico en V3", v3_bad_df)

# %% [markdown]
# ---
# # Escenario 3 — Zona gris: 50% test + 50% gaussian
#
# Mitad de filas normales, mitad con ruido gaussiano (1× std por feature). Drift moderado.
#
# <details><summary>Esperado</summary>
#
# KS y CVM `✓ SI` — contra-intuitivo: el ruido no desplaza la media pero duplica la varianza, y KS detecta cualquier cambio de forma. ClassifierDrift `✓ SI` también con RF, aunque con accuracy moderada (~0.70) porque los valores ruidosos y limpios se solapan.
#
# </details>

# %%
gaussian_df = pd.read_csv("data/test_gaussian.csv")
mix_50 = pd.concat([
    test_df.sample(N_ROWS // 2, random_state=1),
    gaussian_df.sample(N_ROWS // 2, random_state=1),
]).sample(frac=1, random_state=42)
run_scenario("Escenario 3 — Zona gris: 50% normal + 50% gaussian", mix_50)

# %% [markdown]
# ---
# # Escenario 4 — Ruido gaussiano total: `test_gaussian.csv`
#
# 100% de filas con ruido gaussiano (1× std). Sin filas limpias que amortigüen.
#
# <details><summary>Esperado</summary>
#
# Mismo patrón que el escenario 3 pero más marcado. KS y CVM `✓ SI` en todos los features. ClassifierDrift `✓ SI` con accuracy alta (~0.95) — con 100% de ruido la separación entre distribuciones es más clara que con el 50%.
#
# </details>

# %%
run_scenario("Escenario 4 — Ruido gaussiano total: test_gaussian.csv", gaussian_df)

# %% [markdown]
# ---
# # Escenario 5 — Shift de media: `test_sum.csv`
#
# A cada feature se le suma su propia media. Intuitivamente parece el drift más obvio.
#
# <details><summary>Esperado</summary>
#
# KS y CVM `✗ NO` — sorpresa: V1–V28 son componentes PCA con media ≈ 0, así que sumarles la media casi no los cambia. Solo `Time` y `Amount` driftean, insuficiente para superar el `drift_share=0.5`. ClassifierDrift `✓ SI` (~0.97) porque el RF ve el patrón global aunque cada test individual no alcance el umbral.
#
# </details>

# %%
sum_df = pd.read_csv("data/test_sum.csv")
run_scenario("Escenario 5 — Shift de media: test_sum.csv", sum_df)

# %% [markdown]
# ---
# # Escenario 6 — Drift estructural: `test_switching.csv`
#
# Permutación independiente por columna: preserva exactamente las distribuciones marginales pero destruye todas las correlaciones entre features.
#
# <details><summary>Esperado</summary>
#
# KS y CVM `✗ NO` — por construcción: las marginales están intactas y estos tests solo las miran. ClassifierDrift `✓ SI` (~0.89) porque el RF aprende que ciertas combinaciones de valores entre features no existen en data real. Con LogisticRegression el resultado sería `✗ NO` (~0.5) — la elección del discriminador importa tanto como la del método.
#
# </details>

# %%
switching_df = pd.read_csv("data/test_switching.csv")
run_scenario("Escenario 6 — Drift estructural: test_switching.csv", switching_df)

# %%
