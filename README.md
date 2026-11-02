# Laboratorio de stress testing (Clase 7) con Docker

Levanta todo lo de la clase en tu computadora: dos APIs Flask, NGINX como balanceador y Locust.
Solo necesitás Docker Desktop instalado y abierto.

## Arrancar

En una terminal, dentro de esta carpeta:

    docker compose up --build

La primera vez tarda un par de minutos porque descarga las imágenes. Para frenar todo: Ctrl+C.

## Direcciones

| Qué | Dirección en el navegador | Host a usar en Locust |
|---|---|---|
| Locust (gráficos) | http://localhost:8089 | |
| API 1 directa | http://localhost:5001 | http://api1:5000 |
| API 2 directa | http://localhost:5002 | http://api2:5000 |
| NGINX (balanceador) | http://localhost:8080 | http://nginx |

Importante: en el campo Host de Locust se usan los nombres de la última columna, no "localhost",
porque Locust corre dentro de su propio contenedor.

## Equivalencia con las filminas

- Filminas 3 a 8 (instalar todo): reemplazadas por `docker compose up --build`.
- Filmina 9 (primeros tests): Host `http://api1:5000`, probar 10/2, 50/5 y 200/10.
  Para el experimento del sleep, editar `time.sleep(0.1)` en `app.py` y ejecutar
  `docker compose restart api1 api2`.
- Filminas 11 y 17 (dos tipos de usuario): copiar `ejemplos/2_dos_usuarios.py` sobre
  `locustfile.py` y ejecutar `docker compose restart locust`.
- Filminas 24 a 26 (e-commerce): igual con `ejemplos/3_ecommerce.py`. Los endpoints ya están en `app.py`.
- Filminas 27 a 31 (NGINX): Host `http://nginx`. Refrescando http://localhost:8080 se ve la alternancia
  entre API 1 y API 2. Para el experimento de apagar una API: `docker compose stop api2`
  (y `docker compose start api2` para volver).

Cada vez que edites `app.py` o `locustfile.py`, reiniciá el contenedor correspondiente;
no hace falta volver a construir nada.

## Diferencias con la versión en AWS

Las dos APIs usan el mismo `app.py` (en la clase se copia a `app2.py`); el nombre que muestran
lo pone la variable `API_NAME` del `docker-compose.yml`. Y como todo corre en tu máquina,
los números (por ejemplo el techo de requests por segundo) van a ser distintos a los de las
filminas, pero los comportamientos son los mismos.
