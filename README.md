# DWH Streaming — Base para el TP de Integración de Datos (UDESA)

## 1. Qué es esto

Un Data Warehouse funcional levantable en local con Docker. Modela la ingesta y transformación de datos de streaming de música usando una **arquitectura Medallion** (bronze / silver / gold) con un **star schema** en la capa gold.

Está armado para servir como base del trabajo práctico de la materia. Vos arrancás desde acá y le agregás la API REST, los tests de CI y lo que pida el enunciado.

---

## 2. Arquitectura

```
Fuentes (CSV en data/)
      │
      ▼
Extracción (Python — extract/)
      │
      ▼
PostgreSQL — schema bronze (raw, append-only)
      │
      ▼  dbt build (silver + gold)
PostgreSQL — schema silver (limpio, tipado, deduplicado)
      │
      ▼
PostgreSQL — schema gold (star schema)
   ├── dim_artista  (SCD tipo 2)
   ├── dim_cancion
   ├── dim_plataforma
   ├── dim_tiempo
   └── fact_streams (incremental por fecha)
      │
      ├─► Metabase  (BI, http://localhost:3001)
      └─► Dagster   (gobierno + orq, http://localhost:3000)
               └── dispara y monitorea TODO el pipeline
                   (lineage, freshness, asset checks)
```

| Servicio    | Imagen / base              | Puerto | Rol                          |
|-------------|----------------------------|--------|------------------------------|
| PostgreSQL  | `postgres:16`              | 5432   | DWH (bronze / silver / gold) |
| Dagster     | Python 3.12 custom         | 3000   | Orquestación + gobierno      |
| Metabase    | `metabase/metabase:latest` | 3001   | BI para usuarios no técnicos |
| Adminer     | `adminer`                  | 8081   | UI SQL para debug            |

---

## 3. Cómo levantarlo

```bash
git clone <url-del-repo>
cd clases-ing-soft
docker compose up -d
```

Esperá ~60 segundos a que Dagster termine de arrancar, luego abrí http://localhost:3000 → **Assets** → **Materialize all**.

Eso corre la extracción, todos los modelos dbt y los tests de calidad. En una laptop modesta el pipeline completo tarda menos de 2 minutos.

---

## 4. Cómo accedo a cada cosa

| Herramienta        | URL                    | Credenciales                                                        |
|--------------------|------------------------|---------------------------------------------------------------------|
| Dagster (gobierno) | http://localhost:3000  | sin login                                                           |
| Metabase (BI)      | http://localhost:3001  | admin@demo.com / Admin1234!                                         |
| Adminer (SQL)      | http://localhost:8081  | servidor: `postgres` / user: `dwh` / pass: `dwh` / DB: `warehouse` |
| Postgres directo   | localhost:5432         | `psql -h localhost -U dwh -d warehouse`                             |

---

## 5. Cómo actualizo workflows

**Agregar un asset Python** (nueva extracción, nueva fuente):
1. Editá `dagster/dwh_pipeline/assets.py`.
2. `docker compose restart dagster` o clickeá "Reload definitions" en la UI.

**Agregar un modelo dbt** (nueva tabla en silver o gold):
1. Creá el `.sql` en `dbt/models/silver/` o `dbt/models/gold/`.
2. Agregá los tests en el `schema.yml` del subdirectorio.
3. `docker compose restart dagster` para regenerar el manifest.

---

## 6. Cómo reproceso una fecha

`fact_streams` es un modelo incremental con estrategia `delete+insert`. Para reprocesar un día específico pasá la variable `run_date` desde la UI de Dagster:

1. Assets → `fact_streams` → **Materialize**
2. En **Run config**, agregá:
```yaml
ops:
  dbt_fact_assets:
    config:
      run_date: "2025-06-15"
```

La operación es idempotente: podés correrla N veces para el mismo día y el resultado es siempre el mismo.

---

## 7. Modelo de datos

```
                   dim_tiempo
                   ──────────
                   sk_tiempo (PK)
                   fecha
                   anio, mes, dia, trimestre
                   nombre_mes, es_fin_de_semana

dim_artista        fact_streams        dim_cancion
───────────        ────────────        ───────────
sk_artista (PK) →  sk_artista  (FK)   sk_cancion (PK)
artista_id         sk_cancion  (FK) ← cancion_id
nombre             sk_plataforma(FK)  titulo, album
genero             sk_tiempo   (FK)   artista_id
pais               stream_id   (PK)   duracion_seg
anio_debut         fecha               anio_lanzamiento
valid_from         pais_usuario
valid_to           reproducciones
is_current         ingresos_usd
                        ↓
                   dim_plataforma
                   ──────────────
                   sk_plataforma (PK)
                   plataforma_id, nombre
```

| Modelo           | Tipo      | Descripción                                                          |
|------------------|-----------|----------------------------------------------------------------------|
| `fact_streams`   | Fact      | Evento de reproducción: quién escuchó qué, cuándo y en qué plataforma |
| `dim_artista`    | Dimensión | SCD tipo 2: rastrea cambios de género a lo largo del tiempo          |
| `dim_cancion`    | Dimensión | SCD tipo 1: versión actual de cada canción                           |
| `dim_plataforma` | Dimensión | Las 5 plataformas (Spotify, YouTube, Apple Music, Tidal, Amazon)     |
| `dim_tiempo`     | Dimensión | Calendario desde 2024-01-01 hasta hoy, generado en SQL               |

Para ver el lineage completo y la documentación de columnas:
```bash
docker exec -it clases-ing-soft-dagster-1 \
  bash -c "cd /workspace/dbt && dbt docs generate && dbt docs serve --port 8888"
```
Luego abrí http://localhost:8888.

---

## 8. Cómo regenero los datos fake

```bash
# Requiere: pip install faker pandas
python scripts/generate_fake_data.py
```

Genera los cuatro CSV en `data/` con seed 42 (resultado reproducible). Después corré "Materialize all" en Dagster para cargar los nuevos datos.

---

## 9. Troubleshooting

**Puerto ocupado**
Cambiá el puerto en `docker-compose.yml`, por ejemplo `ports: ["3100:3000"]`.

**Dagster tarda en arrancar la primera vez**
Normal — el entrypoint corre `dbt deps` y `dbt parse` antes de levantar el webserver. Esperá 60-90 segundos.

**Dagster: "manifest.json not found"**
```bash
docker compose restart dagster
```

**dbt falla por permisos**
Verificá que `POSTGRES_USER=dwh` esté en el environment del servicio `dagster` en `docker-compose.yml`.

**Empezar de cero**
```bash
docker compose down -v && docker compose up -d
```

**Metabase no muestra dashboards**
El servicio `metabase-init` tarda hasta 3 minutos. Esperá y actualizá la página.
