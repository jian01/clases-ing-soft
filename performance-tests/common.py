"""
Piezas compartidas por todos los tests de performance.

Cada test (smoke.py, load.py, stress.py, spike.py) define solo dos cosas:
  1. QUÉ hace cada usuario virtual  → una clase User (ShopUser, por ejemplo)
  2. CUÁNTOS usuarios hay en cada momento → una StagedShape con sus etapas

Este módulo agrega, además:
  - Un exporter de Prometheus (puerto 9646) con los usuarios virtuales y la
    etapa actual del test → así Grafana muestra "la carga" al lado de "la respuesta".
  - Anotaciones en Grafana: cada etapa queda marcada como una franja en los gráficos.
  - Un resumen por etapa al final, con el veredicto contra el SLA.
"""

import os
import random
import time
from dataclasses import dataclass, field

import gevent
import requests
from locust import FastHttpUser, LoadTestShape, events, task
from locust.runners import WorkerRunner
from prometheus_client import Gauge, start_http_server

# ─── SLA (acuerdo de nivel de servicio) ───────────────────────────────────────
# Es la vara contra la que se compara cada test. La misma línea aparece en Grafana.
SLA_P95_MS = 500  # el 95% de los requests tiene que responder en menos de 500 ms
SLA_ERROR_PCT = 1.0  # menos del 1% de errores

GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://grafana:3000")
GRAFANA_AUTH = tuple(os.environ.get("GRAFANA_AUTH", "admin:admin").split(":", 1))
METRICS_PORT = int(os.environ.get("LOCUST_METRICS_PORT", "9646"))


# ─── Usuario de la tienda ─────────────────────────────────────────────────────
class ShopUser(FastHttpUser):
    """
    Un cliente de la tienda: mira productos y cada tanto compra.

    Cada usuario hace (en promedio) como máximo 2 requests por segundo.
    Así la cuenta es simple:  usuarios x 2 = requests/s que pedimos al sistema.
    La API aguanta ~100 req/s  →  ~50 usuarios es el límite teórico.
    """

    abstract = True  # cada test importa esta clase; Locust la usa vía subclases

    def wait_time(self):
        """
        Como constant_throughput(2), pero con un período aleatorio entre 0.25 y 0.75 s
        (promedio 0.5 s → 2 req/s). Sin el azar, los usuarios que arrancan juntos
        quedan sincronizados para siempre y disparan en ráfagas.
        """
        now = time.time()
        next_start = getattr(self, "_next_start", now) + random.uniform(0.25, 0.75)
        self._next_start = max(next_start, now)  # si venimos atrasados, no "recuperamos"
        return self._next_start - now

    @task(3)
    def ver_productos(self):
        self.client.get("/api/productos", name="GET /api/productos")

    @task(1)
    def comprar(self):
        self.client.post(
            "/api/pedidos",
            json={"producto_id": 1, "cantidad": 1},
            name="POST /api/pedidos",
        )


# ─── Forma de la carga por etapas ─────────────────────────────────────────────
@dataclass
class Stage:
    name: str
    duration: int  # segundos que dura ESTA etapa (no acumulado)
    users: int  # usuarios objetivo durante la etapa
    spawn_rate: float  # usuarios por segundo que se agregan/quitan para llegar
    pico: bool = False  # se pinta en rojo en Grafana


@dataclass
class StageStats:
    stage: Stage
    started_at: float = 0.0
    ended_at: float = 0.0
    latencies_ms: list = field(default_factory=list)
    failures: int = 0
    annotation_id: int | None = None

    @property
    def requests(self):
        return len(self.latencies_ms)

    def rps(self):
        elapsed = (self.ended_at or time.time()) - self.started_at
        return self.requests / elapsed if elapsed > 0 else 0.0

    def error_pct(self):
        return 100.0 * self.failures / self.requests if self.requests else 0.0

    def percentile(self, p):
        if not self.latencies_ms:
            return 0.0
        data = sorted(self.latencies_ms)
        return data[min(len(data) - 1, int(p / 100 * len(data)))]

    def cumple_sla(self):
        return self.percentile(95) < SLA_P95_MS and self.error_pct() < SLA_ERROR_PCT


class StagedShape(LoadTestShape):
    """
    Recorre `stages` en orden. Cada etapa dura `duration` segundos.
    Cuando se terminan las etapas, el test termina solo.

    `strict_sla = True` → si el test no cumple el SLA, Locust sale con código 1
    (lo usa el pipeline de CI para bloquear el PR).
    """

    test_name = "test"
    stages: list[Stage] = []
    strict_sla = False
    abstract = True

    def tick(self):
        run_time = self.get_run_time()
        elapsed = 0
        for index, stage in enumerate(self.stages):
            elapsed += stage.duration
            if run_time < elapsed:
                tracker.enter_stage(self, index)
                return stage.users, stage.spawn_rate
        tracker.finish()
        return None


# ─── Seguimiento de etapas (resumen + Prometheus + Grafana) ──────────────────
locust_users = Gauge("locust_users", "Usuarios virtuales activos")
locust_target_users = Gauge("locust_target_users", "Usuarios virtuales objetivo de la etapa")
locust_stage = Gauge("locust_stage", "Etapa actual del test (1 = activa)", ["etapa"])


