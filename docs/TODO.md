# CronDok - Plan del MVP

> Registro de avance del MVP (v0.1.0), basado en el roadmap de
> `docs/ESPECIFICACION_TECNICA_CRONDOK.md` (v0.2.0).
>
> **Leyenda:** `[ ]` pendiente · `[~]` en progreso · `[x]` hecho
>
> **Regla de avance (puerta de calidad):** ninguna fase se marca como completada ni se
> inicia la siguiente hasta que **todos los tests de la fase actual pasen verde**
> (backend y frontend según aplique), junto con lint y type-check.
>
> **Última actualización:** 2026-07-25 (Fase 4 + features post-MVP: constructor de horarios, dependencias por runner)

---

## Estado General

| Fase | Nombre | Estado | Progreso |
|------|--------|--------|----------|
| 0 | Fundamentos | Completada ✅ | 8/8 |
| 1 | Core Backend | Completada ✅ | 9/9 |
| 2 | Frontend MVP | Completada ✅ | 6/6 |
| 3 | API y Seguridad | Completada ✅ | 4/4 |
| 4 | Dockerización y Release | En progreso | 3/4 |

---

## Fase 0: Fundamentos (Semanas 1-2)

### Scaffold
- [x] 0.1 Inicializar backend con Poetry (`backend/pyproject.toml`, deps del stack)
- [x] 0.2 Inicializar frontend con Vite + React + TS + Tailwind + shadcn/ui
- [x] 0.3 Configurar pre-commit hooks (ruff, mypy, eslint, prettier, detect-secrets)
- [x] 0.4 Configurar CI: `ci-backend.yml` y `ci-frontend.yml` en GitHub Actions

### Persistencia base
- [x] 0.5 Engine SQLite async con pragmas WAL + `busy_timeout` + `synchronous=NORMAL` (spec 6.1)
- [x] 0.6 `UnitOfWork` envolviendo `AsyncSession` (transacciones atómicas, spec 6.2)

### Dominio y puertos
- [x] 0.7 Entidades `Project`, `Runner`, `Execution`, `EnvVar` + value objects (`CronExpression`, `ResourceLimits`, `ExecutionResult`)
- [x] 0.8 Puertos: repositorios, `JobExecutor`, `LogStore` + modelos SQLAlchemy, repositorios SQLite y primera migración Alembic

---

## Fase 1: Core Backend (Semanas 3-5)

- [x] 1.1 Servicios: CRUD de proyectos (`ProjectService`) y runners (`RunnerService`)
- [x] 1.2 `ExecutionQueue`: cola en memoria + consumidor único escritor (spec 6.3)
- [x] 1.3 `FileLogStore`: logs en `data/logs/<execution_id>.log` (spec 6.4)
- [x] 1.4 `DockerExecutor`: contenedores efímeros con límites, semáforo de concurrencia (`CRONDOK_MAX_CONCURRENT_JOBS`) y política `on_overlap` (spec 6.5, 9.2)
- [x] 1.5 `SchedulerService`: rehidratación al arranque + registro dinámico de jobs (spec 7)
- [x] 1.6 API REST completa: routers de projects, runners, executions, env_vars, triggers + endpoint de logs con offset
- [x] 1.7 `EncryptionService` (Fernet) + gestión de `CRONDOK_MASTER_KEY` (spec 9.1)
- [x] 1.8 Tests unitarios e integración (>80% en `domain/` y `services/`)
- [x] 1.9 **Auth core**: entidades `User`/`Session`, hash Argon2id (`pwdlib`), login/logout con cookie HttpOnly, middleware de protección de endpoints, bootstrap del admin en el primer arranque (spec 9.4.1, 9.4.3)

---

## Fase 2: Frontend MVP (Semanas 6-8)

- [x] 2.1 **Pantalla de login** + guarda de rutas (redirect a `/login` sin sesión) y página de gestión de usuarios para admin (spec 9.4.1)
- [x] 2.2 Dashboard de proyectos y runners
- [x] 2.3 Formularios de crear/editar runners con editor de script
- [x] 2.4 Gestión de variables de entorno (tabla con secrets ocultos, solo rotación)
- [x] 2.5 Panel de ejecuciones: lista, estado y visor de logs (polling con offset)
- [x] 2.6 Trigger manual desde la UI

---

## Fase 3: API y Seguridad (Semana 9)

