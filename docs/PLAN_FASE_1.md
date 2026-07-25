# Plan de Implementación - Fase 1: Core Backend

> **Basado en:** `docs/ESPECIFICACION_TECNICA_CRONDOK.md` v0.2.0 (secciones 4, 6, 7, 9) · `docs/TODO.md` (tareas 1.1-1.9)
> **Duración estimada:** 3 semanas
> **Objetivo de la fase:** Backend funcional de punta a punta: servicios de aplicación, cola de
> ejecuciones con escritor único, logs en archivos, executor Docker con concurrencia acotada,
> scheduler stateless, auth multi-usuario y API REST completa — todo tras la puerta de calidad.

**Puerta de calidad (obligatoria para cerrar la fase):**
1. `poetry run pytest` verde — incluye tests de integración que levantan contenedores Docker reales.
2. Cobertura >80% en `domain/` y `services/`.
3. `ruff check`, `ruff format --check`, `mypy` y `pre-commit run --all-files` verdes.
4. Prueba manual end-to-end: login → crear proyecto → crear runner → trigger → ver ejecución y logs vía API.
5. `docs/TODO.md` actualizado (1.1-1.9) y commit realizado.

---

## Paso 1.1 - Servicios CRUD: ProjectService y RunnerService

**Archivos:** `services/project_service.py`, `services/runner_service.py`, `services/errors.py`

1. Excepciones de aplicación: `ProjectNotFoundError`, `RunnerNotFoundError`, `DuplicateNameError`, etc. (sin dependencia de HTTP — el mapeo a status codes vive en el adaptador).
2. `ProjectService`: `create`, `get`, `list`, `update`, `delete` (delete en cascada vía FK; validar que no queden runners huérfanos — la FK `ON DELETE CASCADE` ya lo garantiza, testearlo).
3. `RunnerService`: `create` (valida que el proyecto existe, que el cron es válido vía dominio, normaliza `ResourceLimits`), `update`, `delete`, `enable`/`disable`. Toda escritura dentro de `async with uow:` (spec 6.2).
4. Tests unitarios con repositorios en memoria (fakes implementando los puertos) — sin DB.

**Depende de:** nada nuevo (Fase 0). **Verificación:** tests unitarios verdes, mypy strict en `services/`.

---

## Paso 1.2 - ExecutionQueue + FileLogStore

**Archivos:** `services/execution_queue.py`, `adapters/output/logs/file_log_store.py`

1. `FileLogStore` (implementa `ports/logs/log_store.py`, spec 6.4):
   - `open_writer(execution_id)` → sink async que appendea a `data/logs/<id>.log` (crea dir si no existe).
   - `read(execution_id, offset)` → `(chunk, nuevo_offset)` para polling incremental.
   - `delete(execution_id)`.
2. `ExecutionQueue` (spec 6.3):
   - `asyncio.Queue` interna de eventos: `ExecutionCreated`, `ExecutionStarted`, `ExecutionFinished(exit_code, timed_out)`.
   - `enqueue_execution(runner, trigger_type)` → crea la `Execution` en estado `queued` y encola.
   - **Un único consumidor** (`start()`/`stop()` como tarea async del lifespan) que drena la cola: persiste transiciones de estado vía UoW y despacha al `JobExecutor` respetando el semáforo (1.4).
   - Tests: múltiples productores concurrentes → estados persistidos en orden, sin `database is locked` (test de estrés con 50 ejecuciones encoladas a la vez contra SQLite real en tmp_path).

**Depende de:** 1.1. **Verificación:** test de estrés concurrente verde.

---

## Paso 1.3 - DockerExecutor

**Archivo:** `adapters/output/executor/docker_executor.py`

1. Implementa `JobExecutor` (spec 9.2):
   - Imagen por lenguaje: `python:3.12-slim`, `node:20-slim`, `bash:5` (configurables en settings).
   - Crea contenedor efímero (`auto_remove`), script montado en `/workspace` (tmpfs o volumen temporal), env vars inyectadas, `--network none` salvo `network_enabled`, límites `--memory/--cpus/--pids-limit`, usuario `nobody` (65534).
   - Captura stdout/stderr en streaming hacia el `LogSink` del `LogStore`.
   - Timeout: kill forzado a `timeout_seconds` → `timed_out=True`, estado `killed`.
   - `docker-py` es síncrono → envolver en `asyncio.to_thread` (spec 8.4).
