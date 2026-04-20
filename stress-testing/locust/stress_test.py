"""
STRESS TEST
===========
Objetivo: encontrar el punto de quiebre del sistema.
          ¿A cuántos usuarios concurrentes empieza a degradarse el servicio?

Patrón de carga (ramp-up escalonado):
  0 ──► 10 usuarios  │ 60s  │ warm-up
  10 ──► 50           │ 120s │ carga baja
  50 ──► 100          │ 120s │ carga media
  100 ──► 200         │ 120s │ carga alta
  200 ──► 0           │ 30s  │ cool-down
  Total: ~450 segundos (~7.5 minutos)

Qué observar en Grafana:
  - En qué stage el p95 de /forecast supera los 5s (alerta LatenciaForecastAlta)
  - Si el error rate sube al saturarse las conexiones
  - CPU y memoria durante los stages de alta carga

Cómo correrlo:
  docker compose --profile stress up -d
"""

from locust import LoadTestShape

from locustfile import ApiUser  # noqa: F401 — Locust detecta ApiUser automáticamente


class StressShape(LoadTestShape):
    """
    Ramp-up escalonado hasta 200 usuarios, luego cool-down.

    Las duraciones son ACUMULATIVAS (no por etapa).
    Ej: stage 2 empieza en t=60s y termina en t=180s.
    """

    # Fórmula para calcular spawn_rate: Δusuarios / Δtiempo_del_stage
    # Ejemplo con carga alta (10k → 200k usuarios):
    #   {"duration": 60,  "users": 10000,  "spawn_rate": 167},  # 10000/60
    #   {"duration": 180, "users": 50000,  "spawn_rate": 334},  # 40000/120
    #   {"duration": 300, "users": 100000, "spawn_rate": 417},  # 50000/120
    #   {"duration": 420, "users": 200000, "spawn_rate": 834},  # 100000/120
    #   {"duration": 450, "users": 0,      "spawn_rate": 5000}, # cool-down
    stages = [
        # (duración acumulada, usuarios objetivo, velocidad de spawn)
        {"duration": 60,  "users": 10,  "spawn_rate": 5},   # warm-up
        {"duration": 180, "users": 50,  "spawn_rate": 10},  # carga baja
        {"duration": 300, "users": 100, "spawn_rate": 10},  # carga media
        {"duration": 420, "users": 200, "spawn_rate": 20},  # carga alta
        {"duration": 450, "users": 0,   "spawn_rate": 50},  # cool-down
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None  # fin del test
