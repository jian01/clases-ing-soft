FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el codigo de la aplicacion Dagster
COPY dwh_pipeline/ ./dagster/dwh_pipeline/

ENV DAGSTER_HOME=/workspace/dagster
ENV PYTHONPATH=/workspace/dagster

EXPOSE 3000

# El entrypoint corre dbt deps + dbt parse usando el volumen montado, luego arranca Dagster
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
CMD ["/entrypoint.sh"]
