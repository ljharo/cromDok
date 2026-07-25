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
> **Última actualización:** 2026-07-25

---

## Estado General

| Fase | Nombre | Estado | Progreso |
|------|--------|--------|----------|
| 0 | Fundamentos | Completada ✅ | 8/8 |
| 1 | Core Backend | Pendiente | 0/9 |
| 2 | Frontend MVP | Pendiente | 0/6 |
| 3 | API y Seguridad | Pendiente | 0/4 |
| 4 | Dockerización y Release | Pendiente | 0/4 |

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

- [ ] 1.1 Servicios: CRUD de proyectos (`ProjectService`) y runners (`RunnerService`)
- [ ] 1.2 `ExecutionQueue`: cola en memoria + consumidor único escritor (spec 6.3)
- [ ] 1.3 `FileLogStore`: logs en `data/logs/<execution_id>.log` (spec 6.4)
- [ ] 1.4 `DockerExecutor`: contenedores efímeros con límites, semáforo de concurrencia (`CRONDOK_MAX_CONCURRENT_JOBS`) y política `on_overlap` (spec 6.5, 9.2)
- [ ] 1.5 `SchedulerService`: rehidratación al arranque + registro dinámico de jobs (spec 7)
- [ ] 1.6 API REST completa: routers de projects, runners, executions, env_vars, triggers + endpoint de logs con offset
- [ ] 1.7 `EncryptionService` (Fernet) + gestión de `CRONDOK_MASTER_KEY` (spec 9.1)
- [ ] 1.8 Tests unitarios e integración (>80% en `domain/` y `services/`)
- [ ] 1.9 **Auth core**: entidades `User`/`Session`, hash Argon2id (`pwdlib`), login/logout con cookie HttpOnly, middleware de protección de endpoints, bootstrap del admin en el primer arranque (spec 9.4.1, 9.4.3)

---

## Fase 2: Frontend MVP (Semanas 6-8)

- [ ] 2.1 **Pantalla de login** + guarda de rutas (redirect a `/login` sin sesión) y página de gestión de usuarios para admin (spec 9.4.1)
- [ ] 2.2 Dashboard de proyectos y runners
- [ ] 2.3 Formularios de crear/editar runners con editor de script
- [ ] 2.4 Gestión de variables de entorno (tabla con secrets ocultos, solo rotación)
- [ ] 2.5 Panel de ejecuciones: lista, estado y visor de logs (polling con offset)
- [ ] 2.6 Trigger manual desde la UI

---

## Fase 3: API y Seguridad (Semana 9)

- [ ] 3.1 API keys opacas hasheadas (SHA-256) con scopes y revocación (spec 9.4)
- [ ] 3.2 `POST /api/v1/triggers/{runner_id}` con rate limiting (100 req/min)
- [ ] 3.3 Tarea de retención de logs/ejecuciones (`CRONDOK_LOG_RETENTION_DAYS`, spec 6.4)
- [ ] 3.4 Webhook de notificación en fallo de ejecución

---

## Fase 4: Dockerización y Release (Semana 10)

- [ ] 4.1 Dockerfile multi-stage (backend + build de frontend)
- [ ] 4.2 Docker Compose con volumen persistente (`data/`)
- [ ] 4.3 Documentación de despliegue + advertencia del riesgo del Docker socket (spec 9.3)
- [ ] 4.4 Release v0.1.0 en GitHub

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
