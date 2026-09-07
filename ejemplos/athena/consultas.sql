-- ===========================================================================
-- Practica 4 - S3 + Athena
-- ===========================================================================
-- Antes de correr esto:
--   1. terraform apply
--   2. aws s3 sync ./ejemplos/athena s3://<bucket_athena>/datos
--   3. En el query editor: Configuracion de consultas -> Administrar ->
--      Ubicacion de resultados = s3://<bucket_athena>/resultados/
--   4. Verificar que el selector Database diga "default"
--
-- Reemplazar <bucket_athena> por el output del terraform. Si preferis, el
-- output athena_create_table_personas ya trae la primera sentencia armada.
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- TABLA 1 - personas
-- ---------------------------------------------------------------------------
-- EXTERNAL = la tabla es solo una definicion. Si la borras, el CSV en S3
-- sigue intacto. LOCATION apunta al PREFIJO datos/personas/, no al archivo:
-- Athena lee todo lo que haya abajo.

CREATE EXTERNAL TABLE IF NOT EXISTS personas (
    nombre  STRING,
    edad    INT,
    ciudad  STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
LINES TERMINATED BY '\n'
LOCATION 's3://<bucket_athena>/datos/personas/'
TBLPROPERTIES ('skip.header.line.count'='1');


-- El SELECT de siempre. Fijate abajo del resultado: "Data scanned".
-- Eso es exactamente lo que se factura.
SELECT * FROM personas;


-- Agrupar, contar y promediar: SQL normal sobre un CSV.
SELECT ciudad,
       COUNT(*)          AS cantidad,
       ROUND(AVG(edad))  AS edad_promedio
FROM personas
GROUP BY ciudad
ORDER BY cantidad DESC;


-- ---------------------------------------------------------------------------
-- TABLA 2 - ventas
-- ---------------------------------------------------------------------------
-- Otro prefijo, otra tabla. Por eso los CSV no estan sueltos en datos/:
-- si compartieran prefijo, Athena intentaria leer los dos con el mismo
-- esquema y las filas de uno saldrian como basura en el otro.

CREATE EXTERNAL TABLE IF NOT EXISTS ventas (
    fecha            STRING,
    producto         STRING,
    categoria        STRING,
    cantidad         INT,
    precio_unitario  DOUBLE
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
LINES TERMINATED BY '\n'
LOCATION 's3://<bucket_athena>/datos/ventas/'
TBLPROPERTIES ('skip.header.line.count'='1');


-- Facturacion por categoria: la columna calculada no existe en el CSV,
-- se computa al momento de la consulta.
SELECT categoria,
       SUM(cantidad)                        AS unidades,
       SUM(cantidad * precio_unitario)      AS facturado
FROM ventas
GROUP BY categoria
ORDER BY facturado DESC;


-- Top 5 productos por facturacion.
SELECT producto,
       SUM(cantidad * precio_unitario) AS facturado
FROM ventas
GROUP BY producto
ORDER BY facturado DESC
LIMIT 5;


-- ---------------------------------------------------------------------------
-- Para cerrar
-- ---------------------------------------------------------------------------
-- Borrar la tabla NO borra los datos: es solo metadata.
-- Despues de este DROP, aws s3 ls sobre el prefijo muestra el CSV igual.

-- DROP TABLE personas;
