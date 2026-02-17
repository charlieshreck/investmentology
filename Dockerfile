FROM python:3.13-slim

RUN groupadd -g 1000 app && useradd -u 1000 -g 1000 -m app
WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .
COPY src/investmentology/registry/migrations/ migrations/

USER 1000
EXPOSE 8000
CMD ["uvicorn", "investmentology.api.app:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
