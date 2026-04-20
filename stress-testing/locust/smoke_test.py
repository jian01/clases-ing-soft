"""
SMOKE TEST
==========
Objetivo: verificar que todos los endpoints responden correctamente
          después de un deploy o antes de correr tests más pesados.

Patrón de carga:
  - 1 usuario durante 60 segundos
  - El test termina solo (la Shape retorna None al final)

Cuándo usarlo:
  - Después de cada `docker compose up`
  - Como gate antes del stress/spike test
  - En el pipeline de CI/CD como verificación de sanidad

Cómo correrlo:
  docker compose --profile smoke up -d
"""

from locust import LoadTestShape

from locustfile import ApiUser  # noqa: F401 — Locust detecta ApiUser automáticamente


class SmokeShape(LoadTestShape):
    """
    1 usuario solo, 60 segundos. Termina automáticamente.

    Si hay errores en este test, no tiene sentido correr stress ni spike.
    """

    stages = [
        {"duration": 60, "users": 1, "spawn_rate": 1},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None  # fin del test
