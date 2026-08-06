# AGENTS.md — CronDok

Guía para agentes de IA que trabajen en este repositorio. Asume que el lector
no conoce el proyecto. La documentación funcional completa está en
`docs/ESPECIFICACION_TECNICA_CRONDOK.md` (las secciones de la spec se citan en
el código como "spec X.Y"); `docs/PLAN_FASE_*.md` describen las fases de
desarrollo y `docs/TODO.md` el trabajo pendiente.

## Descripción del proyecto

CronDok es un **scheduler de tareas self-hosted, open source y auto-contenido**
(MIT). Permite definir _runners_ (scripts en Bash, Python o Node.js) con una
expresión cron, cada uno ejecutado en un **contenedor Docker efímero y
aislado**. Gestiona proyectos, variables de entorno cifradas, ejecuciones
manuales o programadas y sus logs desde una interfaz web única.

Todo corre en **un solo contenedor** (`docker compose up -d`): el backend
FastAPI sirve la API (`/api/v1`) y también el build estático del frontend
(SPA con fallback a `index.html`). No hay nginx ni servicios separados.

## Stack tecnológico

- **Backend** (`backend/`): Python ≥ 3.12, FastAPI 0.115, SQLAlchemy 2.0 async
  con SQLite (WAL, via aiosqlite), Alembic, APScheduler 3.x, docker-py,
  pydantic/pydantic-settings, cryptography (Fernet), pwdlib[argon2], croniter.
  Gestión de dependencias con **Poetry** (`backend/pyproject.toml`).
- **Frontend** (`frontend/`): React 18 + TypeScript + Vite 5, React Router 6,
  TanStack Query, axios, react-hook-form + zod, Tailwind CSS + shadcn/ui
  (componentes Radix en `src/components/ui`), CodeMirror para editar scripts.
  Node 20, paquetes con **npm** (`package-lock.json` commiteado).
- **Despliegue**: un único `Dockerfile` multi-stage en la raíz (build del
  frontend → runtime Python; imágenes base **fijadas por digest**) +
  `docker-compose.yml`. El entrypoint (`deploy/entrypoint.sh`) corre
  `alembic upgrade head` y luego uvicorn en el puerto 8000.

## Estructura del código

### Backend: arquitectura hexagonal (puertos y adaptadores)

`backend/src/cron_dok/` está organizado estrictamente por capas:

- `domain/` — entidades (`entities/`), value objects (`value_objects/`) y
  servicios de dominio (`services/cron_validator.py`). Sin dependencias de
  framework.
- `ports/` — interfaces (ABCs/Protocol): `repositories/`, `executors/`
  (JobExecutor), `logs/` (LogStore), `unit_of_work.py`.
- `services/` — servicios de aplicación (project, runner, env_var, auth,
  api_key, scheduler, execution_queue, retention, notification, rbac,
  identity). Reciben sus dependencias **por constructor** (inyección manual,
  sin contenedor DI). Errores de aplicación en `services/errors.py`.
- `adapters/input/` — HTTP: `http/routers/` (un router por recurso), schemas
  pydantic, dependencias FastAPI, rate limiters; y `scheduler/`
  (APSchedulerAdapter).
- `adapters/output/` — `persistence/` (modelos SQLAlchemy, repositorios,
  UnitOfWork, engine), `executor/docker_executor.py`, `logs/file_log_store.py`,
  `security/` (cifrado Fernet, hashing argon2).
- `main.py` — application factory (`create_app`): el lifespan de FastAPI
  construye todo el grafo de objetos y lo expone en `app.state`. Es el único
  sitio que conoce FastAPI en el wiring; los tests inyectan fakes vía los
  parámetros `executor=` y `scheduler_backend=`.
- `config.py` — `Settings` (pydantic-settings), **fuente de verdad** de las
  variables de entorno, todas con prefijo `CRONDOK_`.

Migraciones Alembic en `backend/alembic/` (aplicadas al arrancar el
contenedor). Datos persistentes en `backend/data/` (o `data/` en la raíz con
compose): `crondok.db`, `.master_key`, logs de ejecuciones.

