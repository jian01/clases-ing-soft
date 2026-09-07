# clases-ing-soft

Repositorio de prácticas de **Ingeniería de Software** — Universidad de San
Andrés.

## Práctica 4 — Funcionamiento de S3

Terraform que crea los tres buckets de la práctica, más los archivos de
ejemplo para subir con la AWS CLI.

```
terraform/            infraestructura (main.tf) y guía paso a paso
ejemplos/web/         sitio estático
ejemplos/athena/      CSV + consultas SQL
ejemplos/archivos/    archivos sueltos para ls / cp / rm / sync
```

Arrancar por [`terraform/README.md`](terraform/README.md).

```bash
cd terraform
terraform init
terraform apply
terraform output comandos_para_subir
```
