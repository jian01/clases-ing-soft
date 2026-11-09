"""
Configuracion automatica de Metabase.

Primera vez: crea el usuario admin, conecta la base de datos y genera los dashboards de ejemplo.
Siempre (idempotente): da permisos de lectura sobre bronze/silver/gold al usuario de Metabase
y (re)crea el dashboard "Data Quality — Anomalias" de la clase de data quality.
"""
import os
import sys
import time

import psycopg2
import requests

from dq_dashboard import TABS as DQ_TABS

DQ_DASHBOARD_NAME = "Data Quality — Anomalías"

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
# Usuario con permisos de GRANT (owner de los schemas). Opcional.
PG_ADMIN_USER = os.environ.get("PG_ADMIN_USER")
PG_ADMIN_PASSWORD = os.environ.get("PG_ADMIN_PASSWORD")

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


def _find_database(session_token):
    headers = {"X-Metabase-Session": session_token}
    r = requests.get(f"{MB_HOST}/api/database", headers=headers, timeout=10)
    r.raise_for_status()
    body = r.json()
    databases = body.get("data", []) if isinstance(body, dict) else body
    for db in databases:
        if db.get("name") == "DWH Warehouse":
            return db["id"]
    # Metabase configurado a mano: buscamos el Postgres del warehouse por dbname.
    for db in databases:
        details = db.get("details") or {}
        if db.get("engine") == "postgres" and details.get("dbname") == PG_DB:
            return db["id"]
    return None


def get_database_id(session_token):
    """Devuelve el id de la conexion al warehouse; la crea si no existe.

    Las versiones recientes de Metabase ignoran el bloque "database" de /api/setup,
    asi que la conexion se crea explicitamente con POST /api/database.
    """
    db_id = _find_database(session_token)
    if db_id:
        return db_id

    headers = {"X-Metabase-Session": session_token}
    payload = {
        "name": "DWH Warehouse",
        "engine": "postgres",
        "details": {
            "host": PG_HOST,
            "port": PG_PORT,
            "dbname": PG_DB,
            "user": PG_USER,
            "password": PG_PASSWORD,
        },
        "auto_run_queries": True,
        "is_full_sync": True,
    }
    r = requests.post(f"{MB_HOST}/api/database", json=payload, headers=headers, timeout=60)
    if r.status_code not in (200, 201):
        print(f"ERROR: no se pudo crear la conexion al warehouse: {r.status_code} {r.text}")
        sys.exit(1)
    print("Conexion 'DWH Warehouse' creada en Metabase.")
    return r.json()["id"]


def create_card(session_token, db_id, name, query, display="line", viz=None):
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
        "visualization_settings": viz or {},
    }
    r = requests.post(f"{MB_HOST}/api/card", json=payload, headers=headers, timeout=30)
    if r.status_code not in (200, 202):
        print(f"AVISO: no se pudo crear la card '{name}': {r.status_code} {r.text}")
        return None
    card_id = r.json().get("id")
    print(f"Card '{name}' creada con id={card_id}.")
    return card_id


def _text_dashcard(text):
    return {
        "card_id": None,
        "visualization_settings": {
            "virtual_card": {
                "name": None,
                "display": "text",
                "visualization_settings": {},
                "dataset_query": {},
                "archived": False,
            },
            "text": text,
            "dashcard.background": False,
        },
    }


def create_dashboard(session_token, name, card_ids=None, tabs=None):
    """Crea un dashboard. Usa PUT /api/dashboard/:id con dashcards (API actual de Metabase).

    card_ids: lista simple de cards, una debajo de otra (dashboards de ejemplo).
    tabs:     lista de (nombre_tab, [(card_id | texto, col, row, size_x, size_y), ...]).
    """
    headers = {"X-Metabase-Session": session_token}

    r = requests.post(f"{MB_HOST}/api/dashboard", json={"name": name}, headers=headers, timeout=10)
    if r.status_code not in (200, 202):
        print(f"AVISO: no se pudo crear el dashboard '{name}': {r.status_code} {r.text}")
        return None
    dashboard_id = r.json()["id"]

    if tabs is None:
        tabs = [(None, [(cid, 0, idx * 6, 24, 6) for idx, cid in enumerate(card_ids or []) if cid])]

    payload_tabs = []
    dashcards = []
    next_id = -1
    for tab_idx, (tab_name, items) in enumerate(tabs):
        tab_id = None
        if tab_name is not None:
            tab_id = -(tab_idx + 1)
            payload_tabs.append({"id": tab_id, "name": tab_name})
        for item, col, row, size_x, size_y in items:
            if item is None:
                continue
            dc = _text_dashcard(item) if isinstance(item, str) else {
                "card_id": item,
                "visualization_settings": {},
            }
            dc.update({
                "id": next_id,
                "dashboard_tab_id": tab_id,
                "col": col,
                "row": row,
                "size_x": size_x,
                "size_y": size_y,
                "parameter_mappings": [],
                "series": [],
            })
            dashcards.append(dc)
            next_id -= 1

    r = requests.put(
        f"{MB_HOST}/api/dashboard/{dashboard_id}",
        json={"dashcards": dashcards, "tabs": payload_tabs},
        headers=headers,
        timeout=30,
    )
    if r.status_code not in (200, 202):
        print(f"AVISO: no se pudieron agregar las cards al dashboard '{name}': {r.status_code} {r.text}")

    print(f"Dashboard '{name}' creado con id={dashboard_id}.")
    return dashboard_id


