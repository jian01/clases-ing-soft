from __future__ import annotations

import os
from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param

MODEL_NAME = "fraud_detector"
DATA_PATH = "/opt/airflow/data/creditcard.csv"
SPLITS_DIR = "/tmp/fraud_splits"


@dag(
    dag_id="fraud_detection",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["mlflow", "fraud"],
    params={
        "model_type": Param(
            "logistic_regression",
            enum=["logistic_regression", "random_forest", "xgboost"],
            description="Tipo de modelo a entrenar",
        ),
        "class_weight": Param(
            "none",
            enum=["none", "balanced"],
            description="Estrategia para el desbalance de clases",
        ),
        "n_estimators": Param(100, type="integer", minimum=10, maximum=500),
        "max_depth": Param(6, type="integer", minimum=1, maximum=20),
        "sample_size": Param(
            50000,
            type="integer",
            minimum=10000,
            description="Filas a usar (el dataset completo tiene 284807)",
        ),
    },
)
def fraud_detection():

    @task
    def prepare_data(**context) -> dict:
        import pandas as pd
        from sklearn.model_selection import train_test_split

        sample_size = context["params"]["sample_size"]
        df = pd.read_csv(DATA_PATH)

        if sample_size < len(df):
            df, _ = train_test_split(
                df, train_size=sample_size, stratify=df["Class"], random_state=42,
            )

        X = df.drop("Class", axis=1)
        y = df["Class"]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=42
        )

        os.makedirs(SPLITS_DIR, exist_ok=True)
        X_train.to_csv(f"{SPLITS_DIR}/X_train.csv", index=False)
        X_test.to_csv(f"{SPLITS_DIR}/X_test.csv", index=False)
        y_train.to_csv(f"{SPLITS_DIR}/y_train.csv", index=False)
        y_test.to_csv(f"{SPLITS_DIR}/y_test.csv", index=False)

        fraud_rate = float(y_train.mean())
        print(f"Train size: {len(X_train)} | Test size: {len(X_test)}")
        print(f"Fraud rate in train: {fraud_rate:.4%}")
        return {"n_train": len(X_train), "n_test": len(X_test), "fraud_rate": fraud_rate}

    @task
    def train_and_log(data_info: dict, **context) -> str:
        import matplotlib.pyplot as plt
        import mlflow
        import mlflow.sklearn
        import pandas as pd
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import (
            PrecisionRecallDisplay, average_precision_score,
            f1_score, precision_score, recall_score, roc_auc_score,
        )
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from xgboost import XGBClassifier

        params = context["params"]
        model_type = params["model_type"]
        class_weight = None if params["class_weight"] == "none" else "balanced"

        X_train = pd.read_csv(f"{SPLITS_DIR}/X_train.csv")
        X_test = pd.read_csv(f"{SPLITS_DIR}/X_test.csv")
        y_train = pd.read_csv(f"{SPLITS_DIR}/y_train.csv").squeeze()
        y_test = pd.read_csv(f"{SPLITS_DIR}/y_test.csv").squeeze()

        mlflow.set_tracking_uri("http://mlflow:5000")
        mlflow.set_experiment("fraud_detection")

        with mlflow.start_run() as run:
            if model_type == "logistic_regression":
                model = Pipeline([
                    ("scaler", StandardScaler()),
                    ("clf", LogisticRegression(
                        class_weight=class_weight, max_iter=1000, random_state=42,
                    )),
                ])
            elif model_type == "random_forest":
                model = RandomForestClassifier(
                    n_estimators=params["n_estimators"], max_depth=params["max_depth"],
                    class_weight=class_weight, random_state=42, n_jobs=-1,
                )
            elif model_type == "xgboost":
                neg = (y_train == 0).sum()
                pos = (y_train == 1).sum()
                scale = float(neg / pos) if class_weight == "balanced" else 1.0
                model = XGBClassifier(
                    n_estimators=params["n_estimators"], max_depth=params["max_depth"],
                    scale_pos_weight=scale, random_state=42, eval_metric="aucpr",
                )

            mlflow.log_params({
                "model_type": model_type, "class_weight": params["class_weight"],
                "n_estimators": params["n_estimators"], "max_depth": params["max_depth"],
                "sample_size": params["sample_size"], "n_train": data_info["n_train"],
                "n_test": data_info["n_test"], "fraud_rate": round(data_info["fraud_rate"], 6),
            })

            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1]

            auc_pr = average_precision_score(y_test, y_prob)
            mlflow.log_metrics({
                "auc_pr": auc_pr,
                "roc_auc": roc_auc_score(y_test, y_prob),
                "f1_fraud": f1_score(y_test, y_pred),
                "recall_fraud": recall_score(y_test, y_pred),
                "precision_fraud": precision_score(y_test, y_pred, zero_division=0),
            })

            fig, ax = plt.subplots(figsize=(7, 5))
            PrecisionRecallDisplay.from_predictions(y_test, y_prob, ax=ax, name=model_type)
            ax.set_title(f"PR Curve - {model_type} (AUC-PR={auc_pr:.3f})")
            pr_curve_path = "/tmp/pr_curve.png"
            fig.savefig(pr_curve_path, bbox_inches="tight")
            plt.close()
            mlflow.log_artifact(pr_curve_path)

            mlflow.sklearn.log_model(
                model,
                artifact_path="model",
                registered_model_name=MODEL_NAME,
                # Evita que MLflow infiera los requirements escaneando todos los
                # paquetes instalados (muy lento sobre el filesystem de WSL2/Docker).
                pip_requirements=["scikit-learn==1.9.0", "xgboost==3.2.0"],
            )

            print(f"Run ID: {run.info.run_id}")
            print(f"AUC-PR: {auc_pr:.4f}")
            return run.info.run_id

    @task
    def promote_if_better(mlflow_run_id: str) -> dict:
        import mlflow
        from mlflow.tracking import MlflowClient

        mlflow.set_tracking_uri("http://mlflow:5000")
        client = MlflowClient()

        new_run = client.get_run(mlflow_run_id)
        new_auc_pr = new_run.data.metrics["auc_pr"]
        versions = client.search_model_versions(f"run_id='{mlflow_run_id}'")
        new_version = versions[0].version

        try:
            champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
            champion_run = client.get_run(champion.run_id)
            champion_auc_pr = champion_run.data.metrics["auc_pr"]

            print(f"Champion  AUC-PR: {champion_auc_pr:.4f} (v{champion.version})")
            print(f"Challenger AUC-PR: {new_auc_pr:.4f} (v{new_version})")

            if new_auc_pr > champion_auc_pr:
                client.set_registered_model_alias(MODEL_NAME, "champion", new_version)
                print(f"Promovido v{new_version} como nuevo champion!")
                return {"promoted": True, "new_version": new_version,
                        "new_auc_pr": new_auc_pr, "old_auc_pr": champion_auc_pr}
            else:
                print(f"v{new_version} no supera al champion.")
                return {"promoted": False, "new_version": new_version,
                        "new_auc_pr": new_auc_pr, "old_auc_pr": champion_auc_pr}

        except mlflow.exceptions.MlflowException:
            client.set_registered_model_alias(MODEL_NAME, "champion", new_version)
            print(f"Primer modelo. v{new_version} es el champion!")
            return {"promoted": True, "new_version": new_version,
                    "new_auc_pr": new_auc_pr, "old_auc_pr": None}

    data_info = prepare_data()
    mlflow_run_id = train_and_log(data_info)
    promote_if_better(mlflow_run_id)


fraud_detection()
