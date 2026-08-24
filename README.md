# Clase: Docker Compose

## Estructura del proyecto

```
.
├── docker-compose.yml   # Orquestación de servicios
├── react-app/           # Frontend React (Vite + TypeScript, servido con nginx)
└── py-app/              # Backend FastAPI (Python)
```

---

# Pushear a un registro: 
react-app
```bash
docker build -t react-app:1.0-dev
docker tag react-app:1.0-dev <registry>/<namespace>/<repository>:front-1.0-dev
docker push <registry>/<namespace>/<repository>:front-1.0-dev
```

py-app
```bash
docker build -f ./Dockerfile -t py-app:1.0-dev .
docker tag py-app:1.0-dev <registry>/<namespace>/<repository>:back-1.0-dev # (tag)
docker push <registry>/<namespace>/<repository>:back-1.0-dev
```
---

## CI: publicar en un registro automáticamente

Hay **un workflow por registro**, los dos disparados por cada push a `feature/docker`. Cada uno buildea una imagen por servicio (matrix `py-app` / `react-app`):

| Workflow | Registro | Nombre de la imagen | Autenticación |
|---|---|---|---|
| `.github/workflows/docker-publish-ghcr.yml` | GHCR | `ghcr.io/<owner>/<repo>/py-app` | `GITHUB_TOKEN` (automático) |
| `.github/workflows/docker-publish-dockerhub.yml` | Docker Hub | `docker.io/<usuario>/<repo>-py-app` | `vars.DOCKERHUB_USERNAME` + `secrets.DOCKERHUB_TOKEN` |

La diferencia de nombres no es capricho: GHCR soporta namespaces anidados (`owner/repo/servicio`), Docker Hub no, así que ahí el servicio va como sufijo (`repo-servicio`).

> **Ojo:** al estar separados, cada workflow buildea por su cuenta. Las dos imágenes son equivalentes pero **no comparten digest**. Si se necesita el mismo digest en ambos registros, hay que buildear una vez y copiar la imagen entre registros (`crane copy` / `skopeo copy`) en vez de rebuildear.

### Tags que genera

`docker/metadata-action` genera los tags según la convención estándar:

- `sha-a1b2c3d` → inmutable, atado al commit. **Es el único que sirve para deployar o hacer rollback.**
- `feature-docker` → tag de rama, se mueve en cada push. Sirve para probar, no para deployar.
- `1.2.3`, `1.2`, `1` → si se taggea el repo con `v1.2.3`.
- `latest` → solo en la rama default, y es un puntero móvil (ver "Errores comunes").

Además embebe labels OCI (`org.opencontainers.image.source`, `.revision`, etc.) en la imagen, así se puede trazar de qué commit salió:

```bash
docker inspect ghcr.io/<owner>/<repo>/py-app:sha-a1b2c3d --format '{{json .Config.Labels}}'
```

### Configurar Docker Hub

En **Settings → Secrets and variables → Actions** del repo:

- Variable `DOCKERHUB_USERNAME`: el usuario/organización de Docker Hub (en minúsculas, **no** el email).
- Secret `DOCKERHUB_TOKEN`: un *access token* (Account settings → Personal access tokens), **no** la contraseña.

Si no están cargadas, el workflow de Docker Hub avisa y se saltea; no falla.

**Error típico:** `malformed HTTP Authorization header`. Las credenciales viajan en un header `Authorization: Basic base64(usuario:token)`; si el secret quedó guardado con un salto de línea, un espacio o comillas (pasa al copiar/pegar), el header sale roto. El workflow ahora limpia y valida las credenciales antes del login, pero si el token está mal pegado de raíz conviene regenerarlo y pegarlo de una sola línea.

Las imágenes de GHCR nacen privadas: para hacer `docker pull` sin login hay que marcarlas públicas en la página del package.

---

## Errores comunes

- **Usar `latest` como tag de imagen**
  `latest` no garantiza reproducibilidad. Si alguien hace `docker pull` en otro momento puede obtener una versión diferente. Siempre usar tags semánticos (`1.0.0`, `2.3.1`).

- **No usar `.dockerignore`**
  Sin él, el contexto de build incluye `node_modules/`, `.venv/`, `.git/` y otros directorios pesados, haciendo los builds lentos e impredecibles.

- **Copiar secretos en la imagen**
  Archivos `.env` con credenciales que se copian con `COPY . .` quedan embebidos en la imagen y son visibles con `docker history`. Usar variables de entorno en `docker-compose.yml` o secrets de Docker.

- **No fijar versiones**
  `pip install flask` o `npm install react` sin versión puede romper el build en cualquier momento. Siempre pinear: `flask==3.1.0`, `"react": "^19.0.0"`.

- **(Especifico de react-app) No commitear `package-lock.json`**
  El Dockerfile usa `npm ci`, que requiere un `package-lock.json` existente. Sin él el build falla. Antes del primer `docker compose up --build` hay que correr `npm install` dentro de `react-app/` para generar el lockfile, y commitearlo. `npm ci` es intencionalmente más estricto que `npm install`: instala exactamente lo que dice el lockfile, sin resolver versiones, lo que hace los builds reproducibles.

- **No respetar el orden de las capas en el Dockerfile**
  Copiar todo el código antes de instalar dependencias invalida la caché de `pip install` / `npm ci` en cada cambio de código. Siempre copiar primero los archivos de dependencias, instalar, y después copiar el resto.

---

## Comandos útiles

```bash
# Levantar todo (construye imágenes si es necesario)
docker compose up --build

# Levantar en background
docker compose up --build -d

# Ver logs de un servicio específico
docker compose logs -f py-app

# Bajar servicios (los volúmenes con nombre se conservan)
docker compose down

# Bajar servicios y eliminar volúmenes
docker compose down -v

# Ver imágenes locales
docker images
```
## Demo GitHub Actions

Workflow de publicación automática de imágenes Docker.

TEST DE LAS 16 HORAS

TEST DE LAS 17 HORAS
