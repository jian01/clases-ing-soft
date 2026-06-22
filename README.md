# clases-ing-soft — Concept Drift Demo

Demo de detección de concept drift sobre el dataset de fraude con tarjetas de crédito.

## Requisitos

- pyenv con el virtualenv `udesa14` (Python 3.13)
- El archivo `data/creditcard.csv` (no incluido en el repo)

Instalar dependencias:

```bash
pip install scikit-learn pandas numpy flask evidently duckdb requests
```

## Estructura

```
forecast_api/
  train.py                   # entrena el modelo y genera los splits
  generate_drift_datasets.py # genera los datasets de drift
  app.py                     # API Flask (POST /predict)
data/
  creditcard.csv             # dataset original (no versionado)
  train.csv                  # generado por train.py
  test.csv                   # generado por train.py
  test_gaussian.csv          # generado por generate_drift_datasets.py
  test_sum.csv               # ídem
  test_switching.csv         # ídem
  test_v3_bad.csv            # ídem
pred_log/                    # logs de predicciones (no versionado)
inference_scenarios.py       # notebook jupytext con los escenarios
```

## Paso a paso

### 1. Entrenar el modelo y generar splits

```bash
cd forecast_api
python train.py
```

Genera `data/train.csv`, `data/test.csv` y `forecast_api/model.pkl`.

### 2. Generar datasets de drift

```bash
cd forecast_api
python generate_drift_datasets.py
```

Genera en `data/`:

| Archivo | Tipo de drift |
|---|---|
| `test_gaussian.csv` | Ruido gaussiano uniforme (1× std por feature) — para mixing gradual |
| `test_sum.csv` | Shift de media: se suma la media de cada feature a sí mismo |
| `test_switching.csv` | Permutación por columna — preserva marginales, rompe correlaciones |
| `test_v3_bad.csv` | Corrupción quirúrgica: solo V3 con ruido 10× std |

### 3. Levantar la API

```bash
cd forecast_api
python app.py
```

La API queda en `http://localhost:5000`. Endpoint disponible:

```
POST /predict
Content-Type: application/json

{ "Time": 0.0, "V1": -1.35, ..., "Amount": 149.62 }
```

### 4. Correr los escenarios de drift

Con la API corriendo en otra terminal, abrir `inference_scenarios.py` como notebook:

```bash
pip install jupytext
jupytext --to notebook inference_scenarios.py
jupyter notebook inference_scenarios.ipynb
```

O correrlo directamente como script:

```bash
python inference_scenarios.py
```