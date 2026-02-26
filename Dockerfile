# Stage 1: Build PWA
FROM node:22-slim AS pwa-builder
WORKDIR /pwa
COPY pwa/package*.json pwa/bun.lock ./
RUN npm ci
COPY pwa/ .
RUN npm run build

# Stage 2: Python API + built PWA
FROM python:3.13-slim

RUN groupadd -g 1000 app && useradd -u 1000 -g 1000 -m app
WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .
COPY src/investmentology/registry/migrations/ migrations/
COPY serve.py .
COPY --from=pwa-builder /pwa/dist pwa/dist/

USER 1000
EXPOSE 80
CMD ["python3", "serve.py"]
