# Guía de Performance Testing con Locust

Cuatro tipos de test de performance sobre la misma API, cada uno ejecutable con **un solo comando** y diseñado para que el resultado se vea "en blanco y negro" en Grafana.

| Test | Pregunta que responde | Duración | Comando |
|---|---|---|---|
| **Smoke** | ¿Prende? ¿Todos los endpoints responden bien? | ~20 s | `./run-test.sh smoke` |
| **Load** | ¿Aguanta la carga *esperada* cumpliendo el SLA? | ~3 min | `./run-test.sh load` |
| **Stress** | ¿Dónde se rompe? ¿Cómo se degrada? | ~3.5 min | `./run-test.sh stress` |
| **Spike** | ¿Sobrevive a un pico repentino y se recupera solo? | ~2.75 min | `./run-test.sh spike` |

---

## 1. Levantar todo

Desde la raíz del repo:

```bash
docker compose down -v          # (opcional) arrancar de cero
docker compose up -d --build
```

Abrir Grafana en **http://localhost:3001** → abre directo el tablero **Performance Testing** (no hace falta loguearse para mirar; para editar: `admin` / `admin`).

Después, correr cualquier test:

```bash
./run-test.sh smoke
```

El script espera a que la API esté arriba, construye la imagen de Locust, corre el test y al final imprime una **tabla por etapa** con el veredicto contra el SLA. El reporte HTML de Locust queda en `performance-tests/reports/<test>-report.html`.

---

## 2. El sistema bajo prueba (por qué los resultados son tan nítidos)

> Diagramas de la app y explicación de cuándo/por qué se rompe: **[TIENDA.md](TIENDA.md)**.

Los tests le pegan a la "API de tienda" de `py-app`:

| Endpoint | Qué hace | Tiempo de servicio |
|---|---|---|
| `GET /api/productos` | lectura liviana | ~60 ms |
| `POST /api/pedidos` | escritura más pesada | ~220 ms |

Ambos usan un **pool de 10 conexiones** a una base de datos simulada. Ese pool es el cuello de botella, y le da a la API una **capacidad conocida**:

```
capacidad = 10 conexiones / 0.1 s por request (promedio de la mezcla 3:1) ≈ 100 req/s
```

- Si hay una conexión libre → se atiende enseguida.
- Si no → el request **espera en cola**. La latencia sube.
- Si espera más de **1 segundo** → **HTTP 503** "servidor saturado".

Del lado de Locust, cada usuario virtual hace **2 requests por segundo**, así que la cuenta es directa:

```
usuarios × 2 = req/s pedidos     →     ~50 usuarios = 100% de la capacidad
```

> Se puede cambiar la capacidad con las variables `DB_POOL_SIZE` y `QUEUE_TIMEOUT` del servicio `py-app` en `docker-compose.yml`.

### SLA (la vara para decir "anda bien")

- **p95 < 500 ms**: el 95% de los requests responde en menos de medio segundo.
- **errores < 1%**.

En Grafana el SLA es la **línea punteada roja** de los gráficos de latencia y errores.

---

## 3. Cómo leer el tablero

- **Arriba, "La carga"**: lo que hace Locust → test y etapa en curso, usuarios virtuales.
- **Abajo, "La respuesta"**: cómo reacciona la API → throughput, latencia, pool, cola, errores.
- **Franjas de color en todos los gráficos**: cada etapa del test queda marcada automáticamente. **Azul** = etapa normal, **roja** = pico o sobrecarga.

Los paneles clave:

| Panel | Qué mirar |
|---|---|
| **Throughput** (apilado) | La altura total es lo que *piden* los usuarios. Lo **verde** (atendido) nunca pasa la línea de capacidad (~100 req/s); lo que sobra es **rojo** (503). |
| **Latencia p50/p95/p99** | Mientras esté debajo de la línea roja, se cumple el SLA. |
| **Conexiones del pool en uso** | Cuando toca 10 → saturado. |
| **Requests en cola** | En 0 = sano. Si crece, la latencia sube. |
| **% de errores** | Por encima del 1% → no se cumple el SLA. |
| **CPU de py-app** | Queda baja aunque la API sature: el cuello de botella **no** es la CPU sino el pool. (¡Monitorear solo CPU no alcanza!) |

---

## 4. Smoke test — "¿prende?"

```bash
./run-test.sh smoke
```

- **Carga:** 1 usuario durante 20 segundos.
- **Qué hace:** recorre **todos** los endpoints en orden y valida status code **y contenido** de cada respuesta (incluido un caso de error esperado: un pedido inválido tiene que devolver 400).
- **Veredicto:** pasa si hay 0 errores y p95 < 500 ms. Si falla, el script termina con **exit code 1**.

**En Grafana:** prácticamente nada. Una línea bajita. Esa es la idea: el smoke no mide performance, verifica que el sistema funcione. Si el smoke falla, no tiene sentido correr nada más.

**En CI:** el workflow `.github/workflows/smoke-test.yml` corre este test en **cada Pull Request**. Si algún endpoint se rompe, el PR queda en rojo.

---

## 5. Load test — "¿aguanta un día normal?"

```bash
./run-test.sh load
```

| Etapa | Usuarios | Duración |
|---|---|---|
| rampa | 0 → 30 | 20 s |
| carga normal | 30 (≈ 60 req/s = 60% de la capacidad) | 140 s |
| bajada | 30 → 0 | 20 s |

**Veredicto:** pasa/no pasa contra el SLA (exit code 1 si no cumple). Resultado típico: ~60 req/s, p50 ≈ 65 ms, p95 ≈ 240 ms, 0% errores → ✅ PASA.

