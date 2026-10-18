"""
LOAD TEST — "¿aguanta un día normal?"
=====================================
Objetivo: comprobar que con la carga ESPERADA el sistema cumple el SLA
de forma sostenida. Es un test con veredicto: pasa o no pasa.

Carga (3 min):
  rampa       0 → 30 usuarios   20s
  carga normal    30 usuarios  140s   ← ~60 req/s = 60% de la capacidad (100 req/s)
  bajada     30 → 0  usuarios   20s

Pasa si: p95 < 500 ms y errores < 1%  (exit code 1 si no cumple).

En Grafana: una MESETA. Usuarios planos, req/s planos (~60), latencia plana
(~100 ms, muy por debajo de la línea roja), cero errores, el pool nunca se llena
y la cola está siempre en 0. "Aburrido" = sano.
"""

from common import ShopUser, Stage, StagedShape


class Cliente(ShopUser):
    pass


class LoadShape(StagedShape):
    test_name = "load"
    strict_sla = True
    stages = [
        Stage("rampa", duration=20, users=30, spawn_rate=1.5),
        Stage("carga normal", duration=140, users=30, spawn_rate=1.5),
        Stage("bajada", duration=20, users=0, spawn_rate=1.5),
    ]
