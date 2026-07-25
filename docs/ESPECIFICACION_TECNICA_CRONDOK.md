# CronDok - Especificación Técnica y Arquitectura

> **Versión:** 0.2.0  
> **Fecha:** 2026-07-25  
> **Estado:** Borrador (revisado: concurrencia, logs, seguridad y escalabilidad)  
> **Licencia:** MIT (Open Source)

---

## 1. Contexto y Visión

### 1.1. Problema
Los equipos de desarrollo necesitan ejecutar scripts automatizados (ETL, sincronizaciones, backups, tareas de mantenimiento) de forma recurrente. Las soluciones existentes requieren:
- Gestión de infraestructura compleja (bases de datos, servidores, schedulers).
- Hardcodear credenciales y configuraciones sensibles dentro del código.
- Conocimientos avanzados de Linux/Cron para configurar tareas.
- No ofrecen una experiencia unificada de creación, monitoreo y ejecución manual.

### 1.2. Visión
Construir una plataforma **self-hosted**, **open source** y **auto-contenida** que permita a cualquier usuario o equipo:
- Crear **Proyectos** que agrupen **Runners** (jobs/tareas).
- Definir scripts en múltiples lenguajes (Bash, Python, Node.js) con su propia expresión cron.
- Gestionar **variables de entorno** de forma segura, inyectadas en tiempo de ejecución sin hardcodear.
- Ejecutar jobs de forma programada (cron) o bajo demanda vía API.
- Monitorear ejecuciones, logs y métricas desde una interfaz web unificada.
- Levantar toda la plataforma con **un solo comando** (`docker-compose up`).

### 1.3. Filosofía del Proyecto
- **Zero-config database:** SQLite como motor principal. Un solo archivo, cero mantenimiento.
- **Pocos servicios:** Sin Redis, sin Postgres, sin brokers en el MVP. Cada servicio extra erosiona el diferencial "un solo comando".
- **Seguridad por diseño:** Cada ejecución corre en un contenedor Docker efímero aislado.
- **API-first:** Toda la funcionalidad expuesta vía REST, consumible por la UI o integraciones externas.
- **Escalable por diseño, no por infraestructura:** Las decisiones de concurrencia y almacenamiento (sección 6) permiten crecer sin reescribir. Postgres/Redis/Swarm quedan como ruta documentada (sección 10), no como dependencia.
- **Pragmatismo arquitectónico:** Separación de capas y puertos solo en los puntos de cambio reales (sección 4). Sin ceremonia innecesaria.

---

## 2. Objetivos

### 2.1. Objetivo General
Desarrollar un scheduler de tareas programadas y bajo demanda, con gestión de variables de entorno, ejecución sandboxed y panel de control web, empaquetado como una aplicación monolítica auto-contenida.

### 2.2. Objetivos Específicos
1. Permitir la creación de proyectos y runners con expresiones cron configurables.
2. Proveer un sistema de variables de entorno jerárquico (proyecto → runner) con almacenamiento encriptado.
3. Ejecutar scripts en contenedores Docker aislados con límites de recursos (CPU, memoria, red, tiempo) y **concurrencia acotada**.
4. Garantizar la **integridad de datos bajo concurrencia**: WAL, escritor único para ejecuciones y transacciones atómicas.
5. Almacenar **logs fuera de la base de datos** (archivos), manteniendo SQLite pequeño y rápido a largo plazo.
6. Ofrecer una API REST completa para triggers manuales y consulta de estado.
7. Proveer una interfaz web (React) para gestión visual de proyectos, runners, variables y monitoreo de ejecuciones.
8. Garantizar calidad de código mediante pre-commit hooks y pipeline de CI.
9. Mantener el proceso **stateless**: el scheduler se rehidrata desde la DB al arrancar, permitiendo reinicios y futura replicación sin pérdida.

---

## 3. Stack Tecnológico

