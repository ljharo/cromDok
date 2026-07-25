# syntax=docker/dockerfile:1

# ---- frontend build --------------------------------------------------
FROM node:20-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- backend runtime ---------------------------------------------------
# CronDok mounts the host's Docker socket to launch job containers
# (Docker-out-of-Docker, spec 9.3): whoever controls this process already
# has root-equivalent power over the host, so this image runs as root and
# does not attempt to sandbox itself — the sandboxing (spec 9.2) applies to
# the ephemeral *job* containers it launches, not to this one.
FROM python:3.12-slim AS backend
WORKDIR /app

COPY backend/pyproject.toml backend/poetry.lock backend/README.md ./
COPY backend/src ./src
RUN pip install --no-cache-dir .

COPY backend/alembic ./alembic
COPY backend/alembic.ini ./

COPY --from=frontend-build /app/dist ./static
ENV CRONDOK_STATIC_DIR=/app/static

COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
