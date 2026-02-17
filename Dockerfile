FROM python:3.13-slim AS base

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/
COPY src/investmentology/registry/migrations/ migrations/

EXPOSE 8000

CMD ["uvicorn", "investmentology.api.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
