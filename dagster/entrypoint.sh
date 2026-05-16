#!/bin/bash
set -e

echo "==> Instalando dependencias de dbt (dbt_utils)..."
cd /workspace/dbt && dbt deps --profiles-dir /workspace/dbt

echo "==> Generando manifest.json con dbt parse..."
cd /workspace/dbt && dbt parse --profiles-dir /workspace/dbt

echo "==> Arrancando Dagster..."
exec dagster dev -h 0.0.0.0 -p 3000 -m dwh_pipeline
