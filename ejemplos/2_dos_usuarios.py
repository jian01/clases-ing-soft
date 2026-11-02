# Filminas 11 y 17. Para la versión SIN pesos (filmina 11), borrar las dos líneas "weight".
from locust import HttpUser, task, between


class UsuarioNormal(HttpUser):
    wait_time = between(1, 3)
    weight = 5  # MUCHOS

    @task(3)
    def home(self):
        self.client.get("/")

    @task(1)
    def lento(self):
        self.client.get("/lento")


class UsuarioIntensivo(HttpUser):
    wait_time = between(0.1, 0.5)
    weight = 1  # POCOS

    @task
    def carga(self):
        self.client.get("/")
