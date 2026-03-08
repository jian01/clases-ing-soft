# API de ejemplo con FastAPI

Una API simple construida con [FastAPI](https://fastapi.tiangolo.com/) y gestionada con [Poetry](https://python-poetry.org/).

## Requisitos previos

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (incluido en Docker Desktop)

## Como ejecutar la API

1. **Inicia el servidor**:
   ```bash
   docker compose up api
   ```
   La API se levanta en el puerto 8000.

2. **Abri tu navegador** y entra a: [http://localhost:8000/hello](http://localhost:8000/hello)

   Vas a ver la respuesta de la API:
   ```json
   {"message": "Hola mundo!"}
   ```

3. **Documentacion interactiva**: FastAPI genera documentacion automatica de tu API. Podes acceder a ella en:
   - Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
   - ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

4. **Para detener el servidor**, presiona `CTRL+C` en la terminal.

## Como correr los tests

```bash
docker compose run test
```

Esto ejecuta pre-commit (black, flake8, pylint, mypy) y pytest con reporte de cobertura.

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