### 3.1. Backend
| Tecnología | Versión | Propósito |
|------------|---------|-----------|
| **Python** | 3.12+ | Lenguaje principal del backend |
| **FastAPI** | ^0.115 | Framework web async, auto-documentación OpenAPI |
| **Poetry** | ^1.8 | Gestión de dependencias y empaquetado |
| **APScheduler** | ^3.10 | Motor de scheduling (jobstore en memoria; se rehidrata desde DB al arrancar) |
| **SQLAlchemy** | ^2.0 (async) | ORM y Unit of Work (transacciones atómicas) sobre SQLite |
| **Alembic** | ^1.13 | Migraciones de base de datos |
| **Pydantic** | ^2.8 | Validación de datos y settings |
| **Pydantic-Settings** | ^2.3 | Configuración vía variables de entorno y archivos |
| **python-docker** | ^7.1 | Cliente Docker para orquestar contenedores de ejecución |
| **cryptography** | ^42.0 | Encriptación de secrets (variables de entorno) |
| **pwdlib[argon2]** | ^0.2 | Hash de contraseñas de usuarios (Argon2id) |
| **pytest** | ^8.2 | Framework de testing |
| **pytest-asyncio** | ^0.23 | Soporte async para tests |
| **httpx** | ^0.27 | Cliente HTTP para tests |
| **ruff** | ^0.5 | Linter y formatter (reemplaza flake8, black, isort) |
| **mypy** | ^1.11 | Type checking estático |
| **pre-commit** | ^3.7 | Hooks de git para validaciones locales |

> **Decisión de ORM (por qué SQLAlchemy 2.0 async y no otra cosa):**
> - `AsyncSession` implementa el patrón **Unit of Work**: un conjunto de operaciones se confirma o revierte de forma atómica (`commit`/`rollback`), evitando escrituras parciales.
> - Permite configurar los pragmas de SQLite críticos para concurrencia (`journal_mode=WAL`, `busy_timeout`, `synchronous=NORMAL`) vía el evento `connect` del engine.
> - Portabilidad real a PostgreSQL: mismo código, otro dialecto. Alternativas como SQLModel o Tortoise darían menos control sobre transacciones y concurrencia, no más.

> **Autenticación:** Se descarta JWT. Tanto sesiones de usuario como API keys usan **tokens opacos** (`secrets.token_urlsafe`) almacenados hasheados (SHA-256) en DB, con revocación inmediata. Contraseñas con Argon2id (`pwdlib`). Detalle completo en sección 9.4.

### 3.2. Frontend
| Tecnología | Versión | Propósito |
|------------|---------|-----------|
| **React** | ^18.3 | Librería UI |
| **TypeScript** | ^5.5 | Tipado estático en el frontend |
| **Vite** | ^5.3 | Build tool y dev server |
| **Tailwind CSS** | ^3.4 | Estilos utilitarios |
| **shadcn/ui** | ^0.8 | Componentes UI accesibles y personalizables |
| **TanStack Query** | ^5.51 | Gestión de estado server-side (caching, sync) |
| **React Router** | ^6.25 | Navegación SPA |
| **Axios** | ^1.7 | Cliente HTTP |
| **Zod** | ^3.23 | Validación de esquemas (comparte contratos con backend) |
| **Vitest** | ^2.0 | Testing unitario |
| **ESLint** | ^8.57 | Linter JS/TS |
| **Prettier** | ^3.3 | Formatter |

> **Playwright (E2E) se mueve a Fase 5+** (post-MVP). El MVP se valida con tests unitarios y de integración.

### 3.3. Infraestructura y DevOps
| Tecnología | Propósito |
|------------|-----------|
| **Docker** | Contenerización del backend, frontend (build) y ejecución de jobs |
| **Docker Compose** | Orquestación local de un solo comando |
| **GitHub Actions** | CI/CD: lint, test, build, release |
| **Traefik** | Reverse proxy y SSL automático (futuro) |
| **SQLite (WAL)** | Base de datos embebida, archivo único, modo WAL obligatorio |

---

## 4. Arquitectura: Capas con Puertos en los Puntos de Cambio

Se adopta una **arquitectura en capas pragmática**, inspirada en Hexagonal pero sin su ceremonia completa. El principio rector es el mismo (las dependencias apuntan hacia adentro; el dominio no conoce FastAPI, SQLAlchemy ni Docker), pero se evita el patrón "una clase por caso de uso": los casos de uso son **servicios de aplicación** con métodos, y los **puertos (interfaces) solo se definen donde existe un punto de cambio real**:

| Puerto | Implementación MVP | Implementación futura |
|--------|--------------------|-----------------------|
| `JobExecutor` | Docker local | Docker Swarm / Kubernetes |
| `LogStore` | Archivos locales | S3 / almacenamiento remoto |
| Repositorios (ligero) | SQLite vía SQLAlchemy | PostgreSQL (mismo ORM, otro dialecto) |

