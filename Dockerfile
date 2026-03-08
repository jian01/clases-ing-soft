# ---- Base stage: production API ----
FROM python:3.10-slim AS base

RUN pip install --no-cache-dir poetry

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root --no-interaction --no-ansi

COPY app/ app/

EXPOSE 8000

ENTRYPOINT ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ---- Test stage: linting + tests ----
FROM base AS test

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

RUN poetry install --no-root --no-interaction --no-ansi

COPY tests/ tests/
COPY .pre-commit-config.yaml .
COPY .pre-commit/ .pre-commit/

RUN git init && git add -A

ENTRYPOINT []
CMD ["bash", "-c", "poetry run pre-commit run --all-files && poetry run pytest --cov=app --cov-report=term-missing"]
