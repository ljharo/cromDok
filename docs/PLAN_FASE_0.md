# Plan de Implementación - Fase 0: Fundamentos

> **Basado en:** `docs/ESPECIFICACION_TECNICA_CRONDOK.md` v0.2.0 · `TODO.md`
> **Duración estimada:** 2 semanas
> **Objetivo de la fase:** Dejar el proyecto scaffoldado con backend (Poetry), frontend (Vite),
> calidad automatizada (pre-commit + CI) y la base de persistencia funcionando:
> engine SQLite en WAL, Unit of Work, dominio puro, puertos y repositorios SQLite migrados con Alembic.

---

## 0. Prerequisitos (verificar antes de empezar)

| Herramienta | Versión mínima | Verificación |
|-------------|----------------|--------------|
| Python | 3.12 | `python3 --version` |
| Poetry | 1.8 | `poetry --version` |
| Node.js | 20 | `node --version` |
| Docker | 24+ | `docker info` (daemon corriendo) |
| pre-commit | 3.7 | `pre-commit --version` |

**Criterio de salida de la fase (Definition of Done):**
1. `poetry install`, `npm install` y `pre-commit install` funcionan desde cero.
2. `ruff check`, `ruff format --check` y `mypy` pasan en backend; `eslint` y `tsc --noEmit` en frontend.
3. `pytest` corre verde con los tests de Fase 0.
4. `alembic upgrade head` crea `data/crondok.db` y `PRAGMA journal_mode` devuelve `wal`.
5. CI en GitHub Actions corre verde en un PR de prueba.
6. `docs/TODO.md` actualizado con las tareas 0.1-0.8 marcadas.

> **Puerta de calidad (regla permanente del proyecto):** no se avanza a la siguiente fase
> hasta que todos los tests de la fase actual pasen verde, junto con lint y type-check.
> Si un test falla, se corrige dentro de la fase — no se difiere.

---

## Paso 0.1 - Scaffold del backend (Poetry)

**Orden:** primero en la fase; todo lo demás del backend cuelga de aquí.

1. `mkdir -p backend/src/cron_dok backend/tests/{unit,integration}`
2. `poetry init` no interactivo o `pyproject.toml` manual con layout `src`:
   - deps: `fastapi ^0.115`, `uvicorn[standard]`, `apscheduler ^3.10`, `sqlalchemy[asyncio] ^2.0`,
     `aiosqlite`, `alembic ^1.13`, `pydantic ^2.8`, `pydantic-settings ^2.3`,
     `docker ^7.1`, `cryptography ^42`
   - dev-deps: `pytest ^8.2`, `pytest-asyncio ^0.23`, `httpx ^0.27`, `ruff ^0.5`,
     `mypy ^1.11`, `types-*` necesarios
3. Configurar en el mismo `pyproject.toml`:
   - `[tool.ruff]` — line-length 100, reglas `E, F, I, UP, B, SIM, ANN` (ANN = type hints obligatorios)
   - `[tool.mypy]` — `strict = true` solo para `cron_dok.domain` y `cron_dok.services`
     (override por módulo); modo estándar para `adapters`
   - `[tool.pytest.ini_options]` — `asyncio_mode = "auto"`, `testpaths = ["tests"]`
4. `poetry install` y smoke test: `poetry run python -c "import cron_dok"`.

**Archivos:** `backend/pyproject.toml`, `backend/poetry.lock`, `backend/src/cron_dok/__init__.py`

**Verificación:** `poetry run ruff check . && poetry run mypy .` sin errores (aunque aún no haya código).

---

## Paso 0.2 - Scaffold del frontend (Vite)

1. `npm create vite@latest frontend -- --template react-ts`
2. Instalar y configurar: Tailwind (`tailwind.config.js`, `postcss`), shadcn/ui (`npx shadcn@latest init`),
   TanStack Query, React Router, Axios, Zod.
3. Scripts en `package.json`: `lint`, `type-check` (`tsc --noEmit`), `test:unit` (vitest), `build`.
4. Estructura `src/`: `api/`, `components/`, `features/`, `hooks/`, `types/`, `utils/` (vacías con `.gitkeep`).

**Verificación:** `npm run type-check && npm run lint && npm run build` verdes; `npm run dev` levanta.

> Nota: el frontend es independiente del resto de la fase; puede hacerse en paralelo con 0.3-0.8
> o diferirse si se prioriza el backend. No bloquea nada.

---

## Paso 0.3 - Pre-commit hooks

1. Crear `.pre-commit-config.yaml` en la raíz según spec 8.1 (ruff, mypy, eslint, prettier,
   hooks generales, detect-secrets).
2. `pre-commit install` y `pre-commit run --all-files` hasta que pase limpio.

**Verificación:** commit de prueba dispara los hooks.

---

## Paso 0.4 - CI (GitHub Actions)

1. `.github/workflows/ci-backend.yml` y `ci-frontend.yml` según spec 8.2.
2. Añadir `paths` filter para que cada workflow corra solo cuando cambia su carpeta
   (`backend/**` / `frontend/**`) — evita correr CI de frontend en cambios de backend.
3. Subir y abrir un PR de prueba para validar que ambos workflows corren verdes.