Conceptos clave del dominio: la `ExecutionQueue` (`services/execution_queue.py`)
es el **único escritor** de transiciones de estado de ejecuciones (patrón
single-writer para evitar `database is locked` en SQLite), con un semáforo de
concurrencia (`CRONDOK_MAX_CONCURRENT_JOBS`, default 4) y política de solape
por runner (`skip` / `queue` / `kill_previous`). El contrato de cancelación es
importante: un `JobExecutor` debe ser cancellation-safe (ante
`CancelledError`, matar el contenedor y re-lanzar). El scheduler se rehidrata
desde la BD al arrancar y registra un job de sistema diario (purga de
retención, 04:17).

### Frontend: organización por features

- `src/features/` — un directorio por dominio (`projects`, `runners`,
  `executions`, `env-vars`, `auth`, `users`, `api-keys`), cada uno con sus
  páginas, tablas y `hooks.ts` (hooks de TanStack Query).
- `src/api/` — `client.ts` (instancia única de axios, `baseURL: "/api/v1"`,
  sesión por cookie HttpOnly con `withCredentials`, interceptor que redirige a
  `/login` ante 401) y `endpoints.ts`.
- `src/components/` — `Layout`, componentes compartidos y `ui/` (shadcn/ui).
- `src/router.tsx` — rutas con guards (`RequireAuth`, `RequireRole`).
- Alias `@` → `src/`. El dev server de Vite proxifica `/api` a
  `http://localhost:8000`.

## Comandos de build, test y desarrollo

### Backend (desde `backend/`)

```bash
poetry install
poetry run pytest                                   # tests
poetry run ruff check . && poetry run ruff format --check .
poetry run mypy .
poetry run alembic upgrade head                     # migraciones
```

### Frontend (desde `frontend/`)

```bash
npm ci
npm run dev            # Vite dev server con proxy a :8000
npm run lint           # eslint, --max-warnings 0
npm run type-check     # tsc --noEmit
npm run test:unit      # vitest run
npm run build
npm run format         # prettier --write .
```

### Aplicación completa

```bash
docker compose up -d   # único comando de despliegue; UI en :8000
./dev.sh               # desarrollo: uvicorn :8000 (--reload) + Vite :5173 juntos
```

El primer arranque crea el usuario `admin` con contraseña generada, mostrada
**una sola vez** en los logs (`docker compose logs crondok | grep "First boot"`).

### Pre-commit

`pre-commit install` y `pre-commit run --all-files`. Hooks: ruff + ruff-format,
mypy (con `--config-file=backend/pyproject.toml`), eslint, prettier
(excluye `docs/`), checks genéricos y **detect-secrets** con baseline en
`.secrets.baseline`.

### CI

GitHub Actions con dos workflows filtrados por paths: `ci-backend.yml`
(ruff check, ruff format --check, mypy, pytest con coverage) y
`ci-frontend.yml` (lint, type-check, test:unit, build). Todo lo que corra en
CI debe pasar localmente antes de hacer push.

## Convenciones de estilo

### Python

- Ruff: `line-length = 100`, target `py312`, reglas `E, F, I, UP, B, SIM, ANN`
  (anotaciones de tipo obligatorias, incluidas en firma; `tests/**` exento de
  ANN). Formateo con `ruff format`. `alembic/` excluido del lint.
- isort via ruff con `known-first-party = ["cron_dok"]`.
- mypy: `strict = true` para `cron_dok.domain.*` y `cron_dok.services.*`; el
  resto con `warn_unused_ignores`/`warn_redundant_casts`. docker-py y
  apscheduler no tienen stubs (ignore_missing_imports ya configurado).
- Docstrings en inglés y estilo descriptivo, citando la spec cuando aplica
  (ej. `# spec 9.2`); comentarios puntuales en español también presentes.
- Arquitectura: mantener la separación de capas — el dominio no importa
  FastAPI ni SQLAlchemy; los routers solo orquestan; la lógica va en
  `services/`; nuevas integraciones externas van detrás de un port en
  `ports/` con su adaptador en `adapters/output/`.

### TypeScript/React

