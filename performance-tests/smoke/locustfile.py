"""
SMOKE TEST — "¿prende?"
=======================
Objetivo: verificar con carga MÍNIMA que todos los endpoints responden bien.
No mide performance: si el smoke falla, no tiene sentido correr nada más.

Carga:   1 usuario durante 20 segundos.
Valida:  status code + contenido de la respuesta de cada endpoint.
Pasa si: 0 errores y p95 < 500 ms.  Si falla → exit code 1 (bloquea el PR en CI).

En Grafana: una línea casi plana y bajita. Ni se nota. Esa es la idea.
"""

from locust import HttpUser, SequentialTaskSet, constant, task

from common import Stage, StagedShape


class RecorridoCompleto(SequentialTaskSet):
    """Recorre todos los endpoints de la API en orden, validando cada respuesta."""

    def _check(self, method, path, expected_status=200, validate=None, **kwargs):
        with self.client.request(method, path, name=path,
                                 catch_response=True, **kwargs) as resp:
            if resp.status_code != expected_status:
                resp.failure(f"status {resp.status_code}, se esperaba {expected_status}")
            elif validate and not validate(resp):
                resp.failure(f"respuesta inesperada: {resp.text[:120]}")
            else:
                resp.success()  # necesario cuando el status esperado es un 4xx

    @task
    def health(self):
        self._check("GET", "/health", validate=lambda r: r.json()["status"] == "ok")

    @task
    def productos(self):
        self._check("GET", "/api/productos", validate=lambda r: len(r.json()["productos"]) > 0)

    @task
    def pedido(self):
        self._check("POST", "/api/pedidos", expected_status=201,
                    json={"producto_id": 1, "cantidad": 2},
                    validate=lambda r: r.json()["estado"] == "confirmado")

    @task
    def pedido_invalido(self):
        # También probamos el camino de error: la API tiene que rechazarlo con 400
        self._check("POST", "/api/pedidos", expected_status=400,
                    json={"producto_id": 1, "cantidad": 0})

    @task
    def metrics(self):
        self._check("GET", "/metrics", validate=lambda r: "api_requests_total" in r.text)


class SmokeUser(HttpUser):
    tasks = [RecorridoCompleto]
    wait_time = constant(0.5)


class SmokeShape(StagedShape):
    test_name = "smoke"
    strict_sla = True
    stages = [
        Stage("smoke", duration=20, users=1, spawn_rate=1),
    ]
