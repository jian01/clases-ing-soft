# Práctica 4 — S3 con Terraform

Crea los tres buckets de la práctica y deja los archivos de ejemplo listos
para subir con la CLI.

| Bucket | Para qué | Acceso |
|---|---|---|
| `clase-isw-web-<fecha>` | Hostear el sitio estático | **Público** (lectura) |
| `clase-isw-athena-<fecha>` | Datos crudos + resultados de Athena | Privado |
| `clase-isw-files-<fecha>` | Archivos sueltos para `ls` / `cp` / `rm` / `sync` | Privado |

## Antes de empezar

```bash
aws sts get-caller-identity   # ¿hay credenciales? (si falla: aws configure)
terraform version             # >= 1.5
```

El usuario IAM necesita permisos sobre S3. Para la clase alcanza
`AmazonS3FullAccess`; en producción se acota al bucket y a las acciones que se
usan de verdad.

## Crear la infraestructura

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

El nombre de un bucket es **único a nivel mundial**. Si el apply falla con
`BucketAlreadyExists`, no está mal el código: alguien llegó antes. Copiá
`ejemplo.tfvars` a `terraform.tfvars` y cambiá `fecha` o `prefijo`.

```bash
cp ejemplo.tfvars terraform.tfvars
# editar y volver a aplicar
terraform apply
```

## Subir los archivos de ejemplo

Los tres comandos salen ya armados en el output `comandos_para_subir`:

```bash
terraform output comandos_para_subir
```

Son estos, desde `terraform/`:

```bash
# 1) sitio estático → la raíz del bucket, porque index.html tiene que quedar
#    en el primer nivel para que el website endpoint lo encuentre
aws s3 sync ../ejemplos/web s3://$(terraform output -raw bucket_web)

# 2) datos de Athena → bajo el prefijo datos/, separado de resultados/
aws s3 sync ../ejemplos/athena s3://$(terraform output -raw bucket_athena)/datos

# 3) archivos sueltos → la raíz, con la subcarpeta reportes/ incluida
aws s3 sync ../ejemplos/archivos s3://$(terraform output -raw bucket_files)
```

## Verificar cada bucket

**Web** — abrir la URL en el navegador:

```bash
terraform output -raw url_sitio_estatico
```

Es `http://`, sin la **s**: el website endpoint de S3 no hace TLS. Probá
también una ruta que no exista (`/loquesea`) y tiene que aparecer
`error.html`.

**Athena** — en el query editor, `Configuración de consultas → Administrar`,
pegar la ubicación de resultados:

```bash
terraform output -raw athena_output_location
```

Después, la primera tabla ya viene armada con el nombre real del bucket:

```bash
terraform output -raw athena_create_table_personas
```

El resto de las consultas están en `../ejemplos/athena/consultas.sql`.

**Files** — la CLI:

```bash
aws s3 ls s3://$(terraform output -raw bucket_files)              # PRE reportes/
aws s3 ls s3://$(terraform output -raw bucket_files) --recursive  # claves completas
```

Y el contraste con el bucket público: pegar en el navegador la URL de un
objeto privado, por ejemplo
`https://<bucket_files>.s3.us-east-1.amazonaws.com/notas.txt`. El
`Access Denied` es la configuración funcionando, no un error.

## Al terminar

```bash
terraform destroy
```

`destroy` falla si los buckets tienen objetos: S3 no borra un bucket que no
esté vacío. Vaciarlos primero:

```bash
aws s3 rm s3://$(terraform output -raw bucket_web)    --recursive
aws s3 rm s3://$(terraform output -raw bucket_athena) --recursive
aws s3 rm s3://$(terraform output -raw bucket_files)  --recursive
terraform destroy
```

> Se podría poner `force_destroy = true` en los buckets para que Terraform
> los vacíe solo. Está a propósito **sin** eso: en un repo real, un
> `force_destroy` distraído se lleva datos de producción.

## Nota sobre el estado

El estado queda en `terraform.tfstate`, local y fuera del repo
(ver `.gitignore`). Para trabajo en equipo iría en un backend remoto —
típicamente otro bucket de S3 con lock en DynamoDB. Se ve en otra clase.