- Prettier: `printWidth: 100`, comillas dobles, `trailingComma: "all"`, punto
  y coma. ESLint con typescript-eslint + react-hooks + react-refresh, y
  `--max-warnings 0` (cero warnings).
- TypeScript estricto vía `tsc --noEmit`.
- Componentes funcionales; data fetching exclusivamente con TanStack Query en
  hooks por feature; formularios con react-hook-form + zod; llamadas HTTP solo
  a través de `src/api/client.ts` y `endpoints.ts`.

## Testing

### Backend (`backend/tests/`)

- pytest con `asyncio_mode = "auto"` (los tests async no necesitan decorador).
- Tres niveles: `unit/` (fakes en `unit/fakes.py`), `api/` (endpoints con
  app de test) e `integration/` (SQLite real por test en `tmp_path`, ver
  `tests/conftest.py`; repositorios, UnitOfWork, migraciones, executor).
- Marker `docker`: tests que requieren un daemon Docker local; se auto-skipean
  si no hay daemon (`pytest -m docker` para correrlos explícitamente).
- Coverage configurado sobre `src/cron_dok`.

### Frontend (`frontend/tests/`)

- Vitest + Testing Library + jsdom; setup en `tests/setup.ts`, helpers de
  render en `tests/helpers.tsx`. Tests unitarios en `tests/unit/`.

## Seguridad

- **Socket de Docker**: CronDok monta `/var/run/docker.sock`
  (Docker-out-of-Docker) para lanzar jobs — quien controle el proceso tiene
  control de root sobre el host. Está documentado y aceptado: el sandbox se
  aplica a los contenedores de los _jobs_ (efímeros `--rm`, límites de
  memoria/CPU/PIDs, `--network none` por defecto, usuario `nobody` UID 65534,
  solo `/workspace` montado, timeout forzado), no al proceso de CronDok.
- **Secretos**: variables de entorno cifradas en reposo con Fernet
  (`CRONDOK_MASTER_KEY`, autogenerada en `data/.master_key` si falta; sin esa
  clave los valores son irrecuperables). Los valores secretos se enmascaran en
  los logs (`SecretMasker` en el executor). Nunca loguear secretos ni la
  master key.
- **Auth**: sesiones por cookie HttpOnly; contraseñas con argon2 (pwdlib);
  API keys; RBAC (roles admin/viewer) en `services/rbac.py`. Cambio de
  contraseña self-service en `POST /auth/password`: revoca **todas** las
  sesiones del usuario (también el reset de admin en
  `POST /users/{id}/password`). Un usuario con `must_change_password` queda
  confinado por el servidor a `/auth/me` y `/auth/password` (403 en el resto)
  y la SPA le redirige a `/change-password`.
- **Rate limiting**: login y triggers manuales (`CRONDOK_RATE_LIMIT_TRIGGERS`,
  req/min por identidad).
- Pre-commit incluye detect-secrets con baseline; los hallazgos nuevos
  bloquean el commit.

## Variables de entorno

Todas con prefijo `CRONDOK_`, definidas y documentadas en
`backend/src/cron_dok/config.py` (fuente de verdad) y en la tabla del
`README.md` raíz: `MASTER_KEY`, `MAX_CONCURRENT_JOBS`, `LOG_RETENTION_DAYS`,
`RATE_LIMIT_TRIGGERS`, `WEBHOOK_URL`, `HOST_DATA_DIR`, `EXECUTOR_ENABLED`,
`COOKIE_SECURE`, `TRUSTED_PROXIES`, imágenes Docker de los runners, etc. Si
añades una setting, documéntala en ambos sitios.

## Notas operativas

- **Docker-out-of-Docker**: el daemon resuelve los bind mounts contra el
  filesystem del host, no del contenedor de CronDok; por eso existe
  `CRONDOK_HOST_DATA_DIR` (compose lo calcula como `${PWD}/data`) para
  traducir rutas de workspaces.
- Si Docker no está disponible al arrancar (o `CRONDOK_EXECUTOR_ENABLED=false`),
  la API arranca igual con `UnavailableExecutor`, que marca cada ejecución
  como `failed` de forma limpia.
- Backup: `data/crondok.db` (+ `-wal`/`-shm`) y `data/.master_key`.
