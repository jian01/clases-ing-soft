"""Modulo principal de la aplicacion FastAPI."""

from typing import Dict

from fastapi import FastAPI

from app.sum.routes import router as sum_router
from app.user.routes import router as user_router

app = FastAPI(title="API de ejemplo")

app.include_router(sum_router)
app.include_router(user_router)


@app.get("/hello")
def root() -> Dict[str, str]:
    """Devuelve un saludo.

    :return: Mensaje de saludo.
    """
    return {"message": "Hola mundo!"}
