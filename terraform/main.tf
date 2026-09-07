# ---------------------------------------------------------------------------
# Practica 4 - Funcionamiento de S3
# Tres buckets, un proposito cada uno:
#   1. web     -> hostear un sitio estatico (HTML/CSS servidos por S3)
#   2. athena  -> data lake: datos crudos + resultados de las consultas
#   3. files   -> archivos sueltos para practicar ls / cp / rm / sync
# ---------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region # credenciales: ~/.aws
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

variable "region" {
  description = "Region de AWS donde viven los buckets"
  type        = string
  default     = "us-east-1"
}

variable "prefijo" {
  description = "Prefijo comun de los tres buckets"
  type        = string
  default     = "clase-isw"
}

variable "fecha" {
  description = <<-EOT
    Sufijo con la fecha de la clase (YYYYMMDD). El nombre de un bucket es unico
    a nivel MUNDIAL: si el apply falla con BucketAlreadyExists, cambiar este
    valor (o el prefijo) y volver a aplicar.
  EOT
  type        = string
  default     = "20260330"
}

locals {
  # clase-isw-web-20260330, clase-isw-athena-20260330, clase-isw-files-20260330
  bucket_web    = "${var.prefijo}-web-${var.fecha}"
  bucket_athena = "${var.prefijo}-athena-${var.fecha}"
  bucket_files  = "${var.prefijo}-files-${var.fecha}"

  tags_comunes = {
    Proyecto = "ingenieria-de-software"
    Practica = "4-s3"
    Clase    = var.fecha
    Managed  = "terraform"
  }
}

# ===========================================================================
# BUCKET 1 - Sitio estatico
# ===========================================================================
# Es el unico bucket publico de los tres, y a proposito: para servir una web
# por HTTP, cualquiera en internet tiene que poder hacer GetObject.
# Se necesitan cuatro recursos ademas del bucket:
#   - website_configuration  -> que archivo es el index y cual el de error
#   - public_access_block    -> destrabar el bloqueo (viene todo en true)
#   - ownership_controls     -> ACLs deshabilitadas (modelo recomendado hoy)
#   - bucket_policy          -> el permiso real de lectura publica
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "web" {
  bucket = local.bucket_web

  tags = merge(local.tags_comunes, {
    Name = local.bucket_web
    Uso  = "sitio-estatico"
  })
}

resource "aws_s3_bucket_website_configuration" "web" {
  bucket = aws_s3_bucket.web.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "error.html"
  }
}

# Por defecto S3 bloquea TODO acceso publico, incluso si la policy lo permite:
# es el candado de arriba y hay que abrirlo antes de que la bucket policy tenga
# algun efecto. Se destraba solo lo justo:
#   - block_public_policy     -> false, si no la API rechaza la policy publica
#   - restrict_public_buckets -> false, si no la policy queda puesta pero inerte
# Los dos flags de ACL siguen en true: con BucketOwnerEnforced (mas abajo) las
# ACLs estan deshabilitadas, asi que no hay nada que destrabar ahi.
resource "aws_s3_bucket_public_access_block" "web" {
  bucket = aws_s3_bucket.web.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_ownership_controls" "web" {
  bucket = aws_s3_bucket.web.id

  rule {
    object_ownership = "BucketOwnerEnforced" # ACLs disabled
  }
}

resource "aws_s3_bucket_policy" "web_lectura_publica" {
  bucket = aws_s3_bucket.web.id

  # Sin este depends_on Terraform puede intentar poner la policy antes de
  # destrabar el bloqueo y la API responde AccessDenied.
  depends_on = [aws_s3_bucket_public_access_block.web]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PermitirLecturaPublica"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.web.arn}/*" # ojo: /* son los objetos, no el bucket
      }
    ]
  })
}