class Tracker:
    def __init__(self):
        self.shape = None
        self.current = -1
        self.stats: list[StageStats] = []
        self.finished = False
        self.grafana_warned = False

    # ── ciclo de vida de las etapas ──
    def enter_stage(self, shape, index):
        if index == self.current:
            return
        self.shape = shape
        self._close_current()
        self.current = index
        stage = shape.stages[index]
        stats = StageStats(stage=stage, started_at=time.time())
        self.stats.append(stats)

        locust_stage.clear()
        locust_stage.labels(etapa=f"{shape.test_name.upper()} · {stage.name}").set(1)
        locust_target_users.set(stage.users)

        marca = "🔴" if stage.pico else "▶"
        log(f"{marca} Etapa '{stage.name}': {stage.users} usuarios durante {stage.duration}s")
        stats.annotation_id = self._annotate(
            text=f"{shape.test_name.upper()} · {stage.name} ({stage.users} usuarios)",
            tags=["pico" if stage.pico else "etapa", shape.test_name],
        )

    def finish(self):
        if self.finished:
            return
        self.finished = True
        self._close_current()
        locust_stage.clear()
        locust_target_users.set(0)

    def _close_current(self):
        if 0 <= self.current < len(self.stats):
            stats = self.stats[self.current]
            if not stats.ended_at:
                stats.ended_at = time.time()
                if stats.annotation_id:
                    self._grafana("patch", f"/api/annotations/{stats.annotation_id}",
                                  {"timeEnd": int(stats.ended_at * 1000)})

    # ── métricas por request ──
    def on_request(self, response_time, exception):
        if self.finished or not self.stats:
            return
        # Cada request cuenta para la etapa en la que EMPEZÓ (no en la que terminó):
        # así los 503 lentos del pico no "ensucian" la etapa de recuperación.
        started = time.time() - response_time / 1000
        stats = next((s for s in reversed(self.stats) if s.started_at <= started), self.stats[0])
        stats.latencies_ms.append(response_time)
        if exception:
            stats.failures += 1

    # ── Grafana ──
    def _annotate(self, text, tags):
        result = self._grafana("post", "/api/annotations",
                               {"time": int(time.time() * 1000), "tags": tags, "text": text})
        return result.get("id") if result else None

    def _grafana(self, method, path, payload):
        try:
            resp = requests.request(method, GRAFANA_URL + path, json=payload,
                                    auth=GRAFANA_AUTH, timeout=2)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # Grafana es opcional (ej: en CI no está levantado)
            if not self.grafana_warned:
                log(f"(sin anotaciones en Grafana: {exc.__class__.__name__})")
                self.grafana_warned = True
            return None

    # ── resumen final ──
    def print_summary(self):
        if not self.stats:
            return
        print(flush=True)
        print("═" * 86)
        print(f"  RESUMEN POR ETAPA — test '{self.shape.test_name}'"
              f"   (SLA: p95 < {SLA_P95_MS} ms y errores < {SLA_ERROR_PCT:g}%)")
        print("═" * 86)
        print(f"  {'Etapa':<22}{'Usuarios':>9}{'Req/s':>9}{'p50 ms':>9}{'p95 ms':>9}"
              f"{'Errores':>10}{'Requests':>10}   SLA")
        print("  " + "─" * 84)
        for s in self.stats:
            sla = "✅" if s.cumple_sla() else "❌"
            print(f"  {s.stage.name:<22}{s.stage.users:>9}{s.rps():>9.1f}"
                  f"{s.percentile(50):>9.0f}{s.percentile(95):>9.0f}"
                  f"{s.error_pct():>9.1f}%{s.requests:>10}   {sla}")
        print("═" * 86, flush=True)

    def global_stats(self):
        total = StageStats(stage=Stage("total", 0, 0, 0))
        for s in self.stats:
            total.latencies_ms.extend(s.latencies_ms)
            total.failures += s.failures
        return total


tracker = Tracker()


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ─── Hooks de Locust ──────────────────────────────────────────────────────────
@events.init.add_listener
def _on_init(environment, **_kwargs):
    if isinstance(environment.runner, WorkerRunner):
        return
    start_http_server(METRICS_PORT)
    gevent.spawn(_report_loop, environment)


def _report_loop(environment):
    """Cada segundo actualiza Prometheus; cada 10s imprime una línea de progreso."""
    ticks = 0
    while True:
        runner = environment.runner
        locust_users.set(runner.user_count if runner else 0)
        ticks += 1
        if ticks % 10 == 0 and 0 <= tracker.current < len(tracker.stats) and not tracker.finished:
            total = environment.stats.total
            p95 = total.get_current_response_time_percentile(0.95) or 0
            log(f"   usuarios={runner.user_count:<4} req/s={total.current_rps:6.1f}  "
                f"p95(10s)={p95:5.0f} ms  errores/s={total.current_fail_per_sec:5.1f}")
        gevent.sleep(1)


@events.request.add_listener
def _on_request(response_time, exception, **_kwargs):
    tracker.on_request(response_time, exception)


@events.quitting.add_listener
def _on_quitting(environment, **_kwargs):
    tracker.finish()
    tracker.print_summary()
    shape = tracker.shape
    if shape is None:
        return
    total = tracker.global_stats()
    ok = total.cumple_sla()
    if shape.strict_sla:
        veredicto = "✅ PASA" if ok else "❌ FALLA"
        print(f"\n  Veredicto del test '{shape.test_name}': {veredicto} "
              f"(p95 = {total.percentile(95):.0f} ms, errores = {total.error_pct():.2f}%)\n",
              flush=True)
        environment.process_exit_code = 0 if ok else 1
    else:
        # Stress y spike EXPLORAN los límites: que algunas etapas no cumplan el SLA
        # es el resultado esperado, no un fallo del test.
        print(f"\n  Test exploratorio: mirá en qué etapas se rompe el SLA (❌) "
              f"y comparalo con Grafana.\n", flush=True)
        environment.process_exit_code = 0
