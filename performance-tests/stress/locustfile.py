"""
STRESS TEST — "¿dónde se rompe?"
================================
Objetivo: subir la carga por ESCALONES más allá de lo esperado hasta encontrar
el punto de quiebre. No tiene veredicto pasa/no pasa: el resultado es saber
CUÁNTO aguanta y CÓMO se degrada.

Carga (3.5 min): escalones de 30s
  20 → 40 → 60 → 80 → 100 → 120 → 150 usuarios
  (cada usuario hace 2 req/s → se piden 40, 80, 120, ... 300 req/s)

Capacidad de la API: ~100 req/s (pool de 10 conexiones x 100 ms).

En Grafana se ven tres zonas:
  1. 20-40 usuarios  → todo verde: req/s crecen junto con los usuarios.
  2. 60-80 usuarios  → SATURACIÓN: los req/s se aplanan en la línea de capacidad,
                       el pool está 10/10, crece la cola y la latencia cruza el SLA.
  3. 100+ usuarios   → QUIEBRE: aparecen errores 503 (la cola espera más de 1s).
"""

from common import ShopUser, Stage, StagedShape


class Cliente(ShopUser):
    pass


class StressShape(StagedShape):
    test_name = "stress"
    stages = [
        Stage("20 usuarios", duration=30, users=20, spawn_rate=20),
        Stage("40 usuarios", duration=30, users=40, spawn_rate=20),
        Stage("60 usuarios", duration=30, users=60, spawn_rate=20, pico=True),
        Stage("80 usuarios", duration=30, users=80, spawn_rate=20, pico=True),
        Stage("100 usuarios", duration=30, users=100, spawn_rate=20, pico=True),
        Stage("120 usuarios", duration=30, users=120, spawn_rate=20, pico=True),
        Stage("150 usuarios", duration=30, users=150, spawn_rate=30, pico=True),
    ]
