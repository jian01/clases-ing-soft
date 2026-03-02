# API de ejemplo con FastAPI

Una API simple construida con [FastAPI](https://fastapi.tiangolo.com/) y gestionada con [Poetry](https://python-poetry.org/).

## Requisitos previos

Antes de empezar, necesitas tener instalado en tu computadora:

1. **Python 3.10 o superior**

2. **Poetry** (gestor de dependencias)
   - Una vez que tengas Python instalado, abri una terminal y ejecuta:
     ```bash
     pip install poetry
     ```
   - Verifica que se instalo correctamente:
     ```bash
     poetry --version
     ```

## Instalacion del proyecto

1. **Clona el repositorio**

2. **Instala las dependencias** del proyecto:
   ```bash
   poetry install
   ```
   Esto va a crear un entorno virtual automaticamente y va a instalar todas las librerias necesarias (FastAPI, Uvicorn, httpx, etc.).

## Como ejecutar la API

1. **Inicia el servidor** ejecutando:
   ```bash
   poetry run uvicorn app.main:app --workers 4
   ```
   El flag `--workers 4` levanta 4 procesos (workers) para atender requests en paralelo.

2. **Abri tu navegador** y entra a: [http://127.0.0.1:8000/hello](http://127.0.0.1:8000/hello)

   Vas a ver la respuesta de la API:
   ```json
   {"message": "Hola mundo!"}
   ```

3. **Documentacion interactiva**: FastAPI genera documentacion automatica de tu API. Podes acceder a ella en:
   - Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   - ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

4. **Para detener el servidor**, presiona `CTRL+C` en la terminal.

## Endpoints disponibles

### General

| Metodo | Endpoint | Descripcion |
|---|---|---|
| `GET` | `/hello` | Devuelve un saludo. |

### Sumas

| Metodo | Endpoint | Descripcion |
|---|---|---|
| `GET` | `/sum?a=1&b=2` | Suma dos numeros. |
| `GET` | `/sum-square?a=1&b=2` | Llama internamente a `/sum` por red y devuelve el cuadrado de la suma. |

### Usuarios

| Metodo | Endpoint | Descripcion |
|---|---|---|
| `GET` | `/user` | Lista todos los usuarios. |
| `POST` | `/user` | Crea un nuevo usuario. |
| `GET` | `/user/{username}` | Obtiene un usuario por username. |
| `PUT` | `/user/{username}` | Reemplaza un usuario completamente. |
| `PATCH` | `/user/{username}` | Actualiza parcialmente un usuario. |
| `DELETE` | `/user/{username}` | Elimina un usuario. |
