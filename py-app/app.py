from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from contextlib import asynccontextmanager
import asyncio, os, time, random, uuid

app = FastAPI(title="py-app — Tienda para performance testing")

# ─── Simulación de capacidad ──────────────────────────────────────────────────
# La API de "tienda" (/api/productos y /api/pedidos) usa un pool de conexiones
# a una base de datos simulada. El pool tiene un tamaño FIJO: eso le da al
# sistema una capacidad máxima conocida y hace que los tests de carga muestren
# resultados claros y repetibles.
#
#   capacidad (req/s) = DB_POOL_SIZE / tiempo_medio_de_servicio
#                     = 10 conexiones / 0.1 s  = 100 req/s
#
# Si todas las conexiones están ocupadas, el request espera en cola.
# Si espera más de QUEUE_TIMEOUT segundos → HTTP 503 (servidor saturado).
DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "10"))
QUEUE_TIMEOUT = float(os.environ.get("QUEUE_TIMEOUT", "1.0"))

# Tiempo de servicio de cada endpoint (segundos). Con la mezcla de tráfico de
# Locust (3 lecturas de productos por cada pedido) el promedio es 0.1 s.
SERVICE_TIME = {
    "/api/productos": 0.06,
    "/api/pedidos": 0.22,
}
TRAFFIC_MIX = {"/api/productos": 3, "/api/pedidos": 1}
MEAN_SERVICE_TIME = sum(SERVICE_TIME[e] * w for e, w in TRAFFIC_MIX.items()) / sum(
    TRAFFIC_MIX.values()
)

# ─── Métricas (las lee Prometheus en /metrics) ────────────────────────────────
api_requests_total = Counter(
    "api_requests_total",
    "Requests a la API de tienda, por endpoint y resultado",
    ["endpoint", "status"],
)
api_request_duration = Histogram(
    "api_request_duration_seconds",
    "Latencia total de la API de tienda (cola + procesamiento)",
    ["endpoint"],
    buckets=[0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 5.0],
)
db_pool_size = Gauge("db_pool_size", "Tamaño del pool de conexiones simulado")
db_pool_in_use = Gauge("db_pool_in_use", "Conexiones del pool en uso ahora")
db_pool_waiting = Gauge("db_pool_waiting", "Requests esperando una conexión libre (cola)")
# Contadores de "segundos acumulados": rate() de estos da el PROMEDIO exacto de
# conexiones ocupadas y de requests en cola (ley de Little), sin depender de en
# qué instante justo Prometheus leyó los gauges de arriba.
db_pool_busy_seconds = Counter("db_pool_busy_seconds_total", "Segundos-conexión ocupados del pool")
db_pool_wait_seconds = Counter("db_pool_wait_seconds_total", "Segundos acumulados esperando en cola")
api_capacity_rps = Gauge("api_capacity_rps", "Capacidad teórica máxima de la API de tienda (req/s)")

db_pool_size.set(DB_POOL_SIZE)
api_capacity_rps.set(DB_POOL_SIZE / MEAN_SERVICE_TIME)

_db_pool = asyncio.Semaphore(DB_POOL_SIZE)


@asynccontextmanager
async def db_connection():
    """Pide una conexión al pool; si no se libera ninguna a tiempo → 503."""
    db_pool_waiting.inc()
    queued_at = time.perf_counter()
    try:
        await asyncio.wait_for(_db_pool.acquire(), timeout=QUEUE_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503,
            detail="Servidor saturado: no hay conexiones libres en el pool",
        )
    finally:
        db_pool_waiting.dec()
        db_pool_wait_seconds.inc(time.perf_counter() - queued_at)

    db_pool_in_use.inc()
    acquired_at = time.perf_counter()
    try:
        yield
    finally:
        db_pool_in_use.dec()
        db_pool_busy_seconds.inc(time.perf_counter() - acquired_at)
        _db_pool.release()


async def _serve(endpoint: str):
    """Ejecuta el 'trabajo' de un endpoint de tienda midiendo latencia y resultado."""
    start = time.perf_counter()
    status = "ok"
    try:
        async with db_connection():
            base = SERVICE_TIME[endpoint]
            await asyncio.sleep(random.uniform(base * 0.9, base * 1.1))
    except HTTPException:
        status = "error"
        raise
    finally:
        api_requests_total.labels(endpoint=endpoint, status=status).inc()
        api_request_duration.labels(endpoint=endpoint).observe(time.perf_counter() - start)


# ─── Modelos ──────────────────────────────────────────────────────────────────
class PedidoRequest(BaseModel):
    producto_id: int
    cantidad: int = 1


# ─── Endpoints ────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "py-app"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/productos")
async def listar_productos():
    """Lectura liviana (~60 ms). Ocupa una conexión del pool."""
    # 🔥 DEMO "romper el smoke test": descomentá la línea de abajo y reconstruí la API
    #    (docker compose up -d --build py-app). /api/productos pasa a responder 500
    #    y ./run-test.sh smoke termina con ❌ FALLA (exit code 1) → el PR queda en rojo.
    # raise HTTPException(status_code=500, detail="Bug introducido para la demo")
    await _serve("/api/productos")
    return {
        "productos": [
            {"id": i, "nombre": f"Producto {i}", "precio": 100 * i} for i in range(1, 6)
        ]
    }


@app.post("/api/pedidos", status_code=201)
async def crear_pedido(body: PedidoRequest):
    """Escritura más pesada (~220 ms). Ocupa una conexión del pool."""
    if body.cantidad < 1:
        raise HTTPException(status_code=400, detail="'cantidad' debe ser >= 1")
    await _serve("/api/pedidos")
    return {
        "pedido_id": str(uuid.uuid4())[:8],
        "producto_id": body.producto_id,
        "cantidad": body.cantidad,
        "estado": "confirmado",
    }
