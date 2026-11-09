# Guía asincrónica: Data Quality, Lineage y Governance

Esta guía es para recorrer la clase **por tu cuenta**, en tu máquina, sin haber estado en la clase en vivo. Vas a levantar un data warehouse completo con Docker, romper los datos a propósito de seis maneras distintas y ver qué herramientas detectan cada problema… y cuáles no.

Cada escenario está armado igual: primero te pedimos que **predigas** qué va a pasar, después lo corrés y lo mirás. Al final hay una explicación desplegable. Intentá responder antes de abrirla: es la mejor forma de que te quede.

---

## Qué vas a aprender

1. **Data quality**: cómo los tests de dbt detectan datos malos, qué tipos de problemas atrapa cada test, y por qué los tests solos **no alcanzan**.
2. **Observabilidad de datos**: qué es Elementary y cómo detecta anomalías comparando contra el historial.
3. **Lineage**: cómo saber de dónde viene cada número, a nivel de tabla (dbt docs) y de columna (DataHub).
4. **Governance**: dueños de los datos, contratos de frescura y marcado de datos sensibles (PII), declarados en el código.

## El contexto: qué datos hay

El warehouse tiene datos ficticios de una plataforma de **streaming de música**: artistas, canciones, plataformas (Spotify, YouTube, Apple Music, Tidal, Amazon Music) y 50.000 eventos de streams. Cada stream dice cuántas reproducciones tuvo una canción en una plataforma, en qué país y cuánto dinero generó (`ingresos_usd`).

Está organizado en la **arquitectura medallion**:

| Capa | Schema | Qué tiene |
|---|---|---|
| **Bronze** | `bronze` | Los datos crudos tal como llegaron de los CSV. Todo es texto. No se valida nada. |
| **Silver** | `silver` | Datos limpios: tipados, deduplicados y filtrados. Los modelos se llaman `stg_*`. |
| **Gold** | `gold` | Modelo estrella listo para análisis: `fact_streams` + dimensiones `dim_*`. |

Las herramientas del stack:

| Herramienta | Para qué |
|---|---|
| **PostgreSQL** | El warehouse. |
| **dbt** | Las transformaciones bronze → silver → gold, y los tests de calidad. |
| **Dagster** | El orquestador: corre la carga a bronze y después dbt. |
| **Elementary** | Observabilidad: guarda el historial de tests y métricas y detecta anomalías. |
| **Metabase** | Un dashboard ya armado para mirar los datos de cada capa sin escribir SQL. |
| **dbt docs** | Documentación y lineage del proyecto dbt. |
| **DataHub** (opcional) | Catálogo de datos con lineage por columna. |

---

## Requisitos

