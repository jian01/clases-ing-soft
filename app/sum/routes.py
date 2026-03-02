"""Rutas relacionadas con operaciones de suma."""

from typing import Dict

import httpx
from fastapi import APIRouter

router = APIRouter()


@router.get("/sum")
def sum_numbers(a: int, b: int) -> Dict[str, int]:
    """Suma dos numeros enteros.

    :param a: Primer sumando.
    :param b: Segundo sumando.
    :return: Resultado de la suma.
    """
    return {"result": a + b}


@router.get("/sum-square")
def sum_square(a: int, b: int) -> Dict[str, int]:
    """Suma dos numeros llamando al endpoint ``/sum`` y devuelve el cuadrado.

    :param a: Primer sumando.
    :param b: Segundo sumando.
    :return: Cuadrado de la suma.
    """
    with httpx.Client() as client:
        response = client.get(
            "http://127.0.0.1:8000/sum",
            params={"a": a, "b": b},
        )
    total = response.json()["result"]
    return {"result": total**2}
