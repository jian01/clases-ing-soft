import json
import os
from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param

DATA_DIR = '/opt/airflow/data'


def _makedirs(path: str):
    os.makedirs(path, exist_ok=True)


def _load_split(run_dir: str, target: str):
    import pandas as pd
    X_train = pd.read_parquet(os.path.join(run_dir, 'X_train.parquet')).values
    X_test = pd.read_parquet(os.path.join(run_dir, 'X_test.parquet')).values
    y_train = pd.read_parquet(os.path.join(run_dir, 'y_train.parquet'))[target].values
    y_test = pd.read_parquet(os.path.join(run_dir, 'y_test.parquet'))[target].values
    return X_train, X_test, y_train, y_test


@dag(
    dag_id='entrenamiento_random_forest',
    description='Entrena un Random Forest con RandomizedSearchCV sobre la salida del ETL',
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={'owner': 'udesa', 'retries': 1},
    params={
        'etl_run_id': Param(
            default='',
            type='string',
            description='Valor de etl_run_id impreso al final de la tarea descargar_y_validar del DAG etl_parametrizado',
        ),
        'n_iter': Param(
            default=20,
            type='integer',
            description='Cantidad de combinaciones a probar en RandomizedSearchCV',
        ),
    },
    tags=['training', 'udesa', 'ml'],
)
def entrenamiento_random_forest():

    @task()
    def cargar_datos(**context) -> dict:
        etl_run_id = context['params']['etl_run_id'].strip()
        run_dir = os.path.join(DATA_DIR, etl_run_id)

        if not os.path.exists(run_dir):
            raise FileNotFoundError(
                f"No se encontró el directorio del ETL: {run_dir}\n"
                "Verificá el etl_run_id en los logs de la tarea 'descargar_y_validar'."
            )

        with open(os.path.join(run_dir, 'metadata.json')) as f:
            metadata = json.load(f)

        X_train, X_test, y_train, y_test = _load_split(run_dir, metadata['target'])

        print(f"Train: {X_train.shape} | Test: {X_test.shape}")
        print(f"Target: '{metadata['target']}' | Clases originales: {metadata['classes']}")
        print(f"Balance train — clase 0: {(y_train == 0).sum()} | clase 1: {(y_train == 1).sum()}")

        return {'run_dir': run_dir, 'target': metadata['target']}

    @task()
    def buscar_hiperparametros(info: dict, **context) -> dict:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold

        run_dir = info['run_dir']
        target = info['target']

        X_train, _, y_train, _ = _load_split(run_dir, target)

        param_dist = {
            'n_estimators': [50, 100, 200, 300],
            'max_depth': [None, 5, 10, 20],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'max_features': ['sqrt', 'log2'],
        }

        search = RandomizedSearchCV(
            RandomForestClassifier(random_state=42, n_jobs=-1),
            param_dist,
            n_iter=context['params']['n_iter'],
            cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
            scoring='roc_auc',
            random_state=42,
            n_jobs=-1,
            verbose=1,
        )
        search.fit(X_train, y_train)

        print(f"Mejores parámetros : {search.best_params_}")
        print(f"Mejor ROC-AUC (CV) : {search.best_score_:.4f}")

        return {
            'run_dir': run_dir,
            'target': target,
            'best_params': search.best_params_,
            'cv_roc_auc': float(search.best_score_),
        }

    @task()
    def entrenar_y_evaluar(info: dict):
        import numpy as np
        import joblib
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import (
            accuracy_score, classification_report, confusion_matrix,
            f1_score, precision_score, recall_score, roc_auc_score,
        )

        run_dir = info['run_dir']
        target = info['target']
        best_params = info['best_params']
        cv_roc_auc = info['cv_roc_auc']

        X_train, X_test, y_train, y_test = _load_split(run_dir, target)

        model = RandomForestClassifier(**best_params, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        metrics = {
            'accuracy': round(float(accuracy_score(y_test, y_pred)), 4),
            'precision': round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            'recall': round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            'f1': round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
            'roc_auc_test': round(float(roc_auc_score(y_test, y_proba)), 4),
            'roc_auc_cv': round(float(cv_roc_auc), 4),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
            'best_params': best_params,
            'n_train': int(len(X_train)),
            'n_test': int(len(X_test)),
        }

        print("=== Métricas en Test ===")
        print(f"Accuracy   : {metrics['accuracy']}")
        print(f"Precision  : {metrics['precision']}")
        print(f"Recall     : {metrics['recall']}")
        print(f"F1         : {metrics['f1']}")
        print(f"ROC-AUC    : {metrics['roc_auc_test']}  (CV: {metrics['roc_auc_cv']})")
        print(f"\nMatriz de confusión:\n{np.array(metrics['confusion_matrix'])}")
        print(f"\n{classification_report(y_test, y_pred)}")

        model_dir = os.path.join(run_dir, 'model')
        _makedirs(model_dir)
        joblib.dump(model, os.path.join(model_dir, 'random_forest.joblib'))
        with open(os.path.join(model_dir, 'metrics.json'), 'w') as f:
            json.dump(metrics, f, indent=2)

        print(f"Modelo guardado en: {model_dir}/random_forest.joblib")

    info = cargar_datos()
    info_con_params = buscar_hiperparametros(info)
    entrenar_y_evaluar(info_con_params)


entrenamiento_random_forest()
