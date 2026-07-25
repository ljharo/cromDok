# Plan de Implementación - Fase 3: API y Seguridad

> **Basado en:** `docs/ESPECIFICACION_TECNICA_CRONDOK.md` v0.2.0 (secciones 6.4, 9.4) · `docs/TODO.md` (tareas 3.1-3.4)
> **Duración estimada:** 1 semana
> **Objetivo de la fase:** Abrir la API a integraciones externas de forma segura (API keys con
> scopes y rate limiting) y cerrar dos piezas operativas del MVP: retención de logs/ejecuciones
> y notificación por webhook en fallo.

**Puerta de calidad (obligatoria para cerrar la fase):**
1. `poetry run pytest` verde (backend) + `npx vitest run` verde (frontend).
2. `ruff`, `mypy`, `pre-commit run --all-files` verdes.
3. E2E real: crear API key por UI → trigger con `Authorization: Bearer` → 202; key revocada → 401; scope insuficiente → 403; 101 requests → 429.
4. `docs/TODO.md` actualizado (3.1-3.4) y commit realizado.

---

## Paso 3.1 - API keys opacas con scopes (backend + UI)

### Backend
**Archivos:** `domain/entities/api_key.py`, `ports/repositories/api_key_repository.py`, modelo ORM + **migración Alembic** (`api_keys`), `services/api_key_service.py`, router `api_keys.py`, cambio en `dependencies.py`.

1. Entidad `ApiKey(id, name, key_hash, scopes: list[str], created_by, created_at, last_used_at, revoked_at)`.
2. `ApiKeyService`:
   - `create(name, scopes, user)` → genera `crondok_<token_urlsafe(32)>`, persiste SOLO `sha256(token)`; el token en claro se devuelve **una única vez** en la respuesta de creación.
   - `list()` → sin hashes ni tokens (name, scopes, created_at, last_used_at, revoked).
   - `revoke(id)` → marca `revoked_at` (revocación inmediata, spec 9.4.2).
   - `resolve(token)` → valida hash + no revocada, actualiza `last_used_at`, devuelve contexto (scopes).
3. **Cadena de identidad** (el punto de extensión dejado en 1.6): `resolve_identity` = cookie de sesión → header `Authorization: Bearer crondok_...`. Unificar el contexto: usuario (sesión) o api key (scopes) → mismo chequeo de autorización. Mapeo scopes↔roles: `admin` = todo, `runners:execute` = triggers, `runners:read` = GETs.
4. Router `api_keys.py` (solo admin vía sesión; una API key NO puede gestionar API keys): `GET/POST /api-keys`, `DELETE /api-keys/{id}`.
5. Tests: unitarios (create devuelve token una vez, resolve ok/revocado, scopes) + API (flujo completo: crear key → usarla en un endpoint → revocar → 401; scope insuficiente → 403; una key no puede crear keys).

### Frontend
**Archivos:** `src/features/api-keys/` + entrada en sidebar (solo admin).

6. Página `/api-keys`: tabla (nombre, scopes, creada, último uso, estado), crear (dialog con nombre + checkboxes de scopes → muestra el token UNA vez con botón copiar y aviso "no se volverá a mostrar"), revocar (confirm).
7. Tests vitest: crear muestra el token una vez, revocar llama al endpoint, oculta para no-admin.

---

## Paso 3.2 - Rate limiting en triggers

**Archivos:** `adapters/input/http/rate_limit.py` (o middleware), config.

1. Limiter en memoria (ventana deslizante por minuto) aplicado a `POST /triggers/{id}`: **100 req/min por identidad** (API key o usuario), y por runner para evitar abuso sobre un solo job. 429 con `Retry-After`.
2. Reutilizar/unificar con el limiter de login de 1.6 (hoy es un contador inline): extraer una utilidad común configurable.
3. Config: `CRONDOK_RATE_LIMIT_TRIGGERS` (default 100).
4. Tests: 101 triggers con la misma key → el 101 devuelve 429; keys distintas tienen contadores independientes; ventana se resetea.

