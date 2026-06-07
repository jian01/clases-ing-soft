# Airflow + MLflow — Detección de Fraude

Pipeline de ML orquestado con **Apache Airflow** y trackeado con **MLflow**.
El caso de uso es detección de fraude en transacciones de tarjeta de crédito.

## Stack

| Servicio | Puerto | Descripción |
|---|---|---|
| Airflow webserver | 8080 | UI para disparar y monitorear DAGs |
| MLflow tracking server | 5000 | UI para comparar experimentos y el Model Registry |
| PostgreSQL | — | Backend de Airflow (interno) |

## Requisitos

- Docker + Docker Compose
- Dataset: [Credit Card Fraud Detection](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) (descargarlo manualmente de Kaggle)

## Setup

### 1. Clonar el repo

```bash
git clone <url-del-repo>
cd clases-ing-soft
```

### 2. Descargar el dataset

Descargar `creditcard.csv` desde [Kaggle — Credit Card Fraud Detection](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) (requiere cuenta de Kaggle) y copiarlo en:

```
data/creditcard.csv
```

Esta carpeta se monta directamente dentro de los contenedores, así que no hace falta ningún paso extra para cargarlo.

### 3. Levantar los servicios

```bash
docker compose up --build -d
```

La primera vez tarda unos minutos (descarga imágenes y buildea el contenedor de Airflow).
Esperar a que todos los servicios estén healthy:

```bash
docker compose ps
```

Cuando `airflow-webserver` y `mlflow` figuren como `healthy`, continuar.

### 4. Abrir las UIs

- **Airflow**: http://localhost:8080 — usuario `admin`, contraseña `admin`
- **MLflow**: http://localhost:5000

## Experimentos de la clase

El DAG `fraud_detection` se dispara manualmente con distintos parámetros. Cada ejecución registra un run en MLflow y compara automáticamente con el mejor modelo actual ("champion").

### Secuencia de runs

Ir a Airflow → DAGs → `fraud_detection` → **Trigger DAG w/ config** y completar el JSON:

**Run 1 — Baseline (el plot twist)**
```json
{
  "model_type": "logistic_regression",
  "class_weight": "none",
  "n_estimators": 100,
  "max_depth": 6,
  "sample_size": 50000
}
```

**Run 2 — Mismo modelo, manejo del desbalance**
```json
{
  "model_type": "logistic_regression",
  "class_weight": "balanced",
  "n_estimators": 100,
  "max_depth": 6,
  "sample_size": 50000
}
```

**Run 3 — Random Forest**
```json
{
  "model_type": "random_forest",
  "class_weight": "balanced",
  "n_estimators": 50,
  "max_depth": 6,
  "sample_size": 50000
}
```

**Run 4 — Random Forest con más árboles**
```json
{
  "model_type": "random_forest",
  "class_weight": "balanced",
  "n_estimators": 200,
  "max_depth": 10,
  "sample_size": 50000
}
```

**Run 5 — XGBoost**
```json
{
  "model_type": "xgboost",
  "class_weight": "balanced",
  "n_estimators": 200,
  "max_depth": 6,
  "sample_size": 50000
}
```

### Qué ver en MLflow después de cada run

1. **Experiments → fraud_detection**: tabla con todos los runs, columnas de métricas comparables
2. **Comparar runs**: seleccionar varios y hacer "Compare" para ver el AUC-PR lado a lado
3. **Models → fraud_detector**: historial de versiones y el alias `champion` apuntando al mejor

## Dependencias

Gestionadas con [uv](https://docs.astral.sh/uv/):

```bash
uv sync        # instala el entorno local desde uv.lock
```

Para actualizar el lockfile:

```bash
uv lock
```

## Apagar

```bash
docker compose down
```

Para borrar también los volúmenes (datos de Airflow y MLflow):

```bash
docker compose down -v
```
