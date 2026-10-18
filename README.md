# Clase: Performance Testing (Locust + Prometheus + Grafana)

Cuatro tipos de test de performance sobre una API de tienda, cada uno con **un solo comando** y diseñado para que el resultado se vea claro en Grafana.

```bash
docker compose down -v          # (opcional) arrancar de cero
docker compose up -d --build
./run-test.sh smoke             # o: load | stress | spike
```

Grafana: **http://localhost:3001** (abre directo el tablero *Performance Testing*; para editar: `admin` / `admin`).

| Test | Pregunta | Duración | Detalle |
|---|---|---|---|
| smoke | ¿prende? | ~20 s | [performance-tests/smoke](performance-tests/smoke/README.md) |
| load | ¿aguanta la carga esperada? | ~3 min | [performance-tests/load](performance-tests/load/README.md) |
| stress | ¿dónde se rompe? | ~3.5 min | [performance-tests/stress](performance-tests/stress/README.md) |
| spike | ¿sobrevive a un pico y se recupera? | ~2.75 min | [performance-tests/spike](performance-tests/spike/README.md) |

- **[TIENDA.md](TIENDA.md)**: la app bajo prueba, diagramas, por qué se rompe y la demo para romper el smoke test.
- **[GUIA-LOCUST.md](GUIA-LOCUST.md)**: guía completa de la clase (cómo leer el tablero, qué mirar en cada test).
- El smoke test corre en cada Pull Request (`.github/workflows/smoke-test.yml`).

## Estructura

```
├── docker-compose.yml        # py-app + prometheus + grafana (+ locust, perfil "tests")
├── run-test.sh               # ./run-test.sh <smoke|load|stress|spike>
├── py-app/                   # la tienda (FastAPI)
├── performance-tests/        # tests de Locust, uno por carpeta
└── monitoring/               # config de Prometheus y Grafana (tablero provisionado)
```
