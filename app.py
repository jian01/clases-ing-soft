import os
import time

from flask import Flask

app = Flask(__name__)

# Nombre de la instancia (lo define docker-compose: "API 1" o "API 2")
API_NAME = os.environ.get("API_NAME", "API")


@app.route("/")
def home():
    time.sleep(0.1)  # filmina 9: cambiar a 0.5 para el experimento
    return f"OK - respuesta desde {API_NAME}"


@app.route("/lento")
def lento():
    time.sleep(1)
    return "LENTO"


@app.route("/login", methods=["POST"])
def login():
    return {"status": "ok"}


@app.route("/products")
def products():
    return {"products": list(range(1, 11))}


@app.route("/product/<int:id>")
def product(id):
    return {"id": id}


@app.route("/buy", methods=["POST"])
def buy():
    time.sleep(0.3)  # filmina 26: cambiar a 1 para ver el colapso por compras
    return {"status": "purchased"}


app.run(host="0.0.0.0", port=5000, threaded=False)
# app.run(host="0.0.0.0", port=5000)