Los beneficios buscados (testabilidad, intercambiabilidad) se conservan; se elimina la indirección que no paga (DTOs por caso de uso, puertos para cada operación CRUD).

### 4.1. Capas

```
┌──────────────────────────────────────────────────────────────┐
│                     ADAPTERS DE ENTRADA                      │
│   FastAPI Routers          APScheduler Trigger               │
│        │                        │                            │
│        └───────────┬────────────┘                            │
│                    ▼                                         │
│            SERVICIOS DE APLICACIÓN  (casos de uso)           │
│   ProjectService · RunnerService · ExecutionService          │
│   EnvVarService · SchedulerService · ExecutionQueue          │
│                    │                                         │
│        ┌───────────┴────────────┐                            │
│        ▼                        ▼                            │
│     DOMINIO (puro)         PORTS (interfaces)                │
│   Entities, Value          ProjectRepository ...             │
│   Objects, reglas          JobExecutor · LogStore            │
│                                   │                          │
│                                   ▼                          │
│                     ADAPTERS DE SALIDA                       │
│   SQLite Repositories · Docker Executor · FileLogStore       │
│   EncryptionService · ApiKeyService                          │
└──────────────────────────────────────────────────────────────┘
```

### 4.2. Definición de Capas

#### 4.2.1. Dominio (`/domain`)
Entidades, value objects y reglas de negocio puras. **Sin dependencias externas** (ni siquiera Pydantic).

```python
# domain/entities/runner.py
from dataclasses import dataclass
from domain.value_objects.cron_expression import CronExpression
from domain.value_objects.resource_limits import ResourceLimits

@dataclass
class Runner:
    id: int | None
    project_id: int
    name: str
    script_content: str
    language: str  # python, bash, node
    cron_expression: CronExpression
    resource_limits: ResourceLimits
    is_enabled: bool
    timeout_seconds: int = 300
    on_overlap: str = "skip"  # skip | queue | kill_previous
```

#### 4.2.2. Puertos (`/ports`)
Interfaces abstractas solo en los puntos de cambio reales.

```python
# ports/executors/job_executor.py
from abc import ABC, abstractmethod

class JobExecutor(ABC):
    @abstractmethod
    async def execute(self, runner: Runner, env_vars: dict[str, str],
                      log_sink: LogSink) -> ExecutionResult: ...
```

```python
# ports/logs/log_store.py
from abc import ABC, abstractmethod

class LogStore(ABC):
    @abstractmethod
    async def open_writer(self, execution_id: int) -> LogSink: ...
    @abstractmethod
    async def read(self, execution_id: int, offset: int = 0) -> tuple[str, int]: ...
    @abstractmethod
    async def delete(self, execution_id: int) -> None: ...
```

```python
# ports/repositories/project_repository.py
class ProjectRepository(ABC):
    @abstractmethod
    async def save(self, project: Project) -> Project: ...
    @abstractmethod
    async def get_by_id(self, project_id: int) -> Project | None: ...
    @abstractmethod
    async def list_all(self) -> list[Project]: ...
```

#### 4.2.3. Servicios de Aplicación (`/services`)
Orquestan la lógica de negocio. No conocen HTTP, SQL ni Docker. Las operaciones multi-paso se envuelven en **transacciones** a través de una unidad de trabajo (ver 6.2).

```python
# services/runner_service.py
class RunnerService:
    def __init__(self, uow: UnitOfWork, scheduler: SchedulerService):
        self.uow = uow
        self.scheduler = scheduler

    async def create(self, *, project_id: int, name: str, ...) -> Runner:
        async with self.uow:  # transacción: commit al salir, rollback si hay excepción
            project = await self.uow.projects.get_by_id(project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            runner = await self.uow.runners.save(Runner(...))
        await self.scheduler.register(runner)
        return runner
```

#### 4.2.4. Adaptadores de Entrada (`/adapters/input`)
- **REST (FastAPI):** Routers que validan con Pydantic y llaman a servicios. La inyección usa `Depends` de FastAPI **solo en esta capa** (es el idiomático; el dominio nunca lo conoce).
- **Scheduler (APScheduler):** Escucha eventos de tiempo y encola ejecuciones en `ExecutionQueue`.

