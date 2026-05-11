# Airflow — Ejemplo de clase

Apache Airflow 2.9 corriendo en Docker con un pipeline ETL y entrenamiento de Random Forest.

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) >= 24
- [Docker Compose](https://docs.docker.com/compose/install/) >= 2.20

## Estructura

```
.
├── docker-compose.yml
├── dags/
│   ├── etl_parametrizado.py     # DAG ETL: descarga, transforma y hace split
│   └── entrenamiento_rf.py      # DAG ML: Random Forest con hyperparameter search
├── data/                        # Volumen Docker interno — datasets y modelos generados
├── logs/                        # Volumen Docker interno — accesibles desde la UI
└── plugins/
```

## Servicios del docker-compose

| Servicio            | Rol                                                                                                                                                                        |
|---------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `postgres`          | Base de datos relacional donde Airflow guarda el estado de los DAGs, runs, tareas, usuarios y conexiones. Sin este servicio Airflow no puede arrancar.                    |
| `airflow-init`      | Contenedor de un solo uso que corre al inicio: aplica las migraciones de la base de datos (`db migrate`) y crea el usuario `admin`. Se ejecuta una vez y termina.         |
| `airflow-webserver` | Sirve la UI en http://localhost:8080. Desde acá se visualizan los DAGs, se triggerean runs, se ven logs y se administran conexiones/variables.                            |
| `airflow-scheduler` | Proceso central de Airflow. Monitorea los DAGs en `dags/`, evalúa cuándo deben ejecutarse según su `schedule_interval` y envía las tareas al ejecutor (`LocalExecutor`). |

---

## 1. Levantar el entorno

```bash
# Primera vez: inicializa la base de datos y crea el usuario admin
docker-compose up airflow-init

# Levantar todos los servicios
docker-compose up -d
```

Airflow queda disponible en **http://localhost:8080**

| Campo    | Valor   |
|----------|---------|
| Usuario  | `admin` |
| Password | `admin` |

> La primera vez tarda ~3-5 minutos extra porque instala scikit-learn y las dependencias en los contenedores.

---

## 2. Correr por la UI

### ETL

1. Entrá a http://localhost:8080 y buscá el DAG `etl_parametrizado`
2. Activalo con el toggle de la izquierda
3. Hacé click en ▶ → **Trigger DAG w/ config**
4. Completá los parámetros y ejecutá:

```json
{
  "csv_url": "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv",
  "target_column": "Survived",
  "test_size": 0.2,
  "ignore_columns": ["PassengerId", "Name", "Ticket", "Cabin"]
}
```

5. Entrá al run → tarea `descargar_y_validar` → **Logs**
6. Al final del log vas a ver:

```
etl_run_id para el DAG de entrenamiento: manual__2024_01_01T00_00_00_00_00
```

Copiá ese valor.

### Entrenamiento

1. Buscá el DAG `entrenamiento_random_forest`
2. Activalo con el toggle y hacé click en ▶ → **Trigger DAG w/ config**
3. Pegá el `etl_run_id` copiado:

```json
{
  "etl_run_id": "manual__2024_01_01T00_00_00_00_00",
  "n_iter": 20
}
```

4. En los logs de `entrenar_y_evaluar` vas a ver las métricas al finalizar.

---

## 3. Correr por API

### Activar los DAGs (una sola vez)

Los DAGs arrancan pausados. Antes del primer run hay que activarlos:

```bash
curl -X PATCH http://localhost:8080/api/v1/dags/etl_parametrizado \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{"is_paused": false}'

curl -X PATCH http://localhost:8080/api/v1/dags/entrenamiento_random_forest \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{"is_paused": false}'
```

### Ejemplo con Titanic

**ETL:**
```bash
curl -X POST http://localhost:8080/api/v1/dags/etl_parametrizado/dagRuns \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "conf": {
      "csv_url": "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv",
      "target_column": "Survived",
      "test_size": 0.2,
      "ignore_columns": ["PassengerId", "Name", "Ticket", "Cabin"]
    }
  }'
```

**Resultado ETL:** 891 filas, 8 features → 23 features transformadas (OHE sobre Sex/Embarked, StandardScaler sobre numéricas, Ordinal sobre Age/Fare por alta cardinalidad).

**Entrenamiento:**
```bash
curl -X POST http://localhost:8080/api/v1/dags/entrenamiento_random_forest/dagRuns \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "conf": {
      "etl_run_id": "<etl_run_id del paso anterior>",
      "n_iter": 20
    }
  }'
```

**Métricas Titanic:**

| Métrica   | Valor  |
|-----------|--------|
| Accuracy  | 0.8045 |
| Precision | 0.8036 |
| Recall    | 0.6522 |
| F1        | 0.7200 |
| ROC-AUC   | 0.8358 |

---

### Ejemplo con Heart Disease

**ETL:**
```bash
curl -X POST http://localhost:8080/api/v1/dags/etl_parametrizado/dagRuns \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "conf": {
      "csv_url": "https://storage.googleapis.com/download.tensorflow.org/data/heart.csv",
      "target_column": "target",
      "test_size": 0.2,
      "ignore_columns": []
    }
  }'
```

**Resultado ETL:** 303 filas, 13 features → todas numéricas, StandardScaler aplicado.

**Entrenamiento:** mismo curl que Titanic, con el `etl_run_id` correspondiente.

**Métricas Heart Disease:**

| Métrica   | Valor  |
|-----------|--------|
| Accuracy  | 0.8197 |
| Precision | 0.8750 |
| Recall    | 0.4118 |
| F1        | 0.5600 |
| ROC-AUC   | 0.9372 |

> El recall bajo se explica por el tamaño chico del dataset (303 filas) y el desbalance en el split de test.

---

### Obtener el etl_run_id después del ETL

Cuando el run termina, el `etl_run_id` es el `dag_run_id` con cualquier carácter no alfanumérico reemplazado por `_`. Podés calcularlo directo desde la respuesta del primer curl:

```bash
curl -s http://localhost:8080/api/v1/dags/etl_parametrizado/dagRuns \
  -u admin:admin | python3 -c "
import sys, json, re
runs = json.load(sys.stdin)['dag_runs']
last = runs[-1]
etl_run_id = re.sub(r'[^\w]', '_', last['dag_run_id'])
print('state     :', last['state'])
print('etl_run_id:', etl_run_id)
"
```

### Consultar estado de un run

```bash
curl -s http://localhost:8080/api/v1/dags/<dag_id>/dagRuns/<dag_run_id> \
  -u admin:admin | python3 -m json.tool | grep state
```

---

## 4. Dónde quedan los archivos

`data/` y `logs/` son volúmenes Docker internos (no bind mounts). Los archivos se guardan dentro del volumen `airflow-data` y no son directamente accesibles desde el host.

```
airflow-data (volumen Docker)
└── <etl_run_id>/
    ├── raw.parquet              ← CSV original sin columnas ignoradas
    ├── feature_analysis.json   ← tipos y cardinalidades por columna
    ├── preprocessor.joblib     ← pipeline de sklearn fitted
    ├── metadata.json           ← clases, tamaños, nro de features
    ├── X_train.parquet
    ├── X_test.parquet
    ├── y_train.parquet
    ├── y_test.parquet
    └── model/
        ├── random_forest.joblib
        └── metrics.json
```

Para inspeccionar archivos desde la terminal:

```bash
docker-compose exec airflow-scheduler bash -c "ls /opt/airflow/data/"
docker-compose exec airflow-scheduler bash -c "cat /opt/airflow/data/<etl_run_id>/model/metrics.json"
```

---

## 5. Detener el entorno

```bash
# Detener sin borrar datos
docker-compose down

# Detener y borrar todo (base de datos y datos generados)
docker-compose down -v
```

---

## Troubleshooting

**Error: `client version X is too new. Maximum supported API version is 1.43`**  
Ocurre con Colima porque el daemon dentro de la VM es más viejo que el CLI. Exportalo en tu shell:
```bash
echo 'export DOCKER_API_VERSION=1.43' >> ~/.zshrc && source ~/.zshrc
```

**Error: `uid not found` o `getpwuid(): uid not found`**  
El UID del sistema macOS es demasiado grande para el contenedor. Usá el UID fijo de Airflow:
```bash
echo "AIRFLOW_UID=50000" > .env
```

**Error: `Permission denied` en `/opt/airflow/data` o `/opt/airflow/logs`**  
Los volúmenes Docker se crean con permisos de root. El `airflow-init` ya corre `chmod 777` sobre esos directorios al iniciar. Si el error persiste, bajá todo y volvé a inicializar:
```bash
docker-compose down -v
docker-compose up airflow-init
```

**Error: `DagBag import timeout` en el scheduler**  
Los imports pesados (sklearn, numpy) deben ir dentro de cada `@task`, no al tope del archivo DAG. El scheduler tiene un timeout de 30s para parsear cada archivo y los imports de sklearn pueden superar ese límite.

**El webserver tarda en arrancar**  
Es normal la primera vez. Los contenedores tardan ~3-5 minutos extra instalando dependencias. Seguí el progreso con:
```bash
docker-compose logs -f airflow-scheduler
```

**Puerto 8080 ocupado**  
Cambiá el puerto en `docker-compose.yml`:
```yaml
ports:
  - "9090:8080"
```

**Un DAG aparece en error de importación**  
Revisá la sintaxis del archivo Python:
```bash
docker-compose exec airflow-scheduler python /opt/airflow/dags/mi_dag.py
```
