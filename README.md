# API de ejemplo con FastAPI

Dos microservicios construidos con [FastAPI](https://fastapi.tiangolo.com/) y gestionados con [Poetry](https://python-poetry.org/).

## Requisitos previos

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (incluido en Docker Desktop)

## Como ejecutar los microservicios

Para levantar ambos microservicios juntos:
```bash
docker compose up api-sum api-user
```

- **Sumas** en [http://localhost:8000](http://localhost:8000)
- **Usuarios** en [http://localhost:8001](http://localhost:8001)

Para levantar uno solo:
```bash
docker compose up api-sum    # solo sumas en puerto 8000
docker compose up api-user   # solo usuarios en puerto 8001
```

**Para detener los servicios**, presiona `CTRL+C` en la terminal.

## Documentacion interactiva

Cada microservicio tiene su propia documentacion:

- Sumas: [http://localhost:8000/docs](http://localhost:8000/docs)
- Usuarios: [http://localhost:8001/docs](http://localhost:8001/docs)

## Como correr los tests

```bash
docker compose run test
```

Esto ejecuta pytest con reporte de cobertura.

## Endpoints disponibles

### Sumas (puerto 8000)

| Metodo | Endpoint | Descripcion |
|---|---|---|
| `GET` | `/hello` | Devuelve un saludo. |
| `GET` | `/sum?a=1&b=2` | Suma dos numeros. |
| `GET` | `/sum-slow?a=1&b=2` | Suma dos numeros de forma lenta (iterativa). |
| `GET` | `/sum-square?a=1&b=2` | Llama internamente a `/sum` por red y devuelve el cuadrado de la suma. |

### Usuarios (puerto 8001)

| Metodo | Endpoint | Descripcion |
|---|---|---|
| `GET` | `/user` | Lista todos los usuarios. |
| `POST` | `/user` | Crea un nuevo usuario. |
| `GET` | `/user/{id}` | Obtiene un usuario por ID. |
| `PUT` | `/user/{id}` | Reemplaza un usuario completamente. |
| `PATCH` | `/user/{id}` | Actualiza parcialmente un usuario. |
| `DELETE` | `/user/{id}` | Elimina un usuario. |