#### 4.2.5. Adaptadores de Salida (`/adapters/output`)
- **SQLite Repositories:** Implementaciones con SQLAlchemy 2.0 async.
- **Docker Executor:** Implementación de `JobExecutor` con `docker-py` (llamadas bloqueantes envueltas en `asyncio.to_thread`).
- **File LogStore:** Implementación de `LogStore` sobre `data/logs/<execution_id>.log`.
- **Encryption / API Key services:** Fernet y hashing de tokens opacos.

### 4.3. Regla de Dependencia
> **Las dependencias apuntan siempre hacia adentro.** Los adaptadores dependen de servicios, puertos y dominio. El dominio no depende de nada externo.

---

## 5. Estructura de Carpetas

```
cron-dok/
├── .github/
│   └── workflows/
│       ├── ci-backend.yml          # Lint, type-check, test, build
│       ├── ci-frontend.yml         # Lint, type-check, test, build
│       └── release.yml             # Docker build & push, changelog
├── .pre-commit-config.yaml
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── data/                           # Volumen persistente
│   ├── crondok.db                  # SQLite (WAL: crondok.db-wal, crondok.db-shm)
│   └── logs/                       # Logs de ejecuciones (<execution_id>.log)
│       └── .gitkeep
├── backend/
│   ├── pyproject.toml
│   ├── poetry.lock
│   ├── alembic.ini
│   ├── alembic/
│   ├── tests/
│   │   ├── unit/                   # Dominio y servicios (repos en memoria)
│   │   ├── integration/            # Adaptadores (DB real, Docker)
│   │   └── conftest.py
│   └── src/
│       └── cron_dok/
│           ├── __init__.py
│           ├── main.py             # FastAPI app + static mount + lifespan
│           ├── config.py           # Pydantic-Settings
│           ├── domain/
│           │   ├── entities/       # project.py, runner.py, execution.py, env_var.py
│           │   ├── value_objects/  # cron_expression.py, resource_limits.py, execution_result.py
│           │   └── services/       # cron_validator.py (reglas puras)
│           ├── ports/
│           │   ├── repositories/   # project, runner, execution, env_var
│           │   ├── executors/      # job_executor.py
│           │   └── logs/           # log_store.py
│           ├── services/           # Casos de uso (application services)
│           │   ├── project_service.py
│           │   ├── runner_service.py
│           │   ├── execution_service.py
│           │   ├── execution_queue.py    # Cola en memoria + worker único escritor
│           │   ├── env_var_service.py
│           │   └── scheduler_service.py  # Registro/rehidratación de jobs
│           ├── adapters/
│           │   ├── input/
│           │   │   ├── http/
│           │   │   │   ├── dependencies.py   # Wiring con Depends (solo aquí)
│           │   │   ├── routers/              # projects, runners, executions, env_vars, triggers
│           │   │   └── schemas/              # Pydantic request/response
│           │   │   └── scheduler/
│           │   │       ├── scheduler_adapter.py
│           │   │       └── job_listener.py
│           │   └── output/
│           │       ├── persistence/
│           │       │   ├── database.py       # Engine async + pragmas WAL + UnitOfWork
│           │       │   ├── models/           # ORM models (project, runner, execution, env_var)
│           │       │   └── repositories/     # sqlite_*_repository.py (incluye env_var)
│           │       ├── executor/
│           │       │   └── docker_executor.py
│           │       ├── logs/
│           │       │   └── file_log_store.py
│           │       └── security/
│           │           ├── encryption_service.py   # Fernet
│           │           └── api_key_service.py      # Tokens opacos hasheados
│           └── infrastructure/
│               ├── logging.py
│               └── exceptions.py
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── .eslintrc.cjs
    ├── .prettierrc
    ├── vitest.config.ts
    ├── tests/unit/
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── router.tsx
        ├── api/                    # Cliente HTTP + interceptores
        ├── components/             # Componentes reutilizables (shadcn)
        ├── features/               # projects / runners / executions / env-vars
        ├── hooks/
        ├── types/                  # Zod schemas
        └── utils/
```

---

## 6. Concurrencia y Persistencia (decisiones críticas)

Esta sección recoge las decisiones que hacen al MVP **correcto bajo concurrencia** y **sostenible en el tiempo** sin infraestructura adicional.

