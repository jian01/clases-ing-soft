"""Microservicio de sumas."""

from typing import Dict

from fastapi import FastAPI

from app.sum.routes import router as sum_router

app = FastAPI(title="API de sumas")

app.include_router(sum_router)


@app.get("/hello")
def root() -> Dict[str, str]:
    """Devuelve un saludo.

    :return: Mensaje de saludo.
    """
    return {"message": "Hola mundo!"}
