# Guía de Stress Testing con Locust

Guía paso a paso para levantar y ejecutar los tests de performance sobre la API de la clase.

---

## 1. Levantar el stack principal

Desde la **raíz del repositorio** (`clases-ing-soft/`):

```bash
docker compose up -d --build
```

Verificar que todos los servicios estén corriendo:

```bash
docker compose ps
```

| Servicio | Puerto | Descripción |
|---|---|---|
| `py-app` | 5000 | API FastAPI (la que vamos a estresar) |
| `react-app` | 3000 | Frontend |
| `prometheus` | 9090 | Base de datos de métricas |
| `grafana` | 3001 | Dashboards — **tener esto abierto durante todos los tests** |
| `node-exporter` | 9100 | Métricas del sistema |
| `webhook-receiver` | 8080 | Receptor de alertas |

Abrir Grafana en `http://localhost:3001` (usuario: `admin`, contraseña: `admin`) y dejar el dashboard **Monitoreo** visible durante toda la práctica.

---

## 2. Locust

### Imagen y arquitectura

Usamos la imagen oficial `locustio/locust:2.32.2`.

Los contenedores de Locust se conectan a la red interna del stack mediante una red Docker externa (`clases-ing-soft_default`), lo que les permite alcanzar la API directamente por nombre de host (`py-app:5000`) sin necesidad de exponer puertos adicionales.

### Archivos del directorio `stress-testing/locust/`

| Archivo | Rol |
|---|---|
| `locustfile.py` | Define el comportamiento de cada usuario virtual (qué endpoints llama y con qué datos) |
| `smoke_test.py` | Shape: 1 usuario, 60 segundos — verificación de sanidad |
| `stress_test.py` | Shape: ramp-up escalonado 10→50→100→200 usuarios |
| `spike_test.py` | Shape: baseline → pico x20 → recovery |

**Concepto clave:** el archivo `locustfile.py` define _qué_ hace cada usuario. Los archivos `*_test.py` definen _cuántos_ usuarios corren y _cuándo_ — esto se llama `LoadTestShape`.

### Nota sobre la sintaxis de docker compose con perfiles

Los tests se lanzan con el flag `--profile`. **El flag va antes del subcomando** (`up` o `down`):

```bash
# Correcto
docker compose --profile smoke up
```

---

## 3. Smoke Test

**Objetivo:** verificar que todos los endpoints responden correctamente antes de generar carga real.

**Patrón de carga:** 1 usuario, 60 segundos. El test termina solo.

Desde `stress-testing/locust/`:

```bash
docker compose --profile smoke up
```

El test corre en modo headless (sin UI web). Verás los logs en la terminal y cuando termine (60s), el contenedor se detiene solo. El reporte HTML queda en `reports/smoke-report.html`.

**Interpretación:** si hay cualquier error en el smoke test, revisar que el stack principal esté levantado antes de continuar con los otros tests.

---

## 4. Stress Test

**Objetivo:** encontrar el punto de quiebre del sistema mediante un ramp-up escalonado.

**Patrón de carga:**

| Stage | Usuarios | Tiempo acumulado |
|---|---|---|
| Warm-up | 10 | 0 – 60s |
| Carga baja | 50 | 60 – 180s |
| Carga media | 100 | 180 – 300s |
| Carga alta | 200 | 300 – 420s |
| Cool-down | 0 | 420 – 450s |

Duración total: ~7.5 minutos. El test termina automáticamente.

Desde `stress-testing/locust/`:

```bash
docker compose --profile stress up
```

Abrir la UI de Locust en `http://localhost:8089` para ver los resultados en tiempo real mientras también se observa Grafana.

### Qué observar

En la UI de Locust (`:8089`):
- **Statistics:** RPS, latencia media, p95, p99 y error rate por endpoint
- **Charts:** evolución de RPS y tiempos de respuesta a lo largo del test

En Grafana (`http://localhost:3001`):
- **Latency p95 / p99:** ¿En qué stage supera los 5 segundos?
- **Error Rate %:** ¿Sube cuando se satura el sistema?
- **Forecast Duration Distribution:** el histograma muestra cómo se ensancha la distribución con la carga
- **CPU / Memory:** ¿Cuál es el cuello de botella — la app o los recursos del host?

### Alerta esperada

Si el p95 de `/forecast` supera los 5 segundos durante más de 2 minutos, se dispara la alerta `LatenciaForecastAlta` en Grafana. Verificar en `http://localhost:3001/alerting/list`.

Para detener antes de que termine solo:

```bash
docker compose --profile stress down
```

---

## 5. Spike Test

**Objetivo:** evaluar si el sistema sobrevive un pico abrupto de tráfico y si se recupera correctamente.

**Patrón de carga:**

| Stage | Usuarios | Duración |
|---|---|---|
| Baseline | 10 | 0 – 60s |
| Spike (pico) | 200 | 60 – 120s |
| Recovery | 10 | 120 – 180s |

Duración total: 3 minutos. El test termina automáticamente.

Desde `stress-testing/locust/`:

```bash
docker compose --profile spike up
```

### Qué observar

El spike es intencional y abrupto: en la UI de Locust (`:8089`) y en Grafana se verá un salto vertical en el RPS y la latencia al entrar en el stage de pico.

Preguntas para responder durante el test:
- ¿El sistema sobrevive el pico sin retornar errores?
- ¿La latencia p95 vuelve a los valores del baseline durante la recovery?
- ¿El error rate baja a 0 después del pico?

Una recovery lenta o incompleta puede indicar conexiones no liberadas, memory leaks, o un servidor que no escala de vuelta.

### Alerta esperada

La alerta `ErrorRateAlto` puede dispararse durante el pico si el sistema empieza a rechazar conexiones. Ver en Grafana si se normaliza durante la recovery.

Para detener antes de que termine solo:

```bash
docker compose --profile spike down
```

---

## 6. Leer los reportes HTML

Cada test genera un reporte HTML en `stress-testing/locust/reports/`:

```
reports/
├── smoke-report.html
├── stress-report.html
└── spike-report.html
```

Abrir directamente en el navegador. El reporte incluye:
- Tabla de resultados por endpoint (RPS, latencia, error rate)
- Gráficos de RPS y tiempos de respuesta en el tiempo
- Histograma de distribución de latencias

> Los reportes se sobreescriben en cada ejecución. Renombrar el archivo si querés conservar una corrida anterior.

---

## 7. Alertas configuradas en Grafana

| Alerta | Umbral | Cuándo se dispara |
|---|---|---|
| `ErrorRateAlto` | > 1% por 2 min | Durante el pico del spike test o si hay muchos errores en stress |
| `LatenciaForecastAlta` | p95 > 5s por 2 min | En los stages altos del stress test |
| `CPUAltaSostenida` | CPU > 80% por 5 min | En máquinas con recursos limitados bajo stress alto |

Ver alertas activas en `http://localhost:3001/alerting/list`.

---

## 8. Limpieza

Detener Locust (si el test no terminó solo):

```bash
# Desde stress-testing/locust/
docker compose --profile stress down   # reemplazar por spike según corresponda
```

Detener todo el stack (desde la raíz del repositorio):

```bash
docker compose down
```

Borrar volúmenes (reset completo de datos):

```bash
docker compose down -v
```

Borrar reportes de Locust:

```bash
rm -rf stress-testing/locust/reports/
```
