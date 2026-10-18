"""
SPIKE TEST — "¿sobrevive a un pico repentino y se recupera?"
============================================================
Objetivo: simular un pico ABRUPTO de tráfico (una promo, un link viral) y ver
dos cosas: qué pasa durante el pico y, sobre todo, si el sistema VUELVE solo
a la normalidad cuando el pico termina.

Carga (2 min 45s):
  normal        20 usuarios   60s   ← 40 req/s, todo verde
  PICO         200 usuarios   45s   ← x10 de golpe (en 1 segundo)
  recuperación  20 usuarios   60s   ← ¿vuelve a verse igual que "normal"?

En Grafana: un "escalón" rojo en el medio de dos zonas idénticas.
  - Normal y recuperación: mismas req/s, misma latencia, cero errores.
  - PICO: req/s clavados en la capacidad (~100), latencia por encima del SLA,
    pool 10/10, cola llena y muchos 503.
"""

from common import ShopUser, Stage, StagedShape


class Cliente(ShopUser):
    pass


class SpikeShape(StagedShape):
    test_name = "spike"
    stages = [
        Stage("normal", duration=60, users=20, spawn_rate=20),
        Stage("PICO", duration=45, users=200, spawn_rate=200, pico=True),
        Stage("recuperación", duration=60, users=20, spawn_rate=200),
    ]