- [x] 3.1 API keys opacas hasheadas (SHA-256) con scopes y revocación (spec 9.4) + UI `/api-keys` (admin)
- [x] 3.2 `POST /api/v1/triggers/{runner_id}` con rate limiting (100 req/min por identidad)
- [x] 3.3 Tarea de retención de logs/ejecuciones (`CRONDOK_LOG_RETENTION_DAYS`, spec 6.4)
- [x] 3.4 Webhook de notificación en fallo de ejecución

---

## Fase 4: Dockerización y Release (Semana 10)

- [x] 4.1 Dockerfile multi-stage (backend + build de frontend) + fallback SPA servido por FastAPI
- [x] 4.2 Docker Compose con volumen persistente (`data/`)
- [x] 4.3 Documentación de despliegue + advertencia del riesgo del Docker socket (spec 9.3)
- [ ] 4.4 Release v0.1.0 en GitHub (bloqueada: repo sin remoto; requiere confirmación del usuario)

---

## Post-MVP (Fase 5+, no comprometido)

- WebSocket/SSE para logs en tiempo real
- Playwright E2E
- Docker Swarm support (`SwarmExecutor`)
- Templates de scripts reutilizables
- Métricas (Prometheus) y alertas avanzadas
- Backup automático de SQLite a S3
- Socket proxy con allowlist para Docker API
- PostgreSQL como opción de despliegue documentada

---

## Registro de Cambios

