# syntax=docker/dockerfile:1

# Base images are pinned by digest (supply-chain reproducibility: a retagged
# release can never silently change what we build). To update, pull the new
# digest from https://hub.docker.com/v2/repositories/library/<img>/tags/<tag>
# and bump the tag comment too. Pinned on 2026-08-06.

# ---- frontend build --------------------------------------------------
# node:20-slim
FROM node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS frontend-build
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
# python:3.12-slim
FROM python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b AS backend
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
