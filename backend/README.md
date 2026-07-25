# CronDok Backend

Backend de CronDok: scheduler de tareas self-hosted (FastAPI + SQLAlchemy async + SQLite WAL + APScheduler).

Ver `docs/ESPECIFICACION_TECNICA_CRONDOK.md` para la arquitectura completa. Para
desplegar CronDok completo (backend + frontend) con Docker, ver el `README.md` en
la raíz del repo — esto de aquí es solo para desarrollo local del backend.

## Desarrollo

```bash
poetry install
poetry run pytest
poetry run ruff check . && poetry run ruff format --check .
poetry run mypy .
poetry run alembic upgrade head
```