### 6.1. SQLite en modo WAL
El engine se crea con pragmas aplicados en el evento `connect`:

```python
PRAGMA journal_mode = WAL;      -- lectores no bloquean al escritor
PRAGMA busy_timeout = 5000;     -- reintenta en vez de "database is locked"
PRAGMA synchronous = NORMAL;    -- durabilidad suficiente con WAL, más rápido
PRAGMA foreign_keys = ON;
```

Con WAL, SQLite soporta cómodamente la carga de CronDok (metadatos pequeños, escrituras cortas).

### 6.2. Transacciones atómicas (Unit of Work)
- Toda operación de escritura multi-paso se ejecuta dentro de `async with uow:` (commit al salir, rollback ante excepción). **Nunca** se hacen commits parciales manuales.
- La `AsyncSession` de SQLAlchemy actúa como Unit of Work; el adaptador de persistencia la envuelve en una clase `UnitOfWork` que expone los repositorios.

### 6.3. Escritor único para ejecuciones
El estado de las ejecuciones es lo que más se escribe y desde más lugares (scheduler, triggers manuales, finalización de contenedores). Para eliminar contención por construcción:

- Los productores (scheduler, API, workers de Docker) **no escriben directo**: publican eventos (`created`, `started`, `finished`, `log_chunk`) en una `asyncio.Queue` interna (`ExecutionQueue`).
- Un **único consumidor async** drena la cola y persiste en orden. Una sola tarea escribe ejecuciones → no hay `database is locked` posible en este flujo.

### 6.4. Logs fuera de la base de datos
- Los logs de cada ejecución van a **archivos**: `data/logs/<execution_id>.log`.
- La tabla `executions` guarda solo metadatos: `status`, `trigger_type`, `started_at`, `finished_at`, `exit_code`, `duration_ms`, `log_path`, `log_size_bytes`.
- La UI consulta logs vía `GET /api/v1/executions/{id}/logs?offset=N` (lectura incremental del archivo, estilo tail con polling). WebSocket/SSE queda para Fase 5+.
- **Retención:** tarea de mantenimiento (ella misma un runner del sistema) que purga ejecuciones y logs por antigüidad/cantidad configurable (`CRONDOK_LOG_RETENTION_DAYS`, default 30).

### 6.5. Concurrencia acotada del executor
- Un `asyncio.Semaphore` global limita contenedores simultáneos: `CRONDOK_MAX_CONCURRENT_JOBS` (default 4).
- Los triggers que exceden el límite quedan encolados (estado `queued`), no rechazados.
- **Política de solapamiento por runner** (`on_overlap`): si el cron dispara un runner cuya ejecución anterior sigue viva:
  - `skip` (default): se descarta el disparo y se registra como `skipped`.
  - `queue`: se encola para cuando termine.
  - `kill_previous`: se mata el contenedor anterior y se inicia el nuevo.
- APScheduler se configura con `max_instances=1` y `coalesce=True` por job como segunda línea de defensa.

---

## 7. Ciclo de Vida del Scheduler (proceso stateless)

- APScheduler usa **jobstore en memoria**. No persiste jobs.
- Al arrancar la app (lifespan de FastAPI): leer todos los runners `is_enabled=true` de la DB y registrarlos. Esto se llama **rehidratación**.
- Toda operación que cambia un runner (create/update/enable/disable/delete) actualiza DB y scheduler de forma consistente (DB primero, scheduler después).
- Consecuencia: el proceso es **stateless** — reiniciar el contenedor no pierde nada, y es la precondición para escalar a múltiples nodos en el futuro.

---

## 8. Validaciones y Calidad de Código

### 8.1. Pre-commit Hooks (`.pre-commit-config.yaml`)

```yaml
# Backend
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.5.0
  hooks:
    - id: ruff
      args: [--fix]
    - id: ruff-format

- repo: https://github.com/pre-commit/mirrors-mypy
  rev: v1.11.0
  hooks:
    - id: mypy

# Frontend
- repo: https://github.com/pre-commit/mirrors-eslint
  rev: v8.57.0
  hooks:
    - id: eslint
      files: \.(ts|tsx)$

- repo: https://github.com/pre-commit/mirrors-prettier
  rev: v3.3.0
  hooks:
    - id: prettier
      files: \.(ts|tsx|json|css|md)$

# General
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v4.6.0
  hooks:
    - id: trailing-whitespace
    - id: end-of-file-fixer
    - id: check-yaml
    - id: check-json
    - id: check-added-large-files

# Secrets
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.5.0
  hooks:
    - id: detect-secrets
```

