#!/bin/bash
# Ingestión de metadata dbt → DataHub.
#
# PASO 1 (una sola vez): levantar DataHub
#   pip install 'acryl-datahub[dbt-postgres]'
#   # Remapeo de puertos para no chocar con otros servicios locales
#   # (8080 suele estar ocupado, 8081 es Adminer de este stack):
#   export DATAHUB_MAPPED_GMS_PORT=8090
#   export DATAHUB_MAPPED_SCHEMA_REGISTRY_PORT=8091
#   datahub docker quickstart          # UI en http://localhost:9002
#
# PASO 2 (cada vez que corra el pipeline): generar artefactos y enviar
#   bash datahub/ingest.sh
set -e

# El Postgres del stack se expone en el host en 5433 (ver docker-compose.yml).
export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-5433}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DBT_DIR="$SCRIPT_DIR/../dbt"

echo "==> Generando artefactos dbt (manifest.json + catalog.json)..."
cd "$DBT_DIR"
dbt docs generate --profiles-dir .

echo "==> Ingresando metadata en DataHub..."
cd "$SCRIPT_DIR"
datahub ingest -c recipe.yml

echo ""
echo "Listo. Abrí http://localhost:9002 en tu browser."
echo "  - Search: buscá 'fact_streams' para ver el lineage completo"
echo "  - Owners: cada modelo muestra el campo meta.owner del schema.yml"
echo "  - Tags: columnas con meta.pii=true aparecen con el tag PII"
