# Smoke test — "¿prende?"

```bash
./run-test.sh smoke     # ~20 s
```

**Qué es:** la prueba más chica posible. **1 usuario** recorre **todos** los endpoints en orden durante 20 s y valida status code **y contenido** de cada respuesta. No mide performance: verifica que el sistema funcione. Si el smoke falla, no tiene sentido correr nada más.

Corre en **cada Pull Request** (`.github/workflows/smoke-test.yml`): si falla, el PR queda en rojo.

## Flujo

```mermaid
flowchart LR
    start([1 usuario<br/>20 s]) --> h["GET /health<br/>→ 200, status ok"]
    h --> p["GET /api/productos<br/>→ 200, lista no vacía"]
    p --> o["POST /api/pedidos<br/>→ 201, estado confirmado"]
    o --> bad["POST /api/pedidos cantidad=0<br/>→ 400 (error esperado)"]
    bad --> m["GET /metrics<br/>→ expone api_requests_total"]
    m -->|"repite hasta los 20 s"| h
    m --> v{"¿0 errores y<br/>p95 < 500 ms?"}
    v -->|sí| ok(["✅ PASA · exit 0"])
    v -->|no| ko(["❌ FALLA · exit 1<br/>PR en rojo"])
```

## Resultado esperado

```
  Etapa      Usuarios   Req/s   p50 ms   p95 ms   Errores   SLA
  smoke             1     2.3        3      ~225      0.0%   ✅
  Veredicto del test 'smoke': ✅ PASA
```

**En Grafana:** casi nada, una línea bajita. Esa es la idea.

## Demo: romperlo a propósito

En `py-app/app.py`, dentro de `listar_productos`, descomentar:

```python
# raise HTTPException(status_code=500, detail="Bug introducido para la demo")
```

y reconstruir: `docker compose up -d --build py-app`. Ahora `./run-test.sh smoke` termina con **❌ FALLA (exit code 1)** y el error `GET /api/productos: status 500, se esperaba 200`. Ver [TIENDA.md](../../TIENDA.md#demo-romper-el-smoke-test).