**Verificación:** checks verdes en el PR.

---

## Paso 0.5 - Engine SQLite con WAL (`database.py`)

**Archivo:** `backend/src/cron_dok/adapters/output/persistence/database.py`

1. Crear engine async con `create_async_engine("sqlite+aiosqlite:///data/crondok.db")`.
2. Registrar listener en el evento `connect` que ejecute los pragmas (spec 6.1):

```python
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

3. `session_factory = async_sessionmaker(engine, expire_on_commit=False)`.
4. Test de integración: abrir conexión y assert `PRAGMA journal_mode` → `wal`.

**Dependencia de:** 0.1. **Verificación:** test `test_wal_mode_enabled` verde.

---

## Paso 0.6 - UnitOfWork

**Archivo:** `backend/src/cron_dok/adapters/output/persistence/unit_of_work.py`

1. Clase `UnitOfWork` con `__aenter__`/`__aexit__`: crea sesión al entrar, `commit()` al salir
   sin excepción, `rollback()` + `close()` si la hay (spec 6.2).
2. Expone repositorios como propiedades perezosas (`uow.projects`, `uow.runners`,
   `uow.executions`, `uow.env_vars`) construidos sobre la sesión activa.
3. Test: escritura con excepción a mitad → rollback (la fila no existe); escritura normal → commit.

**Dependencia de:** 0.5 (engine) y 0.8 (repositorios) — se implementa la clase en 0.6 y se
conectan los repositorios al final de 0.8.

---

## Paso 0.7 - Dominio puro

**Carpeta:** `backend/src/cron_dok/domain/`

1. Entidades (dataclasses, sin dependencias externas, spec 4.2.1):
   - `entities/project.py` — `id, name, description, created_at`
   - `entities/runner.py` — incluye `on_overlap: Literal["skip","queue","kill_previous"]`
   - `entities/execution.py` — `id, runner_id, status, trigger_type, started_at, finished_at, exit_code, duration_ms, log_path`
   - `entities/env_var.py` — `id, project_id, runner_id|None, key, encrypted_value`
2. Value objects (inmutables, validan en `__post_init__`):
   - `CronExpression` — valida formato con `croniter` (añadir dep) o APScheduler
   - `ResourceLimits` — `memory_mb, cpu_quota, pids_limit, network_enabled`
   - `ExecutionResult` — `exit_code, duration_ms, timed_out`
3. Servicio de dominio: `services/cron_validator.py` (regla pura, sin I/O).
4. Tests unitarios por cada validación (cron inválido, límites negativos, etc.).

**Verificación:** `mypy --strict` pasa en `domain/`; tests unitarios verdes sin tocar DB ni Docker.

---

## Paso 0.8 - Puertos, modelos ORM, repositorios y Alembic

1. **Puertos** (`ports/`): interfaces ABC de `ProjectRepository`, `RunnerRepository`,
   `ExecutionRepository`, `EnvVarRepository`, `JobExecutor`, `LogStore` (spec 4.2.2).
2. **Modelos ORM** (`adapters/output/persistence/models/`): tablas con SQLAlchemy 2.0
   (`Mapped[]`, `mapped_column`), FK con `ON DELETE CASCADE` de project → runners → executions.
3. **Repositorios SQLite**: implementan los puertos traduciendo modelo ORM ↔ entidad de dominio
   (mapper privado `_to_entity` / `_to_model`).
4. **Alembic**: `alembic init alembic`, configurar `env.py` con el metadata y la URL desde
   settings; primera migración con las 4 tablas; `alembic upgrade head`.
5. Conectar repositorios al `UnitOfWork` (0.6).
6. Tests de integración por repositorio: save/get/list/delete con rollback entre tests
   (fixture de DB temporal en `tmp_path`).

**Verificación:** `alembic upgrade head` desde cero; tests de integración verdes;
`PRAGMA journal_mode` → `wal` en la DB generada.

---

## Orden de ejecución sugerido

```
0.1 ──► 0.5 ──► 0.7 ──► 0.8 ──► (0.6 se completa al final de 0.8)
 │         ▲
 ├──► 0.3 ─┤ (0.3 y 0.4 en cuanto exista pyproject.toml)
 ├──► 0.4 ─┘
 └──► 0.2 (paralelo, no bloquea)
```

## Riesgos de la fase

| Riesgo | Mitigación |
|--------|------------|
| `mypy --strict` pelea con SQLAlchemy/async desde el día 1 | Strict solo en `domain/` (decisión ya tomada en spec 8.3) |
| Alembic + async requiere configuración extra en `env.py` | Usar plantilla async oficial (`alembic init -t async`) |
| Versiones de shadcn/ui cambian el flujo de init | Fijar en el plan el comando exacto usado y commitear `components.json` |
| Pragmas no se aplican por usar el engine equivocado | Test de integración `test_wal_mode_enabled` como red de seguridad |

## Al terminar la fase

- [ ] Marcar 0.1-0.8 como `[x]` en `TODO.md` y actualizar la tabla de progreso (Fase 0 → 8/8).
- [ ] Añadir entrada al Registro de Cambios de `TODO.md`.
- [ ] Commit con `feat: scaffold project foundation (phase 0)`.