**En Grafana:** una **meseta aburrida**. Usuarios planos, ~60 req/s planos, latencia plana muy por debajo de la línea roja, **cero** errores, el pool nunca llega a 10 y la cola está siempre en 0.

> Mensaje para la clase: *aburrido = sano*. El load test confirma que el sistema cumple con la carga que esperamos. No busca romper nada.

---

## 6. Stress test — "¿dónde se rompe?"

```bash
./run-test.sh stress
```

Escalones de 30 segundos: **20 → 40 → 60 → 80 → 100 → 120 → 150** usuarios.

**En Grafana se ven tres zonas:**

1. **20–40 usuarios (franjas azules) → todo verde.** Los req/s suben al mismo ritmo que los usuarios. La latencia ni se mueve.
2. **60–80 usuarios → saturación.** Los req/s **se aplanan** contra la línea de capacidad (~100) aunque haya más usuarios. El pool está 10/10, aparece **cola**, y la latencia **cruza el SLA**.
3. **100–150 usuarios → quiebre.** Las esperas llegan a 1 s y aparecen **503** (rojo en throughput y errores): ~1% con 100 usuarios, ~12% con 120, ~30% con 150.

**Veredicto:** no tiene pasa/no pasa (exit code 0). La tabla final por etapa muestra en qué escalón aparece el primer ❌: ese es el **punto de quiebre**.

Resultado real de una corrida (la tabla que imprime el script):

```
  Etapa                  Usuarios    Req/s   p50 ms   p95 ms   Errores   SLA
  20 usuarios                  20     40.2       64      236      0.0%   ✅
  40 usuarios                  40     79.6       67      241      0.0%   ✅
  60 usuarios                  60     98.0      558      748      0.0%   ❌   ← se satura: la latencia cruza el SLA
  80 usuarios                  80     99.8      790      980      0.0%   ❌
  100 usuarios                100    102.9      962     1144      0.8%   ❌   ← empiezan los 503
  120 usuarios                120    113.6     1038     1208     11.7%   ❌
  150 usuarios                150    136.4     1046     1218     29.4%   ❌
```

Notar que **Req/s se clava en ~100** a partir de 60 usuarios: más usuarios ya no significa más trabajo hecho, solo más espera y más errores.

> Preguntas para la clase: ¿con cuántos usuarios se rompe? ¿Qué se rompe primero, la latencia o los errores? ¿Por qué la CPU sigue baja?

---

## 7. Spike test — "¿sobrevive a un pico y se recupera?"

```bash
./run-test.sh spike
```

| Etapa | Usuarios | Duración |
|---|---|---|
| normal | 20 (40 req/s) | 60 s |
| **PICO** | **200** (de golpe, en 1 segundo) | 45 s |
| recuperación | 20 | 60 s |

**En Grafana:** un bloque rojo en el medio de dos zonas **idénticas**.

- **normal** y **recuperación**: mismos req/s, misma latencia, cero errores.
- **PICO**: throughput clavado en la capacidad, la cola se llena, la latencia salta por encima de 1 s y ~50% de los requests son 503.

```
  Etapa                  Usuarios    Req/s   p50 ms   p95 ms   Errores   SLA
  normal                       20     39.9       65      236      0.0%   ✅
  PICO                        200    188.0     1008     1218     47.8%   ❌
  recuperación                 20     39.9       64      238      0.0%   ✅   ← idéntico a "normal"
```

**Lo importante del spike no es el pico sino la recuperación:** si después del pico la latencia y los errores **vuelven solos** a los valores de "normal", el sistema es resiliente. Si quedaran altos (conexiones que no se liberan, memory leak, colas que no se vacían), tendríamos un problema aunque el pico haya pasado.

> Diferencia con stress: el stress sube **de a poco** para encontrar el límite; el spike salta **de golpe** para ver la reacción y la recuperación.

---

## 8. Estructura de archivos

```
run-test.sh                        # ./run-test.sh <smoke|load|stress|spike>
TIENDA.md                          # la app bajo prueba: diagramas y por qué se rompe
py-app/app.py                      # la tienda (incluye la línea comentada para romper el smoke)
performance-tests/
├── Dockerfile                     # imagen de Locust + exporter de Prometheus
├── common.py                      # usuario de la tienda, etapas, SLA, métricas, anotaciones, resumen
├── smoke/   locustfile.py + README.md (diagrama y resultado esperado)
├── load/    locustfile.py + README.md
├── stress/  locustfile.py + README.md
├── spike/   locustfile.py + README.md
└── reports/                       # reportes HTML de Locust
monitoring/grafana/dashboards/
└── performance-testing.json       # tablero de esta clase
.github/workflows/smoke-test.yml   # smoke test en cada PR
```

**Concepto clave:** la clase `User` define **qué** hace cada usuario virtual; la `LoadTestShape` (las etapas) define **cuántos** usuarios hay en cada momento. Los cuatro tests de carga usan el mismo usuario y cambian solo la forma.

Mientras corre un test, Locust:
- expone `locust_users` y `locust_stage` en el puerto 9646 → Prometheus los lee y Grafana muestra "la carga";
- crea anotaciones en Grafana al empezar y terminar cada etapa → las franjas de colores.

---

## 9. Problemas comunes

| Síntoma | Solución |
|---|---|
| `py-app no responde` | Levantar el stack: `docker compose up -d --build` |
| El tablero no muestra usuarios virtuales | Solo aparecen **mientras** corre un test |
| Quedó un Locust colgado (Ctrl+C a mitad) | `docker rm -f locust` (el script también lo limpia solo) |
| Datos de corridas anteriores en los gráficos | Normal: elegir el rango de tiempo, o `docker compose down -v` para empezar de cero |