### 8.2. CI/CD Pipeline (GitHub Actions)

#### Backend CI (`ci-backend.yml`)
```yaml
name: CI Backend
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install poetry
      - run: poetry install --with dev
      - run: poetry run ruff check .
      - run: poetry run ruff format --check .
      - run: poetry run mypy .
      - run: poetry run pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v4
```

#### Frontend CI (`ci-frontend.yml`)
```yaml
name: CI Frontend
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npm run lint
      - run: npm run type-check
      - run: npm run test:unit
      - run: npm run build
```

### 8.3. Reglas de Validación

| Regla | Backend | Frontend | Descripción |
|-------|---------|----------|-------------|
| **Type Safety** | `mypy` strict en `domain/` y `services/`; modo estándar en `adapters/` | `tsc --noEmit` | Strict donde hay lógica de negocio; pragmático en bordes (SQLAlchemy/docker-py generan ruido) |
| **Linting** | `ruff check` | `eslint` | Sin warnings en CI |
| **Formatting** | `ruff format` | `prettier` | Formato uniforme |
| **Tests** | `pytest` (cobertura >80% en `domain/` y `services/`) | `vitest` | Servicios testeados con repositorios en memoria |
| **Commits** | Conventional Commits | Conventional Commits | `feat:`, `fix:`, `refactor:`, `docs:` |
| **Secrets** | `detect-secrets` | `detect-secrets` | Escaneo de credenciales hardcodeadas |

### 8.4. Convenciones de Código

#### Backend (Python)
- **PEP 8** via Ruff.
- **Type hints obligatorios** en funciones públicas.
- **Docstrings** en Google Style para módulos y clases públicas.
- `Depends` de FastAPI **solo** en `adapters/input/http`. Servicios y dominio reciben dependencias por constructor.
- **Async-first:** todo I/O (DB, Docker, filesystem) es async. Llamadas bloqueantes (docker-py) se envuelven en `asyncio.to_thread`.

#### Frontend (TypeScript/React)
- **Functional components** con hooks.
- **Custom hooks** para lógica de negocio.
- **Zod schemas** para validación de formularios.
- **TanStack Query** para todo fetching (no `useEffect` directo para APIs).

---

## 9. Seguridad

### 9.1. Variables de Entorno (Secrets)
- **Encriptación en reposo:** Fernet (AES-128 CBC + HMAC) con clave maestra del sistema (`CRONDOK_MASTER_KEY`). Si la variable no está definida al primer arranque, se genera y se persiste en `data/.master_key` (permisos 600) con advertencia en logs.
- **Inyección en ejecución:** Las variables se descifran en memoria y se pasan al contenedor como env vars nativas. Nunca se escriben en disco ni en logs (el executor filtra valores de secrets del output capturado).
- **UI:** Los secrets se muestran como `••••••••`. Solo se permite rotar, no leer.
- **Blacklist:** No permitir keys que sobrescriban variables del sistema (`PATH`, `LD_PRELOAD`, `HOME`).

### 9.2. Ejecución de Scripts (Sandboxing)
- **Contenedor efímero por ejecución:** `docker run --rm`.
- **Límites de recursos:** `--memory`, `--cpus`, `--pids-limit` por runner (`ResourceLimits`).
- **Red:** `--network none` por defecto. Solo habilitar si el usuario lo solicita explícitamente por runner.
- **Filesystem:** Volumen temporal montado en `/workspace`. Solo lectura/escritura ahí.
- **Timeout:** Kill forzado después de `timeout_seconds`.
- **Usuario no-root:** Contenedores corren como `nobody` (UID 65534).

### 9.3. El riesgo del Docker socket (reconocido explícitamente)
Para ejecutar jobs, CronDok monta `/var/run/docker.sock` en su propio contenedor (patrón Docker-out-of-Docker). Esto implica:

> **Quien controle el proceso de CronDok tiene control de root sobre el host.** Un escape de sandbox o una vulnerabilidad en la API equivale a compromiso total del host.

