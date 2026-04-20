"""
Comportamiento base de los usuarios virtuales.

Este archivo define QUÉ hacen los usuarios (las acciones).
Los archivos smoke_test.py, stress_test.py y spike_test.py definen
CUÁNTOS usuarios corren y durante cuánto tiempo (la forma de carga).
"""

import random

from locust import HttpUser, between, tag, task


class ApiUser(HttpUser):
    """
    Usuario típico de la API.
    Mezcla de health checks, forecasts y operaciones de datos con think time realista.
    """

    wait_time = between(1, 3)

    @task(1)
    @tag("salud")
    def health_check(self):
        with self.client.get(
            "/health", name="GET /health", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Health check falló: {resp.status_code}")

    @task(4)
    @tag("forecast")
    def forecast(self):
        """Latencia aleatoria entre 0.5s y 4s — rango realista para ver histograma."""
        delay = round(random.uniform(0.5, 4.0), 2)
        with self.client.post(
            "/forecast",
            json={"delay": delay, "simulate_error": False},
            name="POST /forecast",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Forecast falló: {resp.status_code}")

    @task(2)
    @tag("datos")
    def guardar_dato(self):
        numero = random.randint(1, 9999)
        self.client.post(
            "/save",
            json={"content": f"registro #{numero}"},
            name="POST /save",
        )

    @task(2)
    @tag("datos")
    def leer_datos(self):
        self.client.get("/read", name="GET /read")

    @task(1)
    @tag("errores")
    def forecast_con_error(self):
        """
        Genera errores 500 de forma intencional (~11% del tráfico de forecast).
        Sirve para observar el error rate subir en Grafana y disparar alertas.
        """
        with self.client.post(
            "/forecast",
            json={"delay": 0.1, "simulate_error": True},
            name="POST /forecast (error 500)",
            catch_response=True,
        ) as resp:
            # El 500 es intencional: success() evita que Locust lo cuente como falla
            if resp.status_code == 500:
                resp.success()
            else:
                resp.failure(f"Se esperaba 500, llegó: {resp.status_code}")