**Nota:** el limiter en memoria es válido para el MVP single-node; documentado como limitación conocida para multi-nodo (sección 10 de la spec).

---

## Paso 3.3 - Retención de logs y ejecuciones

**Archivos:** `services/retention_service.py`, wiring en scheduler (job del sistema).

1. `RetentionService.purge()`: borra ejecuciones (y sus archivos de log vía `LogStore.delete`) con `finished_at` más antiguo que `CRONDOK_LOG_RETENTION_DAYS` (default 30, ya en config). Solo estados terminales, nunca queued/running.
2. Se registra como job del sistema en APScheduler al arrancar (diario, hora fija p.ej. 04:17) — va por el mismo SchedulerService pero **sin pasar por ExecutionQueue** (no es un runner de usuario; log propio a logging).
3. Tests: unitarios (borra solo lo viejo y terminal, llama a LogStore.delete) + integración (siembra ejecuciones con fechas distintas + archivos de log reales en tmp_path → purge → quedan las recientes, archivos viejos eliminados).

---

## Paso 3.4 - Webhook de notificación en fallo

**Archivos:** `services/notification_service.py`, config, wiring en ExecutionQueue, UI básica en settings del proyecto o global (decidir: ver abajo).

1. Config global por ahora (KISS): `CRONDOK_WEBHOOK_URL` (opcional) + `CRONDOK_WEBHOOK_TIMEOUT` (5s). Si no está definida, no-op. (Webhooks por proyecto queda para Fase 5+.)
2. `NotificationService.notify_failure(execution, runner)`: POST JSON `{event: "execution.failed", execution_id, runner_id, runner_name, exit_code, finished_at, log_excerpt (últimas 500 chars, YA enmascaradas)}` vía httpx async, timeout corto, **fire-and-forget**: un fallo del webhook nunca afecta a la ejecución ni al consumidor de la cola (try/except + log). Máximo 1 reintento.
3. Wiring: el consumidor de `ExecutionQueue` llama a `notify_failure` solo en transición a `failed` (no en `killed` por timeout… decidir: killed por timeout SÍ notifica; skipped no). Documentar la decisión.
4. Tests: unitarios con httpx mockeado (payload correcto, timeout, excepción no propaga, no se llama en succeeded) + test de cola (executor fake que falla → webhook invocado).

---

## Orden de ejecución

```
3.1 (backend) ──► 3.1 (frontend) ──┐
3.2 ───────────────────────────────┼──► cierre (E2E + commit)
3.3 ───────────────────────────────┤
3.4 ───────────────────────────────┘
```
Paralelizable: {3.2, 3.3, 3.4} tras 3.1-backend (3.2 toca dependencies/rate limit; 3.4 toca execution_queue — distintos archivos).

## Riesgos de la fase

| Riesgo | Mitigación |
|--------|------------|
| `resolve_identity` dual (cookie/Bearer) complica el chequeo de autorización | Un solo tipo `Identity` (user \| api_key) con método `allows(action)`; tests de matriz usuario×key×scope |
| Webhook bloqueante frena la cola de ejecuciones | fire-and-forget con timeout 5s, máx 1 reintento, nunca await en el camino crítico del worker |
| Purge borra logs de ejecuciones recién terminadas | Condición estricta: `finished_at < now - retention` Y estado terminal; tests de borde |
| Token de API key filtrado en logs de acceso | No loggear el header Authorization; el token solo se muestra una vez en la respuesta de creación |

## Al terminar la fase

- [ ] Marcar 3.1-3.4 como `[x]` en `docs/TODO.md`, tabla de progreso (Fase 3 → 4/4) y registro de cambios.
- [ ] Commit `feat: api keys, rate limiting, log retention, failure webhooks (phase 3)`.
