import json
import os
import re
from datetime import datetime

import pandas as pd
from airflow.decorators import dag, task
from airflow.models.param import Param

DATA_DIR = '/opt/airflow/data'
CARDINALITY_THRESHOLD = 10


def _run_dir(run_id: str) -> str:
    return os.path.join(DATA_DIR, re.sub(r'[^\w]', '_', run_id))


def _makedirs(path: str):
    os.makedirs(path, exist_ok=True)


@dag(
    dag_id='etl_parametrizado',
    description='Descarga un CSV, transforma features según tipo/cardinalidad y genera el split train/test',
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={'owner': 'udesa', 'retries': 1},
    params={
        'csv_url': Param(
            default='https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv',
            type='string',
            description='URL del CSV a procesar',
        ),
        'target_column': Param(
            default='Survived',
            type='string',
            description='Nombre de la columna target binaria',
        ),
        'test_size': Param(
            default=0.2,
            type='number',
            description='Proporción del dataset para test (entre 0.1 y 0.4)',
        ),
        'ignore_columns': Param(
            default=[],
            type='array',
            description='Columnas a excluir antes del análisis y transformación (ej: IDs, nombres)',
        ),
    },
    tags=['etl', 'udesa'],
)
def etl_parametrizado():

    @task()
    def descargar_y_validar(**context) -> dict:
        csv_url = context['params']['csv_url']
        target = context['params']['target_column']
        ignore_columns = context['params']['ignore_columns'] or []

        df = pd.read_csv(csv_url)

        if target not in df.columns:
            raise ValueError(f"Columna '{target}' no encontrada. Disponibles: {list(df.columns)}")

        cols_to_drop = [c for c in ignore_columns if c in df.columns and c != target]
        not_found = [c for c in ignore_columns if c not in df.columns]
        if not_found:
            print(f"Advertencia — columnas en ignore_columns no encontradas: {not_found}")
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            print(f"Columnas ignoradas: {cols_to_drop}")

        unique_vals = df[target].dropna().unique()
        if len(unique_vals) != 2:
            raise ValueError(f"El target debe ser binario. Valores encontrados: {sorted(unique_vals)}")

        run_dir = _run_dir(context['run_id'])
        _makedirs(run_dir)
        df.to_parquet(os.path.join(run_dir, 'raw.parquet'), index=False)

        print(f"Filas: {len(df)} | Columnas: {len(df.columns)}")
        print(f"Distribución del target:\n{df[target].value_counts().to_string()}")
        print(f"\netl_run_id para el DAG de entrenamiento: {os.path.basename(run_dir)}")

        return {'run_dir': run_dir, 'target': target}

    @task()
    def analizar_features(info: dict) -> dict:
        run_dir = info['run_dir']
        target = info['target']

        df = pd.read_parquet(os.path.join(run_dir, 'raw.parquet'))
        features = df.drop(columns=[target])

        analysis = {}
        for col in features.columns:
            cardinality = int(features[col].nunique())
            is_numeric = pd.api.types.is_numeric_dtype(features[col])
            analysis[col] = {
                'type': 'numeric' if is_numeric else 'categorical',
                'cardinality': cardinality,
                'null_pct': round(float(features[col].isnull().mean()), 4),
                'dtype': str(features[col].dtype),
            }

        with open(os.path.join(run_dir, 'feature_analysis.json'), 'w') as f:
            json.dump(analysis, f, indent=2)

        print(f"{'Columna':<30} {'Tipo':<12} {'Cardinalidad':>13} {'Nulos':>8}")
        print("-" * 65)
        for col, meta in analysis.items():
            encoding = (
                'StandardScaler' if meta['type'] == 'numeric'
                else ('OHE' if meta['cardinality'] <= CARDINALITY_THRESHOLD else 'Ordinal')
            )
            print(f"{col:<30} {meta['type']:<12} {meta['cardinality']:>8}  →  {encoding}")

        return {'run_dir': run_dir, 'target': target, 'analysis': analysis}

    @task()
    def transformar_y_split(info: dict, **context):
        import joblib
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

        run_dir = info['run_dir']
        target = info['target']
        analysis = info['analysis']
        test_size = context['params']['test_size']

        df = pd.read_parquet(os.path.join(run_dir, 'raw.parquet'))
        X = df.drop(columns=[target])
        y = df[target]

        classes = sorted(y.unique())
        y = y.map({classes[0]: 0, classes[1]: 1}).astype(int)

        numeric_cols = [c for c, v in analysis.items() if v['type'] == 'numeric']
        ohe_cols = [c for c, v in analysis.items() if v['type'] == 'categorical' and v['cardinality'] <= CARDINALITY_THRESHOLD]
        ord_cols = [c for c, v in analysis.items() if v['type'] == 'categorical' and v['cardinality'] > CARDINALITY_THRESHOLD]

        transformers = []
        if numeric_cols:
            transformers.append(('num', Pipeline([
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler()),
            ]), numeric_cols))
        if ohe_cols:
            transformers.append(('cat_ohe', Pipeline([
                ('imputer', SimpleImputer(strategy='most_frequent')),
                ('encoder', OneHotEncoder(handle_unknown='ignore', sparse_output=False)),
            ]), ohe_cols))
        if ord_cols:
            transformers.append(('cat_ord', Pipeline([
                ('imputer', SimpleImputer(strategy='most_frequent')),
                ('encoder', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)),
            ]), ord_cols))

        if not transformers:
            raise ValueError("No se encontraron columnas para transformar.")

        preprocessor = ColumnTransformer(transformers=transformers)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )

        X_train_t = preprocessor.fit_transform(X_train)
        X_test_t = preprocessor.transform(X_test)
        feature_names = list(preprocessor.get_feature_names_out())

        pd.DataFrame(X_train_t, columns=feature_names).to_parquet(os.path.join(run_dir, 'X_train.parquet'), index=False)
        pd.DataFrame(X_test_t, columns=feature_names).to_parquet(os.path.join(run_dir, 'X_test.parquet'), index=False)
        y_train.reset_index(drop=True).rename(target).to_frame().to_parquet(os.path.join(run_dir, 'y_train.parquet'), index=False)
        y_test.reset_index(drop=True).rename(target).to_frame().to_parquet(os.path.join(run_dir, 'y_test.parquet'), index=False)
        joblib.dump(preprocessor, os.path.join(run_dir, 'preprocessor.joblib'))

        metadata = {
            'target': target,
            'classes': [str(c) for c in classes],
            'n_train': int(len(X_train)),
            'n_test': int(len(X_test)),
            'n_features_original': int(len(X.columns)),
            'n_features_transformed': int(len(feature_names)),
            'test_size': test_size,
        }
        with open(os.path.join(run_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"Train: {len(X_train)} muestras | Test: {len(X_test)} muestras")
        print(f"Features originales: {len(X.columns)} → transformadas: {len(feature_names)}")

    info = descargar_y_validar()
    info_con_analysis = analizar_features(info)
    transformar_y_split(info_con_analysis)


etl_parametrizado()