def login():
    r = requests.post(
        f"{MB_HOST}/api/session",
        json={"username": MB_ADMIN_EMAIL, "password": MB_ADMIN_PASSWORD},
        timeout=10,
    )
    if r.status_code != 200:
        print(f"ERROR: no se pudo loguear en Metabase como {MB_ADMIN_EMAIL}: {r.status_code} {r.text}")
        sys.exit(1)
    return r.json()["id"]


def grant_read_access():
    """Da SELECT sobre bronze/silver/gold al usuario de Metabase.

    postgres-init/init.sh solo corre con el volumen vacio, asi que lo repetimos aca
    para que funcione tambien sobre volumenes existentes. Es idempotente.
    """
    if not (PG_ADMIN_USER and PG_ADMIN_PASSWORD):
        print("PG_ADMIN_USER no definido: no se aplican grants (bronze/silver pueden no ser visibles).")
        return
    for intento in range(30):
        try:
            conn = psycopg2.connect(
                host=PG_HOST, port=PG_PORT, dbname=PG_DB,
                user=PG_ADMIN_USER, password=PG_ADMIN_PASSWORD,
            )
            break
        except psycopg2.OperationalError:
            time.sleep(2)
    else:
        print("AVISO: no se pudo conectar a Postgres para aplicar grants.")
        return

    conn.autocommit = True
    with conn.cursor() as cur:
        # elementary: tablas de historial de Elementary (dashboard de Data Quality, tabs 6 y 7)
        for schema in ("bronze", "silver", "gold", "elementary"):
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            cur.execute(f"GRANT USAGE ON SCHEMA {schema} TO {PG_USER}")
            cur.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {PG_USER}")
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE {PG_ADMIN_USER} IN SCHEMA {schema} "
                f"GRANT SELECT ON TABLES TO {PG_USER}"
            )
    conn.close()
    print(f"Grants de lectura sobre bronze/silver/gold/elementary aplicados a {PG_USER}.")


def remove_existing(session_token, dashboard_name, card_names):
    """Archiva el dashboard DQ y sus cards si ya existian, para recrearlos con las queries actuales."""
    headers = {"X-Metabase-Session": session_token}
    r = requests.get(f"{MB_HOST}/api/dashboard", headers=headers, timeout=10)
    r.raise_for_status()
    for d in r.json():
        if d.get("name") == dashboard_name and not d.get("archived"):
            requests.put(f"{MB_HOST}/api/dashboard/{d['id']}", json={"archived": True},
                         headers=headers, timeout=10)
            print(f"Dashboard previo '{dashboard_name}' (id={d['id']}) archivado.")
    r = requests.get(f"{MB_HOST}/api/card", headers=headers, timeout=30)
    r.raise_for_status()
    for c in r.json():
        if c.get("name") in card_names and not c.get("archived"):
            requests.put(f"{MB_HOST}/api/card/{c['id']}", json={"archived": True},
                         headers=headers, timeout=10)


def create_dq_dashboard(session_token, db_id):
    card_names = {item["name"] for _, rows in DQ_TABS for row in rows
                  for item, _, _ in row if isinstance(item, dict)}
    remove_existing(session_token, DQ_DASHBOARD_NAME, card_names)

    tabs = []
    for tab_name, rows in DQ_TABS:
        items = []
        y = 0
        for row in rows:
            x = 0
            height = 0
            for item, width, h in row:
                if isinstance(item, dict):
                    item = create_card(session_token, db_id, item["name"], item["query"],
                                       item["display"], item.get("viz"))
                items.append((item, x, y, width, h))
                x += width
                height = max(height, h)
            y += height
        tabs.append((tab_name, items))

    create_dashboard(session_token, DQ_DASHBOARD_NAME, tabs=tabs)


def main():
    wait_for_metabase()
    grant_read_access()

    setup_token = get_setup_token()
    if setup_token:
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
    else:
        print("Metabase ya esta configurado: login como admin.")
        session_token = login()
        db_id = get_database_id(session_token)

    create_dq_dashboard(session_token, db_id)
    print("Configuracion de Metabase finalizada.")


if __name__ == "__main__":
    main()
