# Copiar a terraform.tfvars y cambiar la fecha si el nombre ya esta tomado.
# Un nombre de bucket es unico a nivel MUNDIAL: si el apply falla con
# BucketAlreadyExists, no es un error del codigo, es que alguien llego antes.

region  = "us-east-1"
prefijo = "clase-isw"
fecha   = "20260330"
