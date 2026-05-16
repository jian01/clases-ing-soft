-- Dimensión plataforma. Tabla pequeña y estable; SCD tipo 1.
SELECT
    {{ dbt_utils.generate_surrogate_key(['plataforma_id']) }} AS sk_plataforma,
    plataforma_id,
    nombre
FROM {{ ref('stg_plataformas') }}
