"""
SPIKE TEST
==========
Objetivo: evaluar cómo responde el sistema ante un pico repentino e inesperado
          de tráfico, y si se recupera cuando la carga vuelve a la normalidad.

Patrón de carga:
  10 usuarios  │ 0-60s   │ baseline (tráfico normal)
  200 usuarios │ 60-120s │ SPIKE (x20 en cuestión de segundos)
  10 usuarios  │ 120-180s│ recovery (¿vuelve a la normalidad?)
  Total: 180 segundos (3 minutos)

Preguntas que responde este test:
  - ¿El sistema sobrevive el pico sin caerse?
  - ¿Los errores que aparecen durante el pico desaparecen en la recovery?
  - ¿La latencia vuelve a los valores del baseline después del pico?
  - ¿Hay conexiones o recursos que no se liberan correctamente? (¿memory leak?)

Qué observar en Grafana:
  - El salto brusco en Request Rate cuando arranca el spike
  - La latencia p95/p99 durante el pico (¿se dispara la alerta?)
  - La curva de recovery: ¿vuelve al baseline suavemente o hay oscilaciones?

Cómo correrlo:
  docker compose --profile spike up -d
"""

from locust import LoadTestShape

from locustfile import ApiUser  # noqa: F401 — Locust detecta ApiUser automáticamente


class SpikeShape(LoadTestShape):
    """
    Baseline → Spike → Recovery. El spike es abrupto (spawn_rate alto).

    La clave del spike es el spawn_rate=150 en la segunda etapa:
    pasa de 10 a 200 usuarios casi instantáneamente para simular
    un evento viral o un ataque de tráfico.
    """

    stages = [
        # (duración acumulada, usuarios objetivo, velocidad de spawn)
        {"duration": 60,  "users": 10,  "spawn_rate": 5},    # baseline
        {"duration": 120, "users": 200, "spawn_rate": 150},   # SPIKE
        {"duration": 180, "users": 10,  "spawn_rate": 50},    # recovery
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None  # fin del test
