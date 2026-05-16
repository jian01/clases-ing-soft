"""
Configuracion inicial automatica de Metabase.
Crea el usuario admin, conecta la base de datos y genera los dashboards de ejemplo.
Se ejecuta una sola vez; si Metabase ya tiene setup, sale sin hacer nada.
"""
import os
import sys
import time

import requests

MB_HOST = os.environ["MB_HOST"]
MB_ADMIN_EMAIL = os.environ["MB_ADMIN_EMAIL"]
MB_ADMIN_PASSWORD = os.environ["MB_ADMIN_PASSWORD"]
MB_ADMIN_FIRST_NAME = os.environ.get("MB_ADMIN_FIRST_NAME", "Admin")
MB_ADMIN_LAST_NAME = os.environ.get("MB_ADMIN_LAST_NAME", "Demo")
MB_SITE_NAME = os.environ.get("MB_SITE_NAME", "DWH Streaming")
PG_HOST = os.environ["PG_HOST"]
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_DB = os.environ["PG_DB"]
PG_USER = os.environ["PG_USER"]
PG_PASSWORD = os.environ["PG_PASSWORD"]

QUERY_STREAMS_POR_MES = (
    "SELECT DATE_TRUNC('month', fecha) as mes, "
    "p.nombre as plataforma, "
    "SUM(reproducciones) as total_reproducciones, "
    "SUM(ingresos_usd) as total_ingresos "
    "FROM gold.fact_streams f "
    "JOIN gold.dim_plataforma p ON f.sk_plataforma = p.sk_plataforma "
    "GROUP BY 1, 2 ORDER BY 1, 2"
)

QUERY_TOP_ARTISTAS = (
    "SELECT a.nombre as artista, a.genero, "
    "SUM(f.ingresos_usd) as total_ingresos, "
    "SUM(f.reproducciones) as total_reproducciones "
    "FROM gold.fact_streams f "
    "JOIN gold.dim_cancion c ON f.sk_cancion = c.sk_cancion "
    "JOIN gold.dim_artista a ON f.sk_artista = a.sk_artista "
    "WHERE a.is_current = TRUE "
    "GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10"
)


def wait_for_metabase():
    print("Esperando que Metabase este disponible...")
    for intento in range(60):
        try:
            r = requests.get(f"{MB_HOST}/api/health", timeout=5)
            if r.status_code == 200 and r.json().get("status") == "ok":
                print("Metabase disponible.")
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(5)
        print(f"  intento {intento + 1}/60...")
    print("ERROR: Metabase no respondio en tiempo.")
    sys.exit(1)


def get_setup_token():
    r = requests.get(f"{MB_HOST}/api/session/properties", timeout=10)
    r.raise_for_status()
    token = r.json().get("setup-token")
    return token


def setup_metabase(setup_token):
    payload = {
        "token": setup_token,
        "user": {
            "email": MB_ADMIN_EMAIL,
            "password": MB_ADMIN_PASSWORD,
            "first_name": MB_ADMIN_FIRST_NAME,
            "last_name": MB_ADMIN_LAST_NAME,
            "site_name": MB_SITE_NAME,
        },
        "database": {
            "name": "DWH Warehouse",
            "engine": "postgres",
            "details": {
                "host": PG_HOST,
                "port": PG_PORT,
                "dbname": PG_DB,
                "user": PG_USER,
                "password": PG_PASSWORD,
                "schema-filter-patterns": "gold",
            },
            "auto_run_queries": True,
            "is_full_sync": True,
        },
        "prefs": {
            "allow_tracking": False,
            "site_name": MB_SITE_NAME,
        },
    }
    r = requests.post(f"{MB_HOST}/api/setup", json=payload, timeout=30)
    if r.status_code not in (200, 201):
        print(f"ERROR en setup: {r.status_code} {r.text}")
        sys.exit(1)
    session_token = r.json().get("id")
    print("Setup de Metabase completado.")
    return session_token


def get_database_id(session_token):
    headers = {"X-Metabase-Session": session_token}
    # Esperamos hasta que la DB aparezca en la lista
    for _ in range(20):
        r = requests.get(f"{MB_HOST}/api/database", headers=headers, timeout=10)
        r.raise_for_status()
        databases = r.json().get("data", r.json() if isinstance(r.json(), list) else [])
        for db in databases:
            if db.get("name") == "DWH Warehouse":
                return db["id"]
        time.sleep(3)
    print("ERROR: no se encontro la base de datos 'DWH Warehouse' en Metabase.")
    sys.exit(1)


def create_card(session_token, db_id, name, query, display="line"):
    headers = {"X-Metabase-Session": session_token}
    payload = {
        "name": name,
        "display": display,
        "dataset_query": {
            "type": "native",
            "native": {"query": query},
            "database": db_id,
        },
        "result_metadata": [],
        "visualization_settings": {},
    }
    r = requests.post(f"{MB_HOST}/api/card", json=payload, headers=headers, timeout=30)
    if r.status_code not in (200, 202):
        print(f"AVISO: no se pudo crear la card '{name}': {r.status_code} {r.text}")
        return None
    card_id = r.json().get("id")
    print(f"Card '{name}' creada con id={card_id}.")
    return card_id


def create_dashboard(session_token, name, card_ids):
    headers = {"X-Metabase-Session": session_token}

    # Crear el dashboard vacio
    r = requests.post(
        f"{MB_HOST}/api/dashboard",
        json={"name": name},
        headers=headers,
        timeout=10,
    )
    if r.status_code not in (200, 202):
        print(f"AVISO: no se pudo crear el dashboard '{name}': {r.status_code}")
        return
    dashboard_id = r.json()["id"]

    # Agregar cada card al dashboard
    for idx, card_id in enumerate(card_ids):
        if card_id is None:
            continue
        r = requests.post(
            f"{MB_HOST}/api/dashboard/{dashboard_id}/cards",
            json={
                "cardId": card_id,
                "row": idx * 6,
                "col": 0,
                "size_x": 12,
                "size_y": 6,
            },
            headers=headers,
            timeout=10,
        )
        if r.status_code not in (200, 202):
            print(f"AVISO: no se pudo agregar card {card_id} al dashboard: {r.status_code}")

    print(f"Dashboard '{name}' creado con id={dashboard_id}.")


def main():
    wait_for_metabase()

    setup_token = get_setup_token()
    if not setup_token:
        print("Metabase ya esta configurado, saltando setup.")
        sys.exit(0)

    session_token = setup_metabase(setup_token)
    db_id = get_database_id(session_token)

    card1 = create_card(
        session_token,
        db_id,
        name="Streams por mes y plataforma",
        query=QUERY_STREAMS_POR_MES,
        display="line",
    )

    card2 = create_card(
        session_token,
        db_id,
        name="Top 10 artistas por ingresos",
        query=QUERY_TOP_ARTISTAS,
        display="bar",
    )

    create_dashboard(session_token, "Streams por mes y plataforma", [card1])
    create_dashboard(session_token, "Top 10 artistas por ingresos", [card2])

    print("Configuracion de Metabase finalizada.")


if __name__ == "__main__":
    main()
