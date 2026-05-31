#!/bin/bash
# Ingestión de metadata dbt → DataHub.
#
# PASO 1 (una sola vez): levantar DataHub
#   pip install 'acryl-datahub[dbt-postgres]'
#   datahub docker quickstart          # UI en http://localhost:9002
#
# PASO 2 (cada vez que corra el pipeline): generar artefactos y enviar
#   bash datahub/ingest.sh
set -e

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
