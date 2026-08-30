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

## AWS CLI

### Instalacion

**Mac:**
```bash
brew install awscli
```

**Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

**Windows:** Descargar el instalador desde https://aws.amazon.com/cli/

### Configuracion

```bash
aws configure
```

Te va a pedir cuatro valores:

| Campo | Donde conseguirlo |
|---|---|
| AWS Access Key ID | IAM → Users → tu usuario → Security credentials → Create access key |
| AWS Secret Access Key | Se muestra una sola vez al crear la Access Key |
| Default region name | La region de tu instancia, ej: `us-east-1` |
| Default output format | `json` (recomendado) |

### Manejo de instancias EC2

Necesitas el **Instance ID** (formato `i-0abc1234def56789`), que encontras en la consola de EC2.

**Iniciar una instancia:**
```bash
aws ec2 start-instances --instance-ids <instance-id>
```

**Detener una instancia:**
```bash
aws ec2 stop-instances --instance-ids <instance-id>
```

**Ver el estado e IP publica actual:**
```bash
aws ec2 describe-instances --instance-ids <instance-id> \
  --query "Reservations[0].Instances[0].{State:State.Name,IP:PublicIpAddress}" \
  --output table
```

> **Nota:** La IP publica cambia cada vez que se inicia la instancia (a menos que tengas una Elastic IP asignada). Actualizá `INSTANCE_IP` antes de correr el script de deploy.

---

## Deploy en EC2

El script `initial_setup.sh` instala Docker en una instancia EC2 nueva, copia el proyecto y levanta la API en el puerto 8000.

### Prerequisitos

- Tener el archivo `.aws.pem` en la raiz del proyecto.
- Tener `rsync` instalado localmente.
- Tener el puerto 8000 abierto en el Security Group de la instancia.

### Pasos

1. **Copiá la clave al filesystem de Linux** (necesario para que SSH acepte los permisos):

   ```bash
   cp .aws.pem ~/.ssh/aws.pem
   chmod 400 ~/.ssh/aws.pem
   ```

   > **Por que?** SSH requiere que la clave privada tenga permisos estrictos (`400`). Tenerla en `~/.ssh/` garantiza que esos permisos se apliquen correctamente.

2. **Exporta la IP publica de tu instancia EC2**:

   ```bash
   export INSTANCE_IP=<ip-publica-de-tu-instancia>
   ```

3. **Ejecuta el script**:

   ```bash
   bash initial_setup.sh
   ```

   El script hace tres cosas:
   - **[1/3] Instala Docker** en la instancia via SSH (Docker Engine + plugin `docker compose`).
   - **[2/3] Copia los archivos** del proyecto a la instancia usando `rsync`, excluyendo `.git`, caches y archivos compilados.
   - **[3/3] Construye y levanta** el servicio `api` con `docker compose up -d --build`.

4. La API queda disponible en `http://<INSTANCE_IP>:8000`.

---

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
