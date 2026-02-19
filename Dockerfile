# ---- Base stage: production API ----
FROM python:3.10-slim AS base

RUN pip install --no-cache-dir poetry

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root --no-interaction --no-ansi

COPY app/ app/

EXPOSE 8000

ENV APP_MODULE=app.main:app
ENTRYPOINT ["sh", "-c", "poetry run uvicorn $APP_MODULE --host 0.0.0.0 --port 8000 --workers 4"]

# ---- Test stage: tests ----
FROM base AS test

RUN poetry install --no-root --no-interaction --no-ansi

COPY tests/ tests/

ENTRYPOINT []
CMD ["poetry", "run", "pytest", "--cov=app", "--cov-report=term-missing"]
