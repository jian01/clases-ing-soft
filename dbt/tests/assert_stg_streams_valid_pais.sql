-- Países deben ser código ISO 3166-1 alpha-2: exactamente 2 letras mayúsculas.
-- Este test falla si llega un país mal formado (ej. "ARG", "ar", "00").
SELECT stream_id
FROM {{ ref('stg_streams') }}
WHERE pais_usuario IS NOT NULL
  AND pais_usuario !~ '^[A-Z]{2}$'