# ===========================================================================
# BUCKET 2 - Athena
# ===========================================================================
# Privado. Dos prefijos con roles distintos:
#   datos/       -> los CSV crudos que consultamos
#   resultados/  -> donde Athena escribe cada resultado antes de mostrarlo
# Estan separados porque LOCATION en una tabla externa es un PREFIJO, no un
# archivo: Athena lee todo lo que haya abajo. Si los resultados cayeran junto
# a los datos, la proxima consulta se leeria a si misma.
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "athena" {
  bucket = local.bucket_athena

  tags = merge(local.tags_comunes, {
    Name = local.bucket_athena
    Uso  = "athena-data-lake"
  })
}

resource "aws_s3_bucket_public_access_block" "athena" {
  bucket = aws_s3_bucket.athena.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "athena" {
  bucket = aws_s3_bucket.athena.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Cada consulta de Athena escribe un archivo nuevo en resultados/: ese prefijo
# crece solo y se factura. La regla lo limpia a los 7 dias.
resource "aws_s3_bucket_lifecycle_configuration" "athena" {
  bucket = aws_s3_bucket.athena.id

  rule {
    id     = "borrar-resultados-viejos"
    status = "Enabled"

    filter {
      prefix = "resultados/"
    }

    expiration {
      days = 7
    }
  }
}

# ===========================================================================
# BUCKET 3 - Archivos simples
# ===========================================================================
# El bucket de juguete para la parte de AWS CLI: subir, bajar, borrar y
# sincronizar. Privado y sin versioning, para que 'aws s3 rm' realmente borre
# y se vea que no hay papelera de reciclaje.
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "files" {
  bucket = local.bucket_files

  tags = merge(local.tags_comunes, {
    Name = local.bucket_files
    Uso  = "archivos-cli"
  })
}

resource "aws_s3_bucket_public_access_block" "files" {
  bucket = aws_s3_bucket.files.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "files" {
  bucket = aws_s3_bucket.files.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Sin recurso de versioning a proposito: un bucket nuevo ya viene con
# versioning apagado. Si se activara, 'aws s3 rm' no borraria el objeto,
# escribiria un delete marker encima y cada version seguiria ocupando
# espacio facturado.

# ===========================================================================
# Outputs
# ===========================================================================

output "bucket_web" {
  description = "Bucket del sitio estatico"
  value       = aws_s3_bucket.web.id
}

output "bucket_athena" {
  description = "Bucket de datos y resultados de Athena"
  value       = aws_s3_bucket.athena.id
}

output "bucket_files" {
  description = "Bucket de archivos sueltos para la CLI"
  value       = aws_s3_bucket.files.id
}

output "url_sitio_estatico" {
  description = "URL del sitio (website endpoint, HTTP sin TLS)"
  value       = "http://${aws_s3_bucket_website_configuration.web.website_endpoint}"
}

output "athena_output_location" {
  description = "Pegar en Athena -> Configuracion de consultas -> Administrar"
  value       = "s3://${aws_s3_bucket.athena.id}/resultados/"
}

output "comandos_para_subir" {
  description = "Los tres sync que suben los archivos de ejemplo"
  value = <<-EOT

    # 1) sitio estatico
    aws s3 sync ../ejemplos/web s3://${aws_s3_bucket.web.id}
    #    -> http://${aws_s3_bucket_website_configuration.web.website_endpoint}

    # 2) datos para Athena
    aws s3 sync ../ejemplos/athena s3://${aws_s3_bucket.athena.id}/datos

    # 3) archivos sueltos
    aws s3 sync ../ejemplos/archivos s3://${aws_s3_bucket.files.id}
  EOT
}

output "athena_create_table_personas" {
  description = "CREATE EXTERNAL TABLE listo para pegar en el query editor"
  value       = <<-EOT

    CREATE EXTERNAL TABLE IF NOT EXISTS personas (
        nombre  STRING,
        edad    INT,
        ciudad  STRING
    )
    ROW FORMAT DELIMITED
    FIELDS TERMINATED BY ','
    LINES TERMINATED BY '\n'
    LOCATION 's3://${aws_s3_bucket.athena.id}/datos/personas/'
    TBLPROPERTIES ('skip.header.line.count'='1');
  EOT
}
