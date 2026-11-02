# Filmina 24: login + navegación + compra
from locust import HttpUser, task, between
import random


class EcommerceUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # LOGIN (se ejecuta una vez por usuario)
        self.client.post("/login", json={"username": "user", "password": "pass"})

    @task(3)
    def browse_products(self):
        self.client.get("/products")

    @task(2)
    def view_product(self):
        product_id = random.randint(1, 10)
        self.client.get(f"/product/{product_id}")

    @task(1)
    def buy_product(self):
        product_id = random.randint(1, 10)
        self.client.post("/buy", json={"product_id": product_id, "quantity": 1})