Mitigaciones obligatorias y documentadas:
- Los contenedores de jobs se crean **siempre** con las restricciones de 9.2; un job no puede montar volúmenes arbitrarios ni el socket (el executor no lo permite por diseño, no por configuración).
- La API exige autenticación incluso en instalaciones locales (API key de administrador generada en el primer arranque).
- Documentar en el README que CronDok debe correr en un host/VM dedicado o con Docker rootless, y mencionar la opción futura de un socket proxy con allowlist (ej. `wolflu05/docker-socket-proxy`) que restrinja los endpoints de la API de Docker a solo `containers/*`.

### 9.4. Autenticación y Autorización

CronDok tiene **dos mecanismos de autenticación** sobre la misma base (tokens opacos, nada de JWT):

#### 9.4.1. Usuarios y sesiones (acceso a la UI)
- **Multi-usuario con roles:** tabla `users` (`id, username, password_hash, role, is_active, created_at`). Sin login, la UI y la API son inaccesibles — no existe modo "abierto".
- **Roles:** `admin` (todo, incl. gestión de usuarios y API keys), `operator` (CRUD de proyectos/runners + ejecutar triggers), `viewer` (solo lectura). Se mapean a los mismos scopes de 9.4.2.
- **Contraseñas:** hash con **Argon2id** (vía `pwdlib`). Mínimo 12 caracteres.
- **Sesiones:** token opaco (`secrets.token_urlsafe(32)`) guardado hasheado (SHA-256) en tabla `sessions` (`token_hash, user_id, expires_at, created_at, ip`), entregado al navegador como **cookie HttpOnly + SameSite=Lax** (y `Secure` tras HTTPS). Expiración de 7 días con rotación. Logout = borrar la fila (revocación inmediata).
- **Primer arranque:** si no existe ningún usuario, se crea `admin` con contraseña aleatoria impresa **una sola vez** en los logs del contenedor (patrón Gitea/Portainer), con flag `must_change_password=true`.

#### 9.4.2. API keys (integraciones externas)
- **API keys opacas:** `crondok_<random>` generadas con `secrets.token_urlsafe(32)`. En DB se guarda `sha256(token)` + scopes + `created_at` + `revoked_at`. Revocación inmediata. No se usa JWT: para una app self-hosted, los tokens opacos son más simples y revocables.
- **Scopes:** `runners:read`, `runners:execute`, `admin`.
- Cabecera `Authorization: Bearer crondok_...`. El middleware acepta **sesión (cookie) o API key (header)** y resuelve el mismo contexto de autorización.

#### 9.4.3. Reglas comunes
- **Middleware de FastAPI** que protege todos los endpoints salvo `POST /api/v1/auth/login`, `GET /api/v1/health` y los estáticos del frontend.
- **Rate limiting:** 100 requests/minuto por API key en endpoints de trigger; 10 intentos/minuto por IP en `/auth/login` (anti fuerza bruta).
- **CORS:** Configurable vía variables de entorno; por defecto mismo origen (el backend sirve el frontend).

---

## 10. Ruta de Escalado (documentada, no construida)

El MVP escala a cientos de runners y miles de ejecuciones diarias con las decisiones de la sección 6. Cuando eso no baste:

| Cuando duela... | El paso es... | Por qué es barato |
|---|---|---|
| SQLite se queda corto (multi-nodo, muchos escritores concurrentes) | **PostgreSQL** | SQLAlchemy + Alembic: cambiar dialecto y connection string; los repositorios no cambian |
| Ejecutar en varias máquinas | **SwarmExecutor / K8sExecutor** | Implementan `JobExecutor`; el resto del sistema no se entera |
| Cola distribuida de triggers / caché | **Redis (RQ/Celery)** | `ExecutionQueue` ya es un puerto conceptual: la cola en memoria se reemplaza por una distribuida |
| Logs centralizados | **S3LogStore** | Implementa `LogStore` |
| Métricas y alertas | Exportador Prometheus | Lectura sobre la tabla `executions` (metadatos ligeros) |

> Regla: ninguna de estas dependencias se introduce antes de que exista el dolor que justifica su costo operativo.

---

## 11. Roadmap