2. Filtrado de secrets en logs: los valores de env vars se enmascaran antes de escribir al log (spec 9.1).
3. Tests de integración **con Docker real**: script que imprime, script que falla (exit 1), script que duerme (timeout), límites de memoria. Marcar con `pytest.mark.docker` y skip automático si no hay daemon (para CI sin Docker).

**Depende de:** 1.2. **Verificación:** 4+ tests de integración Docker verdes en local.

---

## Paso 1.4 - Concurrencia acotada y política on_overlap

**Dentro de:** `services/execution_queue.py` (semáforo) y `services/scheduler_service.py`

1. `asyncio.Semaphore(settings.max_concurrent_jobs)` (default 4) en el consumidor: los triggers que exceden quedan `queued` (spec 6.5).
2. Política `on_overlap` por runner: al disparar, si hay ejecución `running`/`queued` del mismo runner → `skip` (registrar `skipped`), `queue` (encolar igual) o `kill_previous` (cancelar contenedor y arrancar).
3. Tests unitarios de las tres políticas con executor fake.

**Depende de:** 1.2, 1.3. **Verificación:** tests de las 3 políticas + test de semáforo (N máx concurrentes reales).

---

## Paso 1.5 - SchedulerService (stateless)

**Archivos:** `services/scheduler_service.py`, `adapters/input/scheduler/scheduler_adapter.py`

1. Wrapper de `AsyncIOScheduler` de APScheduler: `register(runner)`, `unregister(runner_id)`, `update(runner)`; jobs con `max_instances=1`, `coalesce=True` (spec 6.5).
2. **Rehidratación** (spec 7): al arrancar, leer runners `is_enabled=true` y registrarlos. Hook en el lifespan de FastAPI.
3. El callback del scheduler no ejecuta directo: llama a `ExecutionQueue.enqueue_execution(runner, trigger_type="cron")`.
4. Tests: registro/rehidratación con DB temporal (scheduler apagado en tests; verificar que los jobs quedan registrados con el cron correcto vía la API del scheduler, sin esperar disparos reales) + un test de integración con cron de `*/1s`-style (trigger por intervalo de 1s) que verifica el ciclo completo cron → cola → ejecución.

**Depende de:** 1.2. **Verificación:** test de ciclo completo verde.

---

## Paso 1.6 - API REST (routers + schemas)

**Archivos:** `adapters/input/http/routers/{projects,runners,executions,env_vars,triggers}.py`, `schemas/`, `dependencies.py`, `main.py`

1. `dependencies.py`: wiring con `Depends` (solo aquí, spec 8.4): UoW por request, servicios como singletons del lifespan.
2. Endpoints (prefijo `/api/v1`):
   - `projects`: CRUD completo.
   - `runners`: CRUD + `enable`/`disable`.
   - `executions`: `GET /runners/{id}/executions`, `GET /executions/{id}`, `GET /executions/{id}/logs?offset=N` (polling incremental vía `LogStore`).
   - `env_vars`: create/list (nunca devuelve valores, spec 9.1)/delete.
   - `triggers`: `POST /triggers/{runner_id}` → 202 con `execution_id`.
3. Schemas Pydantic request/response; mapeo de excepciones de aplicación a 404/409/422 vía exception handlers.
4. Tests de API con `httpx.AsyncClient` + `ASGITransport` (executor y scheduler fakes).

**Depende de:** 1.1-1.5, 1.9 (middleware). **Verificación:** tests de API verdes cubriendo happy path + errores.

---

## Paso 1.7 - EncryptionService + master key

**Archivos:** `adapters/output/security/encryption_service.py`, lógica de bootstrap en `main.py`/settings

