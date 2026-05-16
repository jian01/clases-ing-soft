"""
Generador de datos falsos para el DWH de streaming musical.
Produce CSVs reproducibles en data/ usando seed fijo.
"""
import os
import random
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

SEED = 42
random.seed(SEED)
fake = Faker("es_AR")
fake.seed_instance(SEED)

OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── plataformas ───────────────────────────────────────────────────────────────

PLATAFORMAS = [
    (1, "Spotify"),
    (2, "YouTube"),
    (3, "Apple Music"),
    (4, "Tidal"),
    (5, "Amazon Music"),
]

# Tasa de ingreso por plataforma (USD por reproducción)
RATES = {
    1: 0.004,   # Spotify
    2: 0.001,   # YouTube
    3: 0.007,   # Apple Music
    4: 0.012,   # Tidal
    5: 0.005,   # Amazon Music
}

# Distribución realista de plataformas: ~60% entre Spotify y YouTube
PLATAFORMA_WEIGHTS = [35, 25, 15, 12, 13]

PAISES = ["AR", "BR", "US", "MX", "ES", "CO", "CL"]
GENEROS = ["Pop", "Rock", "Reggaeton", "Jazz", "Electronica", "Hip-Hop", "Cumbia", "Folk"]


def generate_plataformas():
    rows = [["plataforma_id", "nombre"]]
    for pid, nombre in PLATAFORMAS:
        rows.append([pid, nombre])
    return rows


# ── artistas ─────────────────────────────────────────────────────────────────

def generate_artistas():
    """
    ~200 artistas base + ~30 con una segunda versión (distinto genero, fecha posterior).
    Los duplicados permiten demostrar SCD tipo 2 en dim_artista.
    """
    rows = [["artista_id", "nombre", "genero", "pais", "anio_debut", "fecha_registro"]]

    base_count = 200
    scd_count = 30  # artistas que cambian de género

    for i in range(1, base_count + 1):
        nombre = fake.name()
        genero = random.choice(GENEROS)
        pais = random.choice(PAISES)
        anio_debut = random.randint(1990, 2023)
        # fecha_registro entre 2020-01-01 y 2023-12-31 (primera versión)
        dias_offset = random.randint(0, (date(2023, 12, 31) - date(2020, 1, 1)).days)
        fecha_registro = date(2020, 1, 1) + timedelta(days=dias_offset)
        rows.append([i, nombre, genero, pais, anio_debut, fecha_registro.isoformat()])

    # IDs 1..30 aparecen de nuevo con otro género y fecha_registro 1-2 años después
    for i in range(1, scd_count + 1):
        # Recuperar datos originales para no cambiar nombre/pais
        original = rows[i]  # fila 0 es el header
        nombre = original[1]
        pais = original[3]
        anio_debut = original[4]
        fecha_original = date.fromisoformat(str(original[5]))

        # Género diferente al original
        genero_nuevo = random.choice([g for g in GENEROS if g != original[2]])
        # Fecha 1-2 años después, pero no más allá de 2025-12-31
        dias_extra = random.randint(365, 730)
        fecha_nueva = fecha_original + timedelta(days=dias_extra)
        if fecha_nueva > date(2025, 12, 31):
            fecha_nueva = date(2025, 12, 31)

        rows.append([i, nombre, genero_nuevo, pais, anio_debut, fecha_nueva.isoformat()])

    return rows


# ── canciones ─────────────────────────────────────────────────────────────────

def generate_canciones(n=1000):
    rows = [["cancion_id", "titulo", "artista_id", "album", "duracion_seg", "anio_lanzamiento"]]
    for i in range(1, n + 1):
        titulo = " ".join(fake.words(nb=random.randint(1, 4))).title()
        artista_id = random.randint(1, 200)
        album = " ".join(fake.words(nb=random.randint(1, 3))).title()
        duracion_seg = random.randint(120, 420)
        anio_lanzamiento = random.randint(2000, 2025)
        rows.append([i, titulo, artista_id, album, duracion_seg, anio_lanzamiento])
    return rows


# ── streams ───────────────────────────────────────────────────────────────────

def generate_streams(canciones_count=1000, n=50000):
    fecha_inicio = date(2024, 1, 1)
    fecha_fin = date(2026, 3, 31)
    rango_dias = (fecha_fin - fecha_inicio).days

    rows = [["stream_id", "fecha", "cancion_id", "plataforma_id", "pais_usuario", "reproducciones", "ingresos_usd"]]

    for i in range(1, n + 1):
        dias_offset = random.randint(0, rango_dias)
        fecha = (fecha_inicio + timedelta(days=dias_offset)).isoformat()
        cancion_id = random.randint(1, canciones_count)
        plataforma_id = random.choices(
            [p[0] for p in PLATAFORMAS],
            weights=PLATAFORMA_WEIGHTS,
            k=1
        )[0]
        pais_usuario = random.choice(PAISES)
        reproducciones = random.randint(100, 50000)
        tasa = RATES[plataforma_id]
        ingresos_usd = round(reproducciones * tasa, 2)
        rows.append([i, fecha, cancion_id, plataforma_id, pais_usuario, reproducciones, ingresos_usd])

    return rows


# ── escritura de CSVs ─────────────────────────────────────────────────────────

def write_csv(filename: str, rows: list) -> int:
    path = OUTPUT_DIR / filename
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    # descontar encabezado
    return len(rows) - 1


def main():
    datos = {
        "plataformas.csv": generate_plataformas(),
        "artistas.csv": generate_artistas(),
        "canciones.csv": generate_canciones(1000),
        "streams.csv": generate_streams(1000, 50000),
    }

    print("Generando CSVs en:", OUTPUT_DIR)
    for nombre, rows in datos.items():
        n = write_csv(nombre, rows)
        print(f"  {nombre}: {n} filas")

    # Verificar que hay artistas con IDs duplicados (para SCD2)
    artistas_rows = datos["artistas.csv"][1:]  # sin header
    ids = [r[0] for r in artistas_rows]
    from collections import Counter
    duplicados = [aid for aid, cnt in Counter(ids).items() if cnt > 1]
    print(f"\nArtistas con mas de una version (SCD2): {len(duplicados)} IDs")
    print("IDs ejemplo:", sorted(duplicados)[:5])


if __name__ == "__main__":
    main()