### Fase 0: Fundamentos (Semanas 1-2)
- [ ] Scaffold del proyecto (Poetry, Vite, pre-commit, CI).
- [ ] Engine SQLite con pragmas WAL + `UnitOfWork` (6.1, 6.2).
- [ ] Dominio base: `Project`, `Runner`, `Execution`, `EnvVar` + value objects.
- [ ] Puertos: repositorios, `JobExecutor`, `LogStore`.
- [ ] Adaptador SQLite: modelos, repositorios, Alembic.

### Fase 1: Core Backend (Semanas 3-5)
- [ ] Servicios: CRUD de proyectos y runners.
- [ ] `ExecutionQueue` (escritor único) + `FileLogStore` (6.3, 6.4).
- [ ] Docker Executor con semáforo de concurrencia y política `on_overlap` (6.5).
- [ ] APScheduler: rehidratación al arranque + registro dinámico (sección 7).
- [ ] **Auth core: usuarios con roles, sesiones con cookie HttpOnly, middleware de protección, bootstrap del admin en el primer arranque (9.4.1, 9.4.3).**
- [ ] API REST completa con FastAPI (incluye endpoint de logs con offset).
- [ ] Tests unitarios e integración (>80% en dominio y servicios).

### Fase 2: Frontend MVP (Semanas 6-8)
- [ ] **Pantalla de login + guarda de rutas (redirect a /login sin sesión) y gestión de usuarios para admin.**
- [ ] UI: Dashboard de proyectos y runners.
- [ ] Formularios: Crear/editar runners con editor de script.
- [ ] Gestión de variables de entorno (tabla con ocultamiento de secrets).
- [ ] Panel de ejecuciones: lista, estado, visor de logs (polling con offset).
- [ ] Trigger manual desde la UI.

### Fase 3: API y Seguridad (Semana 9)
- [ ] API keys opacas con scopes y revocación (9.4).
- [ ] Endpoint `POST /api/v1/triggers/{runner_id}` con rate limiting.
- [ ] Tarea de retención de logs/ejecuciones (6.4).
- [ ] Webhook de notificación en fallo.

### Fase 4: Dockerización y Release (Semana 10)
- [ ] Dockerfile multi-stage (backend + frontend build).
- [ ] Docker Compose con volumen persistente + documentación del riesgo del socket (9.3).
- [ ] Documentación de despliegue.
- [ ] Release v0.1.0 en GitHub.

### Fase 5+: Futuro
- [ ] WebSocket/SSE para logs en tiempo real.
- [ ] Playwright E2E.
- [ ] Docker Swarm support (`SwarmExecutor`).
- [ ] Templates de scripts reutilizables.
- [ ] Métricas (Prometheus) y alertas avanzadas.
- [ ] Backup automático de SQLite a S3.
- [ ] Socket proxy con allowlist para Docker API.
- [ ] PostgreSQL como opción de despliegue documentada.

---

## 12. Glosario

| Término | Definición |
|---------|-----------|
| **Runner** | Unidad ejecutable que contiene un script, su cron y su configuración. |
| **Project** | Contenedor lógico que agrupa runners, variables de entorno y permisos. |
| **Execution** | Instancia concreta de un runner ejecutado (programada o manualmente). |
| **Env Var** | Variable de entorno asociada a un proyecto o runner, almacenada encriptada. |
| **Port** | Interfaz abstracta en un punto de cambio real (`JobExecutor`, `LogStore`, repositorios). |
| **Adapter** | Implementación concreta de un port. |
| **Service** | Orquestador de casos de uso que coordina dominio y puertos. |
| **Unit of Work** | Patrón que agrupa operaciones de escritura en una transacción atómica (SQLAlchemy `AsyncSession`). |
| **WAL** | Write-Ahead Logging: modo de SQLite que permite lectores concurrentes con un escritor. |
| **Rehidratación** | Registro de jobs en APScheduler desde la DB al arrancar, haciendo el proceso stateless. |

---

## 13. Referencias

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 - Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [SQLite WAL mode](https://www.sqlite.org/wal.html)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [Poetry Documentation](https://python-poetry.org/docs/)
- [Hexagonal Architecture (Alistair Cockburn)](https://alistair.cockburn.us/hexagonal-architecture/)
- [Dokploy - Self-Hosted PaaS](https://dokploy.com/)

---

*Documento generado para el proyecto CronDok. Sujeto a revisiones conforme avance el desarrollo.*