- **Docker** con **Docker Compose v2** (el comando es `docker compose`, sin guion). En Windows, Docker Desktop con WSL2.
- Unos **6 GB de RAM** libres para Docker.
- Una terminal **bash** (Linux, macOS, WSL o Git Bash en Windows).
- Estos puertos libres en tu máquina: `3000`, `3001`, `5433`, `8081`, `8082`, `8083`. Si alguno está ocupado, mirá [Problemas comunes](#problemas-comunes).

No hace falta instalar Python, dbt ni Postgres: todo corre adentro de Docker.

---

## Paso 1 — Levantar el entorno

```bash
git clone https://github.com/jian01/clases-ing-soft.git
cd clases-ing-soft
git checkout feature/data-quality

docker compose up --build -d
```

La primera vez tarda porque descarga y construye las imágenes. Verificá el estado:

```bash
docker compose ps
```

Esperá a que `postgres` y `metabase` digan `healthy` y `dagster` diga `running`. El contenedor `metabase-init` aparece como `Exited (0)` cuando termina: es un script que configura Metabase solo (usuario, conexión al warehouse y dashboards).

Abrí estas pestañas en el browser:

| Pestaña | URL | Login |
|---|---|---|
| Dagster (orquestador) | http://localhost:3000/assets | — |
| Metabase (dashboard) | http://localhost:3001 | `admin@demo.com` / `Admin1234!` |
| dbt docs (lineage) | http://localhost:8082 | — |

En Metabase, buscá el dashboard **"Data Quality — Anomalías"** (menú *Dashboards* o el buscador). Vas a usarlo todo el tiempo. Tiene una pestaña por tema; si una card dice *"relation does not exist"* es porque todavía no corriste el pipeline: es normal en este punto.

### Un atajo para la terminal

Vas a usar mucho un script que inyecta datos malos en bronze. Para no escribir el comando entero cada vez, definí este alias (vale para la terminal abierta):

```bash
alias dq='docker compose exec dagster python /workspace/scripts/inject_anomalias.py'
```

```bash
dq --list          # lista los escenarios
dq --scenario X    # inyecta el escenario X en bronze
dq --counts        # cuenta filas de "ayer" en bronze, silver y gold
dq --cleanup       # borra todo lo inyectado
```

Los datos inyectados tienen fecha de **ayer** y `stream_id` a partir de 900.000, así que no se mezclan con los datos originales.

---

## Paso 2 — Conocer el pipeline

En Dagster (http://localhost:3000/assets) mirá el grafo de assets. Vas a ver:

- `extract_to_bronze`: carga los CSV de `data/` a las tablas `bronze.*_raw`;
- los modelos de dbt de silver (`stg_*`) y gold (`dim_*`, `fact_streams`);
- `source_freshness_check`: chequea que bronze tenga datos recientes.

Abrí también estos archivos del repo, los vas a necesitar:

- `dbt/models/silver/stg_streams.sql`: cómo se limpia la tabla de streams;
- `dbt/models/silver/schema.yml` y `dbt/models/gold/schema.yml`: los tests y la metadata;
- `dbt/tests/`: tests escritos a mano.

---

## Paso 3 — Primera corrida del pipeline

En Dagster, **Materialize all** (arriba a la derecha en la vista de assets). También podés hacerlo desde la terminal:

```bash
docker compose exec dagster bash -c "cd /workspace/dagster && dagster job execute -m dwh_pipeline -j daily_pipeline"
```

Tiene que terminar en verde. Ahora abrí el dashboard de Metabase en la pestaña **0 · Corridas del pipeline** y anotá:

- Corridas del pipeline (cargas en bronze): **1**
- Filas en `bronze.streams_raw`: **50.000**
- Filas en silver y en gold: **50.000**

### 🤔 Predicción

Vas a correr **exactamente el mismo pipeline otra vez**, con los mismos CSV. ¿Qué va a pasar con la cantidad de filas en bronze? ¿Y en silver?

Corré el pipeline de nuevo y refrescá la pestaña 0.

<details>
<summary>Qué pasó y por qué</summary>

| | 1 corrida | 2 corridas |
|---|---|---|
| Filas en bronze | 50.000 | **100.000** |
| `stream_id` distintos en bronze | 50.000 | 50.000 |
| Filas en silver / gold | 50.000 | 50.000 |

**Bronze es *append-only*.** Guarda todo lo que llegó, cada vez que llegó, con un timestamp `_loaded_at`. Es el registro de auditoría: si mañana alguien pregunta "¿qué nos mandaron el martes?", la respuesta está en bronze. Mirá la tabla **"Un mismo stream (stream_id = 1) en cada capa"**: el stream 1 está dos veces en bronze (una por carga) y una sola vez en silver y gold.

**Silver deduplica.** `stg_streams.sql` numera las cargas de cada `stream_id` y se queda con la más reciente:

```sql
ROW_NUMBER() OVER (PARTITION BY stream_id ORDER BY _loaded_at DESC) AS rn
...
WHERE rn = 1
```

Esto va a importar más adelante: para darte cuenta de que "faltan filas" entre bronze y silver, primero tenés que saber cuál es la diferencia **normal**.

</details>

### Qué es Elementary, y por qué corriste dos veces

**Elementary** es una herramienta open source de **observabilidad de datos** para proyectos dbt. Tiene dos partes:

1. **Un paquete de dbt** (lo ves en `dbt/packages.yml`). Agrega tests nuevos que se declaran en el `schema.yml` como cualquier otro (`elementary.column_anomalies`, `elementary.freshness_anomalies`…). Además, en cada `dbt build` guarda en el schema `elementary` del warehouse:
   - el resultado de **cada test** en cada corrida (`elementary_test_results`);
   - **métricas** de tablas y columnas monitoreadas: promedio, cantidad de nulos, freshness (`data_monitoring_metrics`);
   - metadata de cada corrida de dbt (`dbt_invocations`).
2. **Un CLI (`edr`)** que lee esas tablas y arma un reporte HTML (lo usás en el [Paso 7](#paso-7--el-reporte-de-elementary)).

**La diferencia con un test de dbt.** Un test de dbt es una **regla fija**: "`ingresos_usd` no puede ser negativo". Funciona desde la primera corrida. Un test de anomalías de Elementary **no tiene regla**: compara la medición de hoy contra el **historial** de mediciones anteriores y avisa si se sale de lo normal.

**Por qué dos corridas.** Elementary no guarda filas: guarda **una foto de métricas por corrida**. Los tests de anomalías de este proyecto están configurados con `min_training_set_size: 2`, o sea que necesitan al menos 2 fotos previas para saber qué es "lo normal". Con una sola corrida no hay contra qué comparar.

En la pestaña 0 mirá:
- el gráfico **"Historial de Elementary: average de ingresos_usd en silver"**: 2 puntos, uno por corrida;
- **"Métricas que guarda Elementary"**: cada métrica con 2 puntos de historial;
- **"Corridas de dbt registradas por Elementary"**: 4, porque cada corrida del pipeline hace dos `dbt build` (uno para silver + dimensiones y otro para `fact_streams`).

Ojo con un detalle: las dos fotos valen **exactamente lo mismo**, porque son los mismos datos. El historial no tiene ninguna variación, así que el monitor queda muy sensible: cualquier cambio le va a parecer una anomalía. En un sistema real el historial son semanas de datos con variación natural.

---

## Paso 4 — Los tests que ya existen

Abrí `dbt/models/silver/schema.yml`. Vas a ver cosas como:

```yaml
- name: stream_id
  tests: [unique, not_null]
```

Eso ya es data quality. Los tests genéricos de dbt cubren varias **dimensiones de calidad**:

| Test dbt | Dimensión | Pregunta |
|---|---|---|
| `not_null` | Completeness | ¿Falta algún valor obligatorio? |
| `unique` | Uniqueness | ¿Hay duplicados? |
| `accepted_values` | Validity | ¿El valor está dentro de los permitidos? |
| `relationships` | Integrity | ¿La clave foránea apunta a algo que existe? |

Y en `dbt/tests/` hay **tests singulares**: un test de dbt es simplemente una query que busca filas malas. **Si devuelve filas, el test falla.** Por ejemplo `assert_stg_streams_valid_pais.sql`:

```sql
SELECT stream_id FROM {{ ref('stg_streams') }}
WHERE pais_usuario IS NOT NULL
  AND pais_usuario !~ '^[A-Z]{2}$'
```

Es un **contrato**: declara que `pais_usuario` tiene que ser un código ISO de 2 letras mayúsculas (`AR`, `US`, `BR`…).

Y `assert_fact_streams_ingreso_por_reproduccion_razonable.sql` falla si algún stream paga más de **$0.05 por reproducción**. Ese número no sale de la nada: el máximo real del dataset es $0.012/play (Tidal). Lo podés ver en Metabase, pestaña **3 · Ingreso sospechoso**, card "Máximo USD/play de los streams normales". Es un test que **conoce el negocio**.

**Un detalle importante del pipeline:** Dagster corre dbt en dos pasos, primero silver + dimensiones (`dbt_dim_assets`) y después `fact_streams` (`dbt_fact_assets`). Si un test del primer paso falla, **el segundo no corre**. Es una protección: un dato malo detectado en silver no llega a gold.

---

## Paso 5 — Cómo vas a trabajar cada escenario

Vas a romper los datos de seis maneras. Para cada una, el ciclo es siempre el mismo:

```bash
dq --scenario <nombre>     # 1. inyectar datos malos en bronze
# 2. Dagster → Materialize all
# 3. mirar qué falló (Dagster) y qué hay en cada capa (Metabase)
dq --cleanup               # 4. limpiar
# 5. Dagster → Materialize all → tiene que volver a verde
```

**No te saltees el paso 5.** Si no volvés a verde, el escenario siguiente arrastra los errores del anterior.

**Cómo ver qué test falló en Dagster:** entrá a *Runs* (http://localhost:3000/runs), abrí el último run, buscá el step en rojo y mirá sus logs. La salida de dbt tiene líneas como `FAIL 2 assert_stg_streams_valid_pais`: el número es la cantidad de filas que devolvió el test.

**Cómo ver los datos en Metabase:** cada escenario tiene su pestaña en el dashboard, con contadores por capa y las **filas crudas** tal como están en bronze, con columnas `llego_a_silver` / `llego_a_gold`. Los textos aparecen entre comillas (`'  '`) para que se vean los espacios. Refrescá el dashboard después de cada corrida.

> ⚠️ **Hacé el escenario 6 al final.** Deja un "recuerdo" en Elementary que no se borra con `--cleanup` (lo vas a entender cuando llegues).

---

## Paso 6 — Los escenarios

### Escenario 1 — País inválido

```bash
dq --scenario pais_invalido
```

Inyecta **7 streams** con códigos de país malformados: `'ARG'`, `'ar'`, `'USA'`, `'00'`, `'NONE'`, `'  '` (dos espacios) y `'XX1'`. Todo lo demás es válido.

#### 🤔 Predicción

El test `assert_stg_streams_valid_pais` busca países que no sean exactamente 2 letras mayúsculas. Hay 7 países rotos. **¿Cuántas filas va a reportar el test?**

Corré el pipeline. Mirá el run en Dagster y la pestaña **1 · País inválido** en Metabase.

<details>
<summary>Qué pasó y por qué</summary>

El test falla, pero **con 2 filas, no con 7**.

Mirá la tabla "País: bronze vs silver" en Metabase. La clave está en cómo `stg_streams.sql` limpia el país:

```sql
UPPER(TRIM(pais_usuario))::varchar(2) AS pais_usuario
```

En Postgres, convertir explícitamente a `varchar(2)` **recorta el texto sin avisar**:

| Bronze | Silver | ¿Falla el test? |
|---|---|---|
| `'ARG'` | `'AR'` | no |
| `'ar'` | `'AR'` | no |
| `'USA'` | `'US'` | no |
| `'NONE'` | `'NO'` (¡Noruega!) | no |
| `'XX1'` | `'XX'` | no |
| `'00'` | `'00'` | **sí** |
| `'  '` | `''` | **sí** |

El test hizo exactamente lo que dice: verificó que silver tenga 2 letras mayúsculas, y silver las tiene. El problema es que **la transformación corrompió el dato antes de que el test lo viera**. "NONE" se convirtió en Noruega y "USA" en un código que parece válido.

Este es un **dato silencioso**: un error que no rompe ningún test. Testear la salida de una transformación no alcanza si la transformación misma altera el dato.

Fijate también en Dagster: el step `dbt_fact_assets` **no corrió**. El test falló en silver y Dagster frenó el paso a gold.

</details>

```bash
dq --cleanup
# Materialize all → verde
```

---

### Escenario 2 — Null en un campo obligatorio

```bash
dq --scenario null_en_cancion
```

Inyecta **5 streams con `cancion_id = NULL`**. El resto de los campos es válido.

#### 🤔 Predicción

Mirá `stg_streams.sql`: ¿filtra los `cancion_id` nulos? Y en `fact_streams.sql`, ¿qué pasa con un stream sin canción cuando se hace el `JOIN` con `dim_cancion`? ¿Dónde conviene testear: en silver o en gold?

Corré el pipeline. Mirá la pestaña **2 · cancion_id NULL** y, en **Resumen**, la tabla "Valores nulos por columna y capa".

<details>
<summary>Qué pasó y por qué</summary>

Falla `not_null_stg_streams_cancion_id` con **5 filas**.

- Bronze acepta todo, así que las 5 filas entran.
- `stg_streams` no filtra por `cancion_id`, así que llegan a silver con NULL y el test de silver las detecta.
- Si el pipeline siguiera, en gold **desaparecerían**: el `JOIN` con `dim_cancion` nunca matchea un NULL, así que esas filas se pierden sin error.

Si solo testearas gold, **nunca verías este problema**: en gold no hay nulos porque las filas directamente no están. Por eso conviene testear temprano, en la capa donde el problema todavía es visible.

</details>

```bash
dq --cleanup
# Materialize all → verde
```

---

### Escenario 3 — Una regla de negocio

```bash
dq --scenario ingreso_sospechoso
```

Inyecta **10 streams con 100 reproducciones y $1.000 de ingresos**: $10 por reproducción. El máximo real es $0.012.

#### 🤔 Predicción

Estas filas no tienen nulos, no están duplicadas y los ingresos no son negativos. ¿Qué test las puede atrapar? ¿En qué capa?

Corré el pipeline. Mirá la pestaña **3 · Ingreso sospechoso**.

<details>
<summary>Qué pasó y por qué</summary>

Falla `assert_fact_streams_ingreso_por_reproduccion_razonable` con **10 filas**.

Es el único escenario donde el dato malo **llega hasta gold**: pasa todos los filtros de silver y ningún test genérico lo detecta. Solo lo atrapa un test que **conoce el dominio**, es decir, que sabe que ninguna plataforma paga $10 por reproducción. En Metabase vas a ver la columna `veces_el_maximo_real` en 833.

Esta es la diferencia entre **tests genéricos** (`not_null`, `unique`: sirven para cualquier tabla) y **tests de negocio** (necesitan que alguien que entiende los datos defina qué es razonable).

</details>

```bash
dq --cleanup
# Materialize all → verde
```

> 💡 Mirá la salida del `--cleanup`: además de bronze, borra filas de `gold.fact_streams`. ¿Por qué hace falta? `fact_streams` es un modelo **incremental**: en cada corrida solo procesa la fecha de ayer y no vuelve a mirar lo que ya cargó. Re-correr el pipeline no borra filas que ya llegaron a gold. Corregir el origen no corrige el destino si la carga es incremental.

---

### Escenario 4 — Un error que se propaga

```bash
dq --scenario plataforma_nueva
```

Inyecta una plataforma nueva, **"TikTok Music"** (`plataforma_id = 9`), en `bronze.plataformas_raw`, más 8 streams que la usan.

#### 🤔 Predicción

`dim_plataforma` tiene un test `accepted_values` con la lista de plataformas conocidas. ¿Hasta qué capa llega TikTok Music? ¿Y los 8 streams?

Corré el pipeline. Mirá la pestaña **4 · Plataforma nueva**, tabla "Plataformas: recorrido bronze → silver → gold".

<details>
<summary>Qué pasó y por qué</summary>

Falla `accepted_values_dim_plataforma_nombre…` con **1 fila**.

TikTok Music viajó por todas las capas: bronze → `stg_plataformas` → `dim_plataforma`. En Metabase aparece con `en_catalogo = false` pero `llego_a_silver = true` y `llego_a_gold = true`.

Un error en una tabla de catálogo chiquita (5 filas) llegó hasta la capa que usan los analistas. Sin el test, nadie se daría cuenta hasta que alguien pregunte "¿qué es TikTok Music en el reporte?".

Los 8 streams, en cambio, **no llegaron a la fact** (`streams_en_gold = 0`): como el test falló en una dimensión, Dagster no corrió `fact_streams`. El test funcionó como una barrera.

</details>

```bash
dq --cleanup
# Materialize all → verde
```

---

### Escenario 5 — El dato silencioso

```bash
dq --scenario silencioso
```

Inyecta **16 streams inválidos**: 8 con ingresos negativos (`-50`) y 8 con 0 reproducciones.

#### 🤔 Predicción

Mirá el final de `stg_streams.sql`:

```sql
WHERE rn = 1
  AND reproducciones > 0
  AND ingresos_usd   >= 0
```

¿Qué test va a fallar?

Corré el pipeline.

<details>
<summary>Qué pasó y por qué</summary>

**Ningún test falla. El pipeline queda en verde.**

Silver filtra las 16 filas con el `WHERE` y **desaparecen sin dejar rastro**. Los tests de silver y gold no las ven porque ya no existen. Nadie se entera de que llegaron datos inválidos.

Comprobalo:

```bash
dq --counts
```

```
Conteos de streams para fecha AAAA-MM-DD:
   bronze.streams_raw  :     16  (incluye 16 inyectadas)
   silver.stg_streams  :      0
   gold.fact_streams   :      0

   Diferencia bronze→silver: 16 filas desaparecieron en silver.
```

En Metabase, pestaña **5 · Silencioso**: "Filas inválidas en bronze = 16", "en silver = 0", las 16 filas con `llego_a_silver = false`, y la tabla "Conteos por fecha y capa" con la diferencia en la fecha de ayer.

Es el segundo dato silencioso que ves. En el escenario 1 la transformación **cambió** el dato; acá lo **borró**. Silver hizo exactamente lo que le pedimos, pero nadie nos avisó. **Los tests declarativos sobre la salida no alcanzan**: hace falta comparar entre capas, o monitorear. Para eso existe la **observabilidad de datos**.

</details>

```bash
dq --cleanup
# Materialize all → verde
```

---

### Escenario 6 — Una anomalía estadística (hacelo último)

> Necesitás al menos 2 corridas limpias previas (ya las tenés desde el Paso 3).

```bash
dq --scenario column_anomaly
```

Inyecta **5.000 streams** (10% del volumen) con 50.000 reproducciones y $2.400 de ingresos cada uno: **$0.048 por reproducción**, justo debajo del límite de $0.05 del test de negocio.

#### 🤔 Predicción

Cada fila individual es válida: no hay nulos, no hay negativos, y el ratio está debajo del límite. ¿Algún test va a fallar?

Corré el pipeline. Mirá la pestaña **6 · Column anomaly**.

<details>
<summary>Qué pasó y por qué</summary>

Ningún test de dbt falla, pero **falla el test de Elementary** `elementary_column_anomalies_stg_streams_…_ingresos_usd`.

En Metabase:
- **"Average ingresos_usd en silver — ahora"**: ~$327;
- **"Average histórico según Elementary"**: ~$120;
- el gráfico del historial: plano en ~$120 y con un salto en la última corrida;
- **"Resultados de los tests de anomalías"**: lo que reportó Elementary ("the last average value is 327… The average for this metric is 120…").

El promedio de ingresos casi se triplicó en una sola carga. Cada fila es válida por separado, pero el conjunto no: es como un sistema de pagos que empezó a atribuir de más a miles de eventos. **Ninguna regla fija lo detecta. Lo detecta un monitor que conoce el historial.**

Como el test es de silver, Dagster tampoco corrió `fact_streams`: la anomalía quedó frenada antes de gold.

</details>

```bash
dq --cleanup
# Materialize all
```

#### 🤔 Y ahora…

Después del cleanup, volvé a correr el pipeline. **¿El test de Elementary vuelve a verde?**

<details>
<summary>Qué pasó y por qué</summary>

**No. Sigue fallando.** Ahora el promedio "volvió" a ~$120, pero el historial incluye el pico de $327. Comparado con ese historial, el valor normal ahora parece anómalo. Lo ves en el gráfico de la pestaña 6.

Un monitor estadístico **tiene memoria**: después de un incidente, su baseline queda contaminado. En sistemas reales se marca el run anómalo para excluirlo, o se espera a que salga de la ventana de entrenamiento. Por eso este escenario va último.

Para volver a cero, reseteá todo (ver [Empezar de nuevo](#empezar-de-nuevo)).

</details>

---

## Paso 7 — El reporte de Elementary

Generá el reporte HTML con el CLI de Elementary (no se actualiza solo: hay que volver a correr este comando cada vez que quieras verlo actualizado):

```bash
docker compose exec dagster bash -c "rm -f /workspace/dbt/edr_target/elementary_report.html && edr report --project-dir /workspace/dbt --profiles-dir /workspace/dbt --file-path /workspace/dbt/edr_target/elementary_report.html"
```

Abrí http://localhost:8083/elementary_report.html y recorré:

- **Test Results**: el resultado de todos los tests. Ahí están los fallos de los escenarios.
- Dentro de *Test Results*, abrí el test `column_anomalies` de `ingresos_usd` en `stg_streams`: muestra el gráfico de la métrica `average` a lo largo de las corridas, con el pico del escenario 6.
- **Lineage**: el grafo de modelos, con el estado de sus tests.

Compará con la pestaña **7 · Elementary** del dashboard, que lee las mismas tablas: "Métricas que guarda Elementary" e "Historial de resultados de tests".

Mirá en `dbt/models/silver/schema.yml` cómo se declara el monitor:

```yaml
- name: ingresos_usd
  tests:
    - elementary.column_anomalies:
        column_anomalies: [null_count, average, min_value, max_value]
        min_training_set_size: 2
```

> Detalle: aunque el YAML pide `min_value` y `max_value`, en esta versión Elementary solo registra `average` y `null_count` para estas columnas. Lo podés comprobar en la tabla "Métricas que guarda Elementary".

---

## Paso 8 — Lineage con dbt docs

**Lineage** es poder responder "¿de dónde viene este dato?" y "¿qué se rompe si cambio esto?".

Primero regenerá la documentación con el warehouse ya cargado (cuando arrancó, las tablas todavía no existían):

```bash
docker compose restart dbt-docs
```

Abrí http://localhost:8082 y buscá `fact_streams`. Abajo a la derecha está el botón para ver el **grafo de lineage**.

#### 🤔 Ejercicios

1. Si el equipo que manda los datos cambia el tipo de `ingresos_usd` en `streams_raw`, ¿qué modelos se pueden romper?
2. ¿De qué tabla de bronze viene `sk_artista` de `fact_streams`?

<details>
<summary>Respuestas</summary>

1. Desde `streams_raw`, mirá sus descendientes: `stg_streams` → `fact_streams`.
2. Hacia arriba desde `fact_streams`: `dim_artista` ← `stg_artistas` ← `artistas_raw`.

Esto es lineage **a nivel de modelo** (tabla). Sabés que `fact_streams` depende de `streams_raw`, pero no qué columna de `streams_raw` termina en cada campo. Para eso hace falta lineage **a nivel de columna**, que es lo que agrega DataHub.

</details>

---

## Paso 9 (opcional) — Lineage por columna con DataHub

DataHub es un **catálogo de datos**: un buscador de todas las tablas de una organización, con su lineage por columna, sus dueños, sus tags (como PII) y el estado de sus tests. No mueve datos: guarda **metadata** sobre ellos.

Es pesado (unos 10 contenedores, ~8 GB de RAM), por eso no está en el `docker-compose.yml`. Si tu máquina lo aguanta:

```bash
pip install 'acryl-datahub[dbt-postgres]'

# puertos remapeados para no chocar con otros servicios
export DATAHUB_MAPPED_GMS_PORT=8090
export DATAHUB_MAPPED_SCHEMA_REGISTRY_PORT=8091
datahub docker quickstart          # UI en http://localhost:9002 (datahub / datahub)

bash datahub/ingest.sh             # manda la metadata de dbt a DataHub
```

`ingest.sh` corre `dbt docs generate` desde tu máquina (necesita `dbt-postgres` instalado y se conecta a `localhost:5433`) y después `datahub ingest -c datahub/recipe.yml`. Mirá el `recipe.yml`: DataHub **no se conecta a nada nuevo**, lee los archivos que dbt ya genera (`manifest.json`, `catalog.json`, `run_results.json`).

En http://localhost:9002 buscá `fact_streams` y mirá las pestañas **Lineage** (flechas columna a columna), **Schema** (descripciones del `schema.yml`) y **Properties** (`owner`).

Para borrarlo: `datahub docker nuke`.

---

## Paso 10 — Governance en el código

Governance es saber **quién es responsable** de cada dato, **qué garantías** da y **qué datos son sensibles**. En este proyecto todo eso está declarado en el código, al lado de los modelos.

**Dueños.** En `dbt/models/gold/schema.yml`:

```yaml
- name: fact_streams
  meta:
    owner: "equipo-analytics"
    team:  "analytics"
```

Al estar en el repositorio, el dueño viaja con el modelo: lo leen dbt docs, DataHub y cualquier herramienta de catálogo.

**Contrato de frescura.** En `dbt/models/sources.yml`:

```yaml
freshness:
  warn_after:  {count: 24, period: hour}
  error_after: {count: 48, period: hour}
```

Es una promesa a quien consume `bronze`: los datos tienen menos de 24 horas. Probalo:

```bash
docker compose exec dagster dbt source freshness --profiles-dir /workspace/dbt --project-dir /workspace/dbt
```

(También corre en cada pipeline: es el asset `source_freshness_check`.)

**Datos sensibles (PII).** En los `schema.yml`:

```yaml
- name: pais_usuario
  meta:
    pii: false
    sensitivity: "low"
```

`pais_usuario` no es PII porque es nivel país, no identifica a una persona. Pero si hubiera un `email`, marcarlo `pii: true` haría que DataHub lo muestre como sensible, y alguien de seguridad podría pedir "todas las columnas con PII del warehouse" en segundos.

---

## Resumen: los pilares de la observabilidad de datos

| Pilar | Pregunta | Dónde lo viste |
|---|---|---|
| **Freshness** | ¿Cuándo se actualizó por última vez? | `dbt source freshness`, Elementary |
| **Volume** | ¿Llegaron todos los datos? | Conteos entre capas (escenario 5, pestaña 0) |
| **Schema** | ¿Cambió la estructura? | Elementary, DataHub |
| **Distribution** | ¿Cambiaron los valores? | Elementary `column_anomalies` (escenario 6) |
| **Lineage** | ¿De dónde viene este número? | dbt docs, DataHub |
| **Governance** | ¿Quién es dueño? ¿Hay PII? | `meta` en `schema.yml`, DataHub |

Y el ecosistema de herramientas:

| Herramienta | Open source | Qué hace |
|---|---|---|
| dbt tests | ✅ | Calidad declarativa en cada corrida |
| Elementary | ✅ | Observabilidad histórica y detección de anomalías |
| dbt docs | ✅ | Lineage a nivel de modelo |
| DataHub | ✅ | Catálogo: lineage por columna, dueños, PII |
| Atlan | ❌ (SaaS) | Catálogo comercial, sin operarlo vos |
| Unity Catalog | ❌ (Databricks) | Governance nativo de Databricks |

Más allá de la herramienta, el activo que perdura es la **metadata declarada en los `schema.yml`**: tests, dueños, descripciones y tags. Esa información se puede llevar de una herramienta a otra.

---

## Desafíos

Para cerrar, dos ejercicios para resolver los datos silenciosos que encontraste. Cuando termines, dejá el proyecto como estaba: borrá el test que creaste (`rm dbt/tests/assert_bronze_silver_sin_perdidas.sql`) y deshacé el cambio en silver (`git checkout -- dbt/models/silver/stg_streams.sql`).

### Desafío 1 — Detectar el escenario 5 sin cambiar el pipeline

Escribí un test singular de dbt (un archivo `.sql` en `dbt/tests/`) que falle si hay `stream_id` en bronze que no llegaron a silver. Probalo con el escenario `silencioso`.

<details>
<summary>Pista</summary>

Contá los `stream_id` **distintos** de `{{ source('bronze', 'streams_raw') }}` (acordate de que bronze tiene duplicados por diseño) y compará contra `COUNT(*)` de `{{ ref('stg_streams') }}`. El test tiene que devolver una fila solo si la diferencia es mayor a 0.

</details>

<details>
<summary>Una solución</summary>

`dbt/tests/assert_bronze_silver_sin_perdidas.sql`:

```sql
-- Falla si hay stream_id en bronze que no llegaron a silver.
WITH bronze AS (
    SELECT COUNT(DISTINCT stream_id) AS n
    FROM {{ source('bronze', 'streams_raw') }}
    WHERE stream_id IS NOT NULL
),
silver AS (
    SELECT COUNT(*) AS n FROM {{ ref('stg_streams') }}
)
SELECT bronze.n AS stream_ids_en_bronze,
       silver.n AS filas_en_silver,
       bronze.n - silver.n AS perdidas
FROM bronze, silver
WHERE bronze.n - silver.n > 0
```

Probalo:

```bash
docker compose exec dagster dbt test --select assert_bronze_silver_sin_perdidas --profiles-dir /workspace/dbt --project-dir /workspace/dbt
dq --scenario silencioso
docker compose exec dagster dbt build --select stg_streams --profiles-dir /workspace/dbt --project-dir /workspace/dbt
docker compose exec dagster dbt test --select assert_bronze_silver_sin_perdidas --profiles-dir /workspace/dbt --project-dir /workspace/dbt
dq --cleanup
```

Sin datos inyectados pasa; con el escenario silencioso falla. Este tipo de test es un **contrato entre capas**: herramientas como Soda Core o Great Expectations están pensadas para escribir muchos de estos.

Para pensar: ¿qué pasaría si silver filtrara filas **a propósito** (por ejemplo, datos de prueba)? En ese caso convendría tolerar un umbral, o mandar las filas filtradas a una tabla de "cuarentena" y testear esa tabla.

</details>

### Desafío 2 — Que el escenario 1 deje de ser silencioso

Modificá `dbt/models/silver/stg_streams.sql` para que un país mal formado **no se transforme en uno válido**, y comprobá que el test `assert_stg_streams_valid_pais` lo detecta.

<details>
<summary>Una solución</summary>

Sacar el cast a `varchar(2)`, que es el que recorta:

```sql
UPPER(TRIM(pais_usuario))::varchar AS pais_usuario
```

Con el escenario `pais_invalido` el test pasa a fallar con **6 filas de 7**. La única que pasa es `'ar'`, que se convierte en `'AR'`: eso es una normalización legítima (pasar a mayúsculas no cambia el significado), a diferencia de recortar `'NONE'` a `'NO'`.

Otra opción sería dejar el valor en NULL si no cumple el formato. ¡Pero ojo! El test ignora los NULL (`WHERE pais_usuario IS NOT NULL`), así que el problema volvería a ser silencioso. Si elegís ese camino, tendrías que mandar las filas a una tabla de cuarentena o agregar un test sobre bronze.

</details>

---

## Empezar de nuevo

Para volver todo a cero (borra el warehouse, el historial de Elementary y Metabase):

```bash
docker compose down -v
docker compose up --build -d
```

Después corré el pipeline **dos veces** (Paso 3) antes de volver a hacer los escenarios.

Para apagar todo sin borrar datos: `docker compose down` (sin `-v`).

---

## Problemas comunes

| Síntoma | Qué hacer |
|---|---|
| `Bind for 0.0.0.0:XXXX failed: port is already allocated` | Otro programa usa ese puerto. Cambiá el número de la izquierda en la línea `ports` de ese servicio en `docker-compose.yml` (por ejemplo `"5434:5432"`) y volvé a levantar. |
| Las cards de Metabase dicen "relation does not exist" | Todavía no corriste el pipeline. *Materialize all* en Dagster. |
| No encuentro el dashboard en Metabase | Buscá "Data Quality" en el buscador de arriba. Si no está: `docker compose up -d --build metabase-init`. |
| Un escenario muestra errores de otro escenario | Faltó `dq --cleanup` + volver a correr el pipeline. |
| El test de Elementary sigue en rojo después del escenario 6 | Es esperado (leé la explicación del escenario 6). `docker compose down -v` para empezar de cero. |
| dbt docs no muestra columnas ni tipos | `docker compose restart dbt-docs`. |
| El reporte de Elementary no muestra lo último | No se actualiza solo: volvé a correr el comando `edr report` del Paso 7. |
| `dq: command not found` | El alias vale solo para la terminal donde lo definiste. Volvé a correr la línea `alias dq=...`. |
