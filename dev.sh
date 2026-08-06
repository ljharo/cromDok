#!/usr/bin/env bash
# Arranca backend (uvicorn :8000, con --reload) y frontend (Vite :5173, que
# proxifica /api al 8000) juntos para desarrollo local. Ctrl-C mata ambos;
# si uno de los dos muere, el otro también se detiene.
#
# Requisitos: `poetry install` en backend/ y `npm ci` en frontend/.
# Producción (un solo contenedor): docker compose up -d
set -euo pipefail

cd "$(dirname "$0")"

pids=()
cleanup() {
  kill "${pids[@]}" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

(
  cd backend
  poetry run alembic upgrade head
  poetry run uvicorn cron_dok.main:app --reload --port 8000
) &
pids+=($!)

(
  cd frontend
  npm run dev
) &
pids+=($!)

echo "CronDok dev: UI en http://localhost:5173 (API en :8000). Ctrl-C para parar."

# Sale en cuanto uno de los dos procesos termine; el trap mata al otro.
wait -n "${pids[@]}"
