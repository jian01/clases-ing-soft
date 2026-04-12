from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Gauge, Histogram
import os, time, random, uuid
from datetime import datetime
from typing import Optional

app = FastAPI(title="py-app — Sistema de Monitoreo Demo")

STORAGE_DIR = os.environ.get("STORAGE_DIR", "/data")
STORAGE_FILE = os.path.join(STORAGE_DIR, "store.txt")

# ─── Métricas custom de negocio ───────────────────────────────────────────────
saves_total = Counter(
    "saves_total",
    "Total de operaciones /save realizadas",
    ["status"],
)
reads_total = Counter(
    "reads_total",
    "Total de operaciones /read realizadas",
)
entries_stored = Gauge(
    "entries_stored",
    "Cantidad de entradas actualmente almacenadas en disco",
)
forecasts_total = Counter(
    "forecasts_total",
    "Total de forecasts generados",
    ["status"],
)
forecast_duration = Histogram(
    "forecast_duration_seconds",
    "Tiempo de procesamiento de un forecast (KPI objetivo: < 5s)",
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0],
)

# ─── Instrumentación automática de métricas HTTP ──────────────────────────────
# Expone http_request_duration_seconds{handler, method, status_code} en /metrics
Instrumentator().instrument(app).expose(app)

# ─── Estado en memoria ────────────────────────────────────────────────────────
_forecast_history: list[dict] = []


# ─── Helpers ──────────────────────────────────────────────────────────────────
def ensure_storage_dir():
    os.makedirs(STORAGE_DIR, exist_ok=True)


def count_entries() -> int:
    if not os.path.exists(STORAGE_FILE):
        return 0
    with open(STORAGE_FILE, "r") as f:
        return sum(1 for line in f if line.strip())


def _run_forecast(delay: Optional[float]) -> dict:
    """Lógica central de forecast (reutilizable desde /simulate/load)."""
    actual_delay = delay if delay is not None else random.uniform(0.3, 7.0)
    start = time.time()
    time.sleep(actual_delay)
    duration = time.time() - start

    forecast_duration.observe(duration)
    forecasts_total.labels(status="success").inc()

    record = {
        "id": str(uuid.uuid4())[:8],
        "duration_s": round(duration, 3),
        "sla_ok": duration < 5.0,
        "created_at": datetime.utcnow().isoformat(),
    }
    _forecast_history.append(record)
    return record


def _run_save(content: str):
    """Lógica central de save (reutilizable desde /simulate/load)."""
    ensure_storage_dir()
    with open(STORAGE_FILE, "a") as f:
        f.write(content + "\n")
    saves_total.labels(status="success").inc()
    entries_stored.set(count_entries())


# ─── Modelos ──────────────────────────────────────────────────────────────────
class SaveRequest(BaseModel):
    content: str


class ForecastRequest(BaseModel):
    delay: Optional[float] = None        # None → random entre 0.3 y 7s
    simulate_error: Optional[bool] = False


class LoadRequest(BaseModel):
    count: int = 10
    endpoint: str = "/forecast"          # "/forecast" | "/save" | "/read"
    delay_between: float = 0.1           # segundos entre iteraciones


# ─── Endpoints originales ─────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "py-app"}


@app.post("/save")
def save(body: SaveRequest):
    if not body.content.strip():
        saves_total.labels(status="error").inc()
        raise HTTPException(status_code=400, detail="'content' must not be empty")
    _run_save(body.content)
    return {"message": "Content saved", "file": STORAGE_FILE}


@app.get("/read")
def read():
    reads_total.inc()
    ensure_storage_dir()
    if not os.path.exists(STORAGE_FILE):
        return {"content": [], "file": STORAGE_FILE}
    with open(STORAGE_FILE, "r") as f:
        lines = [line.rstrip("\n") for line in f.readlines() if line.strip()]
    return {"content": lines, "file": STORAGE_FILE}


# ─── Endpoints nuevos (demo de monitoreo) ─────────────────────────────────────
@app.post("/forecast")
def forecast(body: ForecastRequest):
    """
    Simula la generación de un pronóstico con latencia variable.
    - delay=None           → latencia aleatoria entre 0.3s y 7s
    - delay=2.0            → siempre 2 segundos (predecible para demos)
    - simulate_error=true  → dispara un HTTP 500 (para probar alertas)
    """
    if body.simulate_error:
        forecasts_total.labels(status="error").inc()
        raise HTTPException(status_code=500, detail="Simulated forecast error")
    return _run_forecast(body.delay)


@app.get("/forecast/history")
def get_forecast_history():
    """Historial de forecasts — simula consultas de integración externa."""
    return {
        "forecasts": _forecast_history[-50:],
        "total": len(_forecast_history),
        "sla_violations": sum(1 for f in _forecast_history if not f["sla_ok"]),
    }


@app.post("/simulate/load")
def simulate_load(body: LoadRequest):
    """
    Genera carga artificial actualizando métricas directamente.
    No hace requests HTTP internos: actualiza los contadores y gauges custom.
    Para métricas HTTP (http_request_duration_seconds), usar curl o el frontend.
    """
    results = {"ok": 0, "error": 0, "total": body.count, "endpoint": body.endpoint}

    for _ in range(body.count):
        try:
            if body.endpoint == "/forecast":
                _run_forecast(delay=None)
            elif body.endpoint == "/save":
                _run_save(f"load-test-{uuid.uuid4()}")
            elif body.endpoint == "/read":
                reads_total.inc()
            results["ok"] += 1
        except Exception:
            results["error"] += 1

        if body.delay_between > 0:
            time.sleep(body.delay_between)

    return results