1. Fernet con `CRONDOK_MASTER_KEY`; si no está definida, generar y persistir en `data/.master_key` (chmod 600) con warning en logs (spec 9.1).
2. `EnvVarService` (`services/env_var_service.py`): `create` encripta antes de persistir; `resolve_for_runner(runner_id)` descifra en memoria (proyecto → runner, el runner sobrescribe).
3. Tests: roundtrip encrypt/decrypt, jerarquía proyecto→runner, bootstrap de master key en tmp_path.

**Depende de:** 1.1. **Verificación:** tests verdes; ningún test escribe secrets en claro en disco.

---

## Paso 1.8 - (se reserva para cierre) Suite completa y cobertura

No es código nuevo: es la verificación final de la puerta de calidad de la fase (arriba) + rellenar huecos de cobertura que hayan quedado en `services/`.

---

## Paso 1.9 - Auth core (hacer ANTES de 1.6, ver orden)

**Archivos:** `domain/entities/user.py`, `ports/repositories/user_repository.py`, `adapters/output/persistence/models/user_model.py` (+ `session`), `services/auth_service.py`, `adapters/output/security/password_service.py`, router `auth.py`, middleware, migración Alembic nueva.

1. **Dominio:** `User(id, username, password_hash, role: admin|operator|viewer, is_active, must_change_password)` y `Session(token_hash, user_id, expires_at)`.
2. **Migración Alembic:** tablas `users` y `sessions` (segunda migración; la numeración continúa desde la de Fase 0).
3. **PasswordService:** Argon2id vía `pwdlib`, mínimo 12 chars (spec 9.4.1).
4. **AuthService:** `login(username, password)` → crea sesión (token opaco, hash SHA-256 en DB, expira 7 días); `logout(token)`; `resolve_session(token)` → user o None; `bootstrap_admin()` — si no hay usuarios, crea `admin` con password aleatoria impresa una vez en logs.
5. **Middleware/dependencia FastAPI:** protege todo salvo `POST /api/v1/auth/login`, `GET /api/v1/health` y estáticos; acepta cookie de sesión (las API keys llegan en Fase 3, pero dejar el punto de extensión en el resolver).
6. **Autorización por rol:** dependencia `require_role("admin")` para gestión de usuarios; `viewer` solo GET.
7. Tests: login ok/fallo, sesión expirada, RBAC por endpoint, bootstrap idempotente, rate limit de login (10/min por IP — puede implementarse con un contador en memoria simple).

**Depende de:** 1.1. **Verificación:** tests de auth verdes; petición sin sesión a cualquier endpoint → 401.

---

## Orden de ejecución

```
1.1 ──► 1.2 ──► 1.3 ──► 1.4 ──┐
  │       │                   ├──► 1.6 ──► 1.8 (cierre)
  │       └──► 1.5 ───────────┤
  ├──► 1.7                    │
  └──► 1.9 ───────────────────┘ (antes de 1.6 para que la API nazca protegida)
```

Paralelizable: {1.7, 1.9} tras 1.1; {1.3+1.4} y 1.5 tras 1.2.

## Riesgos de la fase

| Riesgo | Mitigación |
|--------|------------|
| Tests Docker lentos/inestables en CI | Marcar `@pytest.mark.docker`, skip sin daemon; CI los corre en ubuntu-latest (Docker disponible) |
| APScheduler + asyncio en tests (loops colgados) | Scheduler nunca arranca en tests unitarios; un solo test de integración con scheduler real y timeout duro |
| docker-py síncrono bloquea el loop | Todo acceso a Docker vía `asyncio.to_thread`; test que verifica que el loop responde durante una ejecución larga |
| Cookie auth + futura API key en el mismo resolver | Diseñar `resolve_identity` con cadena: cookie → header Bearer (extensible en Fase 3 sin refactor) |
| Pull de imágenes Docker en tests (python:3.12-slim etc.) | Pull previo documentado o fixture de sesión que las precarga una vez |

## Al terminar la fase

- [ ] Marcar 1.1-1.9 como `[x]` en `docs/TODO.md`, tabla de progreso (Fase 1 → 9/9) y registro de cambios.
- [ ] Commit `feat: core backend - services, execution queue, docker executor, scheduler, auth (phase 1)`.
