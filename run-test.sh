#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Ejecuta un test de performance contra py-app usando Locust (en Docker).
#
#   ./run-test.sh smoke    # ~20s   ¿prende? (1 usuario, valida todos los endpoints)
#   ./run-test.sh load     # ~3m    ¿aguanta la carga normal? (30 usuarios)
#   ./run-test.sh stress   # ~3.5m  ¿dónde se rompe? (escalones 20 → 150 usuarios)
#   ./run-test.sh spike    # ~2.75m ¿sobrevive a un pico y se recupera? (20 → 200 → 20)
#
# Requisito: el stack levantado →  docker compose up -d --build
# Mientras corre, mirar Grafana: http://localhost:3001  (tablero "Performance Testing")
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

TEST="${1:-}"
API_URL="${API_URL:-http://localhost:5000}"
GRAFANA_DASHBOARD="http://localhost:3001/d/perf-testing/performance-testing?from=now-5m&to=now&refresh=5s"

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
}

case "$TEST" in
  smoke | load | stress | spike) ;;
  *) usage ;;
esac

# 1. Esperar a que la API esté arriba (útil justo después de `docker compose up`)
printf "Esperando a py-app en %s " "$API_URL"
for _ in $(seq 1 30); do
  if curl -fsS "$API_URL/health" >/dev/null 2>&1; then
    echo "✔"
    break
  fi
  printf "."
  sleep 2
done
if ! curl -fsS "$API_URL/health" >/dev/null 2>&1; then
  echo
  echo "✘ py-app no responde. Levantá el stack primero:  docker compose up -d --build"
  exit 1
fi

# Si Grafana es parte del stack (local, no en CI), esperarla también: si no,
# justo después de `docker compose up` el test arranca sin anotaciones.
if [ -n "$(docker compose ps -q grafana 2>/dev/null)" ]; then
  printf "Esperando a Grafana "
  for _ in $(seq 1 30); do
    curl -fsS http://localhost:3001/api/health >/dev/null 2>&1 && break
    printf "."
    sleep 2
  done
  echo "✔"
fi

echo
echo "▶ Test: $TEST"
echo "  Grafana: $GRAFANA_DASHBOARD"
echo

# 2. Correr Locust. El servicio `locust` está en el perfil "tests" del docker-compose,
#    así que solo se crea cuando lo pedimos explícitamente acá.
#    --name locust: Prometheus lo encuentra por ese nombre (locust:9646)
#    --user: los reportes quedan con el dueño del usuario actual (no root)
REPORT="reports/${TEST}-report.html"
docker compose build --quiet locust
docker rm -f locust >/dev/null 2>&1 || true   # por si quedó uno colgado de una corrida cortada
set +e
docker compose run --rm --name locust \
  --user "$(id -u):$(id -g)" \
  locust \
  -f "/mnt/tests/${TEST}/locustfile.py" \
  --host http://py-app:5000 \
  --headless \
  --only-summary \
  --html "/mnt/tests/${REPORT}"
EXIT_CODE=$?
set -e

echo
echo "Reporte HTML: performance-tests/${REPORT}"
if [ "$EXIT_CODE" -eq 0 ]; then
  echo "✔ Test '$TEST' terminado OK"
else
  echo "✘ Test '$TEST' FALLÓ (exit code $EXIT_CODE)"
fi
exit "$EXIT_CODE"
