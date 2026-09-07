# Archivos de ejemplo

Uno por bucket. Se suben con `aws s3 sync` — los comandos exactos están en
[`../terraform/README.md`](../terraform/README.md).

```
ejemplos/
├── web/                    → bucket del sitio estático (a la raíz)
│   ├── index.html            documento índice
│   ├── estilos.css           segundo objeto: si la policy está mal, carga sin estilos
│   └── error.html            documento de error (404)
│
├── athena/                 → bucket de Athena, bajo el prefijo datos/
│   ├── personas/
│   │   └── personas.csv      nombre,edad,ciudad — 20 filas
│   ├── ventas/
│   │   └── ventas.csv        fecha,producto,categoria,cantidad,precio — 27 filas
│   └── consultas.sql         CREATE EXTERNAL TABLE + los SELECT de la clase
│
└── archivos/               → bucket de archivos sueltos (a la raíz)
    ├── notas.txt             para subir, sobrescribir y borrar
    ├── datos20260330.csv     el CSV chico de la presentación
    ├── config.json           otro tipo de contenido
    ├── lista.md              checklist de la práctica
    └── reportes/             subcarpeta local → prefijo en S3
        ├── reporte-marzo.txt
        └── reporte-abril.txt
```

## Por qué los CSV de Athena están en subcarpetas

`LOCATION` en una tabla externa es un **prefijo**, no un archivo: Athena lee
todo lo que haya abajo. Si `personas.csv` y `ventas.csv` compartieran prefijo,
cada tabla intentaría leer los dos con su propio esquema y las filas del otro
saldrían como basura.

Por lo mismo los resultados van a `resultados/` y no a `datos/`: si cayeran
junto a los datos, la próxima consulta se leería a sí misma.

## Los CSV no llevan comillas

Están pensados para `ROW FORMAT DELIMITED FIELDS TERMINATED BY ','`, que es el
parser simple: no entiende campos entrecomillados ni comas dentro de un valor.
Por eso ninguna ciudad ni producto tiene coma. Para CSV de verdad hay que usar
`OpenCSVSerde`.
