# syntax=docker/dockerfile:1
# One image: FastAPI serves /api and the built Vue app. Built by GitHub Actions on master (.github/workflows/ci.yml).

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS build
WORKDIR /src
COPY backend/pyproject.toml ./
COPY backend/src ./src
COPY --from=web /web/dist ./src/quarry/web
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    QUARRY_HOST=0.0.0.0 QUARRY_PORT=8000 FORWARDED_ALLOW_IPS=*
COPY --from=build /install /usr/local
RUN useradd --system --uid 10001 quarry
USER quarry
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"
CMD ["quarry", "serve"]
