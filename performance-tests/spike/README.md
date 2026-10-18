# Spike test — "¿sobrevive a un pico y se recupera?"

```bash
./run-test.sh spike     # ~2.75 min
```

**Qué es:** un pico **abrupto** de tráfico (una promo, un link viral): de 20 a 200 usuarios **en 1 segundo**. Importa qué pasa durante el pico, pero sobre todo si el sistema **vuelve solo a la normalidad** cuando termina. Exit 0 (exploratorio).

> Diferencia con stress: el stress sube **de a poco** para encontrar el límite; el spike salta **de golpe** para ver la reacción y la recuperación.

## Forma de la carga

```mermaid
xychart-beta
    title "Usuarios virtuales en el tiempo"
    x-axis "segundos" [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165]
    y-axis "usuarios" 0 --> 220
    line [20, 20, 20, 20, 200, 200, 200, 20, 20, 20, 20, 20]
```

| Etapa | Usuarios | Duración | req/s pedidos |
|---|---|---|---|
| normal | 20 | 60 s | 40 |
| **PICO** | **200** | 45 s | **400** (capacidad: 100) |
| recuperación | 20 | 60 s | 40 |

## Flujo

```mermaid
flowchart LR
    n["🟢 normal · 20 usuarios<br/>40 req/s<br/>p95 ≈ 240 ms · 0% errores"] -->|"t = 60 s<br/>x10 de golpe"| p["🔴 PICO · 200 usuarios<br/>atiende ~100 req/s, cola llena<br/>p95 ≈ 1.2 s · ~48% 503"]
    p -->|"t = 105 s"| r["🟢 recuperación · 20 usuarios<br/>¿idéntico a normal?"]
```

## Resultado esperado

```
  Etapa                  Usuarios    Req/s   p50 ms   p95 ms   Errores   SLA
  normal                       20     39.9       65      236      0.0%   ✅
  PICO                        200    188.0     1008     1218     47.8%   ❌
  recuperación                 20     39.9       64      238      0.0%   ✅  ← idéntico a "normal"
```

**En Grafana:** un bloque rojo entre dos zonas **idénticas**. Si después del pico la latencia o los errores quedaran altos (conexiones que no se liberan, memory leak, colas que no se vacían), el sistema tendría un problema aunque el pico ya haya pasado.
