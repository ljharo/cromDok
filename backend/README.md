# CronDok Backend

Backend de CronDok: scheduler de tareas self-hosted (FastAPI + SQLAlchemy async + SQLite WAL + APScheduler).

Ver `docs/ESPECIFICACION_TECNICA_CRONDOK.md` para la arquitectura completa.

## Desarrollo

```bash
poetry install
poetry run pytest
poetry run ruff check . && poetry run ruff format --check .
poetry run mypy .
poetry run alembic upgrade head
```