| Fecha | Cambio |
|-------|--------|
| 2026-07-25 | Creación del plan. Especificación técnica v0.2.0 aprobada como base. |
| 2026-07-25 | Regla permanente: puerta de calidad — no se avanza de fase sin tests/lint/type-check verdes. |
| 2026-07-25 | **Fase 0 completada.** Backend Poetry (dominio, puertos, SQLite WAL, UnitOfWork, Alembic), frontend Vite/React/Tailwind/shadcn, pre-commit (11 hooks) y CI con path filters. Puerta de calidad verificada: 58 tests backend verdes (89% cov, dominio 100%), type-check/lint/build frontend verdes, `pre-commit run --all-files` 11/11 passed. |
| 2026-07-25 | Spec v0.2.0 → añadida **autenticación multi-usuario con roles** (9.4): usuarios + sesiones con cookie HttpOnly (Argon2id, tokens opacos), middleware de protección, bootstrap de admin en primer arranque. Nuevas tareas 1.9 y 2.1; `pwdlib[argon2]` al stack. |
| 2026-07-25 | Commit inicial de Fase 0 (`51311cf`). Creado `docs/PLAN_FASE_1.md` (incluye auth core como paso 1.9, antes de la API REST). |
| 2026-07-25 | **Fase 1 completada.** Servicios CRUD, ExecutionQueue (escritor único, semáforo, on_overlap), FileLogStore, DockerExecutor (sandbox + enmascarado de secrets, tests con Docker real), SchedulerService stateless con rehidratación, auth multi-usuario (Argon2id, sesiones HttpOnly, RBAC admin/operator/viewer, bootstrap admin), API REST completa (24 endpoints). Puerta de calidad verificada: 272 tests verdes, cobertura 95% total (dominio 100%, servicios ~99%), ruff/mypy/pre-commit limpios. |
| 2026-07-25 | Commit de Fase 1 (`96494dd`). Creado `docs/PLAN_FASE_2.md` (frontend MVP: paso 2.0 de base añadido — cliente HTTP con cookie auth, tipos Zod, layout). |
| 2026-07-25 | **Fase 2 completada.** Login + guardas RBAC, gestión de usuarios, dashboard proyectos/runners (cron legible con cronstrue), form de runner con CodeMirror 6, env vars enmascaradas con rotación, panel de ejecuciones con visor de logs en vivo (polling incremental por offset), trigger manual. Puerta de calidad verificada: 62 tests frontend verdes, type-check/lint/build limpios, **E2E real contra backend + Docker**: login → proyecto → runner → env var → trigger → ejecución `succeeded` → logs con secret enmascarado (`Variable: ********`). |
| 2026-07-25 | Commit de Fase 2 (`bf70abf`). Creado `docs/PLAN_FASE_3.md` (API keys + UI de gestión, rate limiting, retención de logs, webhook en fallo). |
| 2026-07-25 | **Fase 3 completada.** API keys opacas (SHA-256) con scopes y revocación inmediata + página `/api-keys` (admin, token mostrado una única vez); cadena de identidad unificada (`Identity` = sesión \| API key) para RBAC; rate limiting de triggers (100 req/min por identidad, `SlidingWindowRateLimiter` compartido con el login) con `Retry-After`; `RetentionService` (purga diaria de ejecuciones/logs terminales vencidos, spec 6.4); `NotificationService` (webhook fire-and-forget en fallo, 1 reintento, nunca bloquea la cola). Puerta de calidad verificada: 307 tests backend + 65 tests frontend verdes, ruff/mypy/eslint/tsc/build limpios, E2E real contra el backend vivo (crear key → trigger con Bearer → 202; scope insuficiente → 403; key revocada → 401; 101ª request → 429 con `Retry-After`). |
| 2026-07-25 | Commit de Fase 3 (`664f382`). Corregidos, de paso, dos bugs latentes de versión: `.pre-commit-config.yaml` tenía `ruff-pre-commit` anclado a v0.5.0 y `mirrors-mypy` a v1.11.0 mientras Poetry (sin tope superior) ya instalaba ruff 0.16.0 y mypy 2.3.0 — el desfase hacía que el hook `ruff-format` reformateara archivos ya formateados y abortara cualquier commit. Ambos pines actualizados para igualar lo instalado. |
| 2026-07-25 | **Fase 4 (4.1-4.3) completada.** Imagen Docker multi-stage (`node:20-slim` build del frontend + `python:3.12-slim` runtime); FastAPI sirve el build de Vite y hace fallback de SPA (`static_dir`/`CRONDOK_STATIC_DIR`, un solo contenedor, spec 1.3); `docker-compose.yml` con volumen persistente calculado solo (`${PWD}/data`) y el socket de Docker montado (9.3); `README.md` raíz con quickstart, tabla de env vars y advertencia explícita del riesgo del socket. **Bug real descubierto al dockerizar:** el `DockerExecutor` escribía el workspace del job en un `tempfile.TemporaryDirectory()` — funciona corriendo en el host, pero falla dentro de un contenedor porque el daemon resuelve los bind-mounts contra el host, no contra el contenedor de CronDok (`No such file or directory` en el job). Corregido con `host_data_dir`/`CRONDOK_HOST_DATA_DIR`: el workspace vive bajo `data_dir/workspaces/<uuid>` y el executor traduce la ruta al equivalente en el host antes de pedirle al daemon que la monte. Verificado con un job real (`succeeded`, logs correctos) dentro de `docker compose up`, incluyendo persistencia tras `docker compose restart`. 4.4 (release en GitHub) queda pendiente: el repo no tiene remoto configurado y ese paso requiere confirmación explícita del usuario. |
| 2026-07-25 | **Feature post-MVP: constructor de horarios ("Simple"/"Avanzado").** `ScheduleBuilder` reemplaza el input de cron crudo en el formulario de runner: presets (cada N minutos/horas, diario, semanal por día, mensual) que generan la expresión cron (`frontend/src/lib/cron.ts`: `scheduleToCron`/`cronToSchedule`), con fallback a edición cruda para expresiones que no calzan en un preset. Sin cambios de backend (ya aceptaba cualquier cron válido). 13 tests nuevos de las funciones de conversión + tests de integración del formulario. Se descubrió y corrigió de paso que Radix Tabs activa con `mousedown`, no `click` (afecta cómo se simulan clicks de tabs en tests). |
| 2026-07-25 | **Feature post-MVP: dependencias declarativas por runner con caché.** Nuevo campo `dependencies` (uno por línea: `requirements.txt` para python, `nombre`/`nombre@version` para node; sin efecto en bash) instalado por `DockerExecutor` en un volumen cacheado por runner (`data_dir/dep_cache/<runner_id>/pkgs`) y reusado mientras el manifiesto no cambie (hash), sin dejar de destruir el contenedor de ejecución en cada corrida (aislamiento intacto, spec 9.2) — decisión explícita: cachear dependencias sí, contenedor persistente no. Requiere `network_enabled` para instalar (falla con mensaje claro si no); el propio proceso host nunca escribe/borra el caché (permisos del usuario `nobody`), todo ocurre dentro de un contenedor efímero como ese mismo usuario. Migración Alembic (`14647ed74b75`) añade la columna. Puerta de calidad verificada: 329 tests backend (incluye 4 tests de integración reales contra Docker instalando paquetes de verdad — `six` en Python, `ms` en Node — y validando que la segunda corrida reusa el caché aun con red desactivada) + 83 tests frontend, ruff/mypy/eslint/tsc/build/pre-commit limpios. |
