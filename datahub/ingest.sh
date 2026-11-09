#!/bin/bash
# Ingestión de metadata dbt → DataHub.
#
# PASO 1 (una sola vez): levantar DataHub
#   pip install 'acryl-datahub[dbt,datahub-rest]'
#   # Remapeo de puertos para no chocar con otros servicios locales
#   # (8080 suele estar ocupado, 8081 es Adminer de este stack):
#   export DATAHUB_MAPPED_GMS_PORT=8090
#   export DATAHUB_MAPPED_SCHEMA_REGISTRY_PORT=8091
#   datahub docker quickstart          # UI en http://localhost:9002
#
# PASO 2 (cada vez que corra el pipeline): generar artefactos y enviar
#   bash datahub/ingest.sh
#
# Requiere el stack de la clase levantado (docker compose up -d): los artefactos de dbt
# se generan adentro del contenedor de Dagster, así que no hace falta dbt en la máquina.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$SCRIPT_DIR/.."

echo "==> Generando artefactos dbt (manifest.json + catalog.json) en el contenedor de Dagster..."
cd "$REPO_DIR"
docker compose exec -T dagster \
  dbt docs generate --profiles-dir /workspace/dbt --project-dir /workspace/dbt
# dbt/ está montado como volumen: los archivos quedan en dbt/target/ del repo.

echo "==> Ingresando metadata en DataHub..."
cd "$SCRIPT_DIR"
datahub ingest -c recipe.yml

echo ""
echo "Listo. Abrí http://localhost:9002 en tu browser."
echo "  - Search: buscá 'fact_streams' para ver el lineage completo"
echo "  - Owners: cada modelo muestra el campo meta.owner del schema.yml"
echo "  - Tags: columnas con meta.pii=true aparecen con el tag PII"
