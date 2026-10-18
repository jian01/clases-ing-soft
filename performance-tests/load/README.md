# Load test — "¿aguanta un día normal?"

```bash
./run-test.sh load      # ~3 min
```

**Qué es:** se aplica la carga **esperada** (30 usuarios ≈ 60 req/s = 60% de la capacidad) de forma sostenida y se verifica que se cumpla el SLA. Tiene veredicto: **pasa o no pasa** (exit code 1 si no cumple).

## Forma de la carga

```mermaid
xychart-beta
    title "Usuarios virtuales en el tiempo"
    x-axis "segundos" [0, 20, 40, 60, 80, 100, 120, 140, 160, 180]
    y-axis "usuarios" 0 --> 60
    line [0, 30, 30, 30, 30, 30, 30, 30, 30, 0]
```

| Etapa | Usuarios | Duración | req/s pedidos |
|---|---|---|---|
| rampa | 0 → 30 | 20 s | 0 → 60 |
| carga normal | 30 | 140 s | 60 (capacidad: 100) |
| bajada | 30 → 0 | 20 s | 60 → 0 |

## Flujo

```mermaid
flowchart LR
    u["30 usuarios<br/>× 2 req/s"] -->|"60 req/s"| api["py-app<br/>capacidad ~100 req/s"]
    api --> pool["pool: ~6 de 10<br/>conexiones en uso"]
    pool --> q["cola ≈ 0"]
    q --> r(["✅ p95 ≈ 240 ms<br/>0% errores"])
```

## Resultado esperado

```
  Etapa                  Usuarios    Req/s   p50 ms   p95 ms   Errores   SLA
  rampa                        30     31.0       64      238      0.0%   ✅
  carga normal                 30     59.9       65      236      0.0%   ✅
  bajada                        0     29.2       64      235      0.0%   ✅
  Veredicto del test 'load': ✅ PASA
```

**En Grafana:** una **meseta aburrida**. Todo plano, latencia muy por debajo de la línea roja, cero errores, cola en 0. *Aburrido = sano.*
