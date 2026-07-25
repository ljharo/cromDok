# Plan de Implementación - Fase 2: Frontend MVP

> **Basado en:** `docs/ESPECIFICACION_TECNICA_CRONDOK.md` v0.2.0 (secciones 3.2, 8.4, 9.4) · `docs/TODO.md` (tareas 2.1-2.6)
> **Duración estimada:** 3 semanas
> **Objetivo de la fase:** UI funcional completa contra la API real de la Fase 1: login con guarda
> de rutas, gestión de usuarios (admin), dashboard de proyectos/runners, formularios de runner con
> editor de script, gestión de env vars, panel de ejecuciones con visor de logs y trigger manual.

**Puerta de calidad (obligatoria para cerrar la fase):**
1. `npm run type-check`, `npm run lint`, `npm run test:unit`, `npm run build` verdes.
2. `pre-commit run --all-files` verde.
3. Verificación manual end-to-end: backend real corriendo + `npm run dev` → login → crear proyecto → crear runner → trigger → ver logs en el visor.
4. `docs/TODO.md` actualizado (2.1-2.6) y commit realizado.

**Contrato con el backend (ya existe, Fase 1):**
- Auth: `POST /api/v1/auth/login` (set-cookie `crondok_session` HttpOnly), `POST /auth/logout`, `GET /auth/me`. Cookie de sesión → el cliente usa `withCredentials` y no guarda tokens.
- RBAC: roles `admin`/`operator`/`viewer` (viewer solo lectura; la UI debe ocultar acciones de escritura).
- Recursos: CRUD `projects`, `runners` (+`enable`/`disable`), `executions` (+`logs?offset=N` incremental), `env-vars` (nunca devuelven valores), `users` (solo admin), `POST /triggers/{runner_id}` → 202.
- Errores: 401 sin sesión, 403 sin rol, 409 duplicado, 422 validación.

---

## Paso 2.0 - Base: cliente HTTP, tipos y layout (previo a todo)

**Archivos:** `src/api/client.ts`, `src/api/endpoints.ts`, `src/types/`, `src/components/Layout.tsx`

1. `client.ts`: instancia Axios con `baseURL: "/api/v1"`, `withCredentials: true`, interceptor 401 → redirect a `/login` (salvo si ya estás ahí). Proxy de Vite: `/api` → `http://localhost:8000` en `vite.config.ts` para desarrollo.
2. `types/`: tipos TS + Zod schemas compartiendo contrato con los schemas Pydantic del backend (Project, Runner, Execution, EnvVarSummary, User, LoginRequest, etc.). Los Zod schemas se usan en formularios (spec 8.4).
3. Layout de la app: sidebar con navegación (Proyectos, Ejecuciones, Usuarios si admin), header con usuario actual + logout. Componentes shadcn necesarios: instalar con CLI los que hagan falta (button, input, card, table, dialog, form, select, badge, tabs, textarea, dropdown-menu, sonner/toast).
4. Hook `useCurrentUser` (TanStack Query sobre `GET /auth/me`) como fuente de verdad de sesión y rol.

**Verificación:** type-check/lint verdes; smoke test del layout.

---

## Paso 2.1 - Login + guarda de rutas + gestión de usuarios

**Archivos:** `src/features/auth/`, `src/features/users/`, `src/router.tsx`

1. Pantalla `/login`: formulario (React Hook Form + Zod), errores 401 en pantalla, redirect al destino original tras login.
2. Guarda de rutas: componente `RequireAuth` que consulta `useCurrentUser`; sin sesión → `/login`. `RequireRole("admin")` para rutas de admin.
3. `/users` (solo admin): tabla de usuarios, crear usuario (con rol), eliminar, reset password. Opción "cambiar contraseña" propia si `must_change_password` (banner o redirect forzado).
4. Botón logout en el header (llama `POST /auth/logout`, invalida query `me`, redirect a `/login`).
5. Tests vitest: login renderiza y valida, guarda redirige sin sesión (mockear client con MSW o mock de axios), tabla de usuarios oculta para no-admin.

**Depende de:** 2.0. **Verificación:** tests verdes; navegación manual: sin login no se ve nada salvo /login.

---

## Paso 2.2 - Dashboard de proyectos y runners

**Archivos:** `src/features/projects/`, `src/features/runners/`

1. `/projects`: grid/tabla de proyectos (nombre, descripción, nº de runners), crear proyecto (dialog), editar, eliminar (confirm dialog — avisa de cascada).
2. `/projects/{id}`: detalle con tabs: **Runners** | **Variables** | **Ejecuciones**.
3. Tabla de runners del proyecto: nombre, lenguaje (badge), cron (badge + descripción legible, ej. con `cronstrue`), enabled (switch que llama enable/disable), última ejecución (estado con color), acciones (editar, eliminar, ejecutar).
4. TanStack Query para todo fetching; invalidaciones tras mutaciones (spec 8.4: no useEffect para APIs).
5. Tests: lista renderiza proyectos/runners, estados vacíos, switch enable/disable llama al endpoint.

**Depende de:** 2.1. **Verificación:** tests verdes + flujo manual crear proyecto → aparece en lista.

---

## Paso 2.3 - Formularios de runner con editor de script

**Archivos:** `src/features/runners/components/RunnerForm.tsx`, editor

1. Formulario crear/editar runner: nombre, lenguaje (select python/bash/node), expresión cron (input con validación Zod + preview legible con `cronstrue` + error 422 del backend mapeado al campo), timeout, límites de recursos (memoria, CPUs, pids), `network_enabled` (checkbox con warning de seguridad), `on_overlap` (select skip/queue/kill_previous).
2. Editor de script: **CodeMirror 6** (`@uiw/react-codemirror` — ligero y sin workers complicados) con highlighting por lenguaje. No Monaco (pesado para el MVP).
3. Validación cliente con Zod antes de enviar; errores de campo del backend (422) mapeados al formulario.
4. Tests: validaciones Zod (cron inválido no envía), cambio de lenguaje cambia highlighting, submit llama al endpoint con el payload correcto.

**Depende de:** 2.2. **Verificación:** crear runner end-to-end manual (aparece en tabla con su cron).

---

## Paso 2.4 - Gestión de variables de entorno

**Archivos:** `src/features/env-vars/`

1. Tab dentro del detalle del proyecto: tabla de env vars (key, scope: proyecto o runner específico, valor SIEMPRE `••••••••` — el backend nunca lo devuelve).
2. Crear variable: key (validación formato + blacklist PATH/LD_PRELOAD/HOME en cliente, además del 422 del backend), value (input password), scope (proyecto o runner del proyecto).
3. Acciones: rotar (dialog con nuevo valor; nunca muestra el actual) y eliminar.
4. Tests: list no muestra valores, crear valida blacklist, rotate envía al endpoint correcto.

**Depende de:** 2.2. **Verificación:** crear var → aparece enmascarada; rotar funciona.

---

## Paso 2.5 - Panel de ejecuciones con visor de logs

**Archivos:** `src/features/executions/`

1. `/executions` global y tab de ejecuciones por proyecto: tabla (runner, trigger programado/manual, estado con badge de color: queued/running/succeeded/failed/killed/skipped, inicio, duración, exit code).
2. Polling con TanStack Query (`refetchInterval` ~3s) solo mientras haya ejecuciones en estado queued/running; parado cuando todo está en estado terminal.
3. Visor de logs: drawer/página `GET /executions/{id}/logs?offset=N` con polling incremental (el hook conserva el offset y appendea chunks), auto-scroll al final con toggle, badge "EN VIVO" mientras running.
4. Tests: tabla renderiza estados con badges, hook de logs acumula chunks por offset (mock de respuestas secuenciales), polling se detiene en estado terminal.

**Depende de:** 2.2. **Verificación:** trigger manual → ver ejecución pasar por estados → logs en vivo.

---

## Paso 2.6 - Trigger manual desde la UI

**Archivos:** integración en `src/features/runners/` y `src/features/executions/`

1. Botón "Ejecutar ahora" en cada runner (tabla y detalle): `POST /triggers/{id}` → 202, toast con confirmación y link a la ejecución.
2. Invalidar queries de ejecuciones tras el trigger para que aparezca la nueva en queued.
3. Respeto de RBAC: viewer no ve el botón (ni los de crear/editar/eliminar de 2.2-2.4 — repasar).
4. Tests: click → endpoint llamado, toast mostrado, viewer no ve el botón.

**Depende de:** 2.5. **Verificación:** flujo completo manual E2E de la puerta de calidad.

---

## Orden de ejecución

```
2.0 ──► 2.1 ──► 2.2 ──┬──► 2.3 ──┐
                      ├──► 2.4 ──┼──► 2.5 ──► 2.6
                      └──────────┘
```
Paralelizable tras 2.2: {2.3, 2.4} y 2.5 pueden ir en paralelo; 2.6 cierra.

## Riesgos de la fase

| Riesgo | Mitigación |
|--------|------------|
| Cookie HttpOnly + proxy Vite: CORS/puertos en dev | Proxy `/api` en `vite.config.ts`; mismo origen en prod (backend sirve estáticos en Fase 4) |
| Polling descontrolado de ejecuciones/logs | `refetchInterval` condicional (solo estados vivos); logs con offset incremental, nunca refetch completo |
| shadcn + Tailwind v3 vs CLI actual (v4) | Mantener el patrón de Fase 0: componentes generados compatibles con Tailwind 3.4 instalado |
| Editor de script pesado | CodeMirror 6, no Monaco; carga perezosa si hiciera falta |
| Tests de componentes con TanStack Query | Wrapper de test con QueryClientProvider + router de memoria; MSW o mock del client axios |

## Al terminar la fase

- [ ] Marcar 2.1-2.6 como `[x]` en `docs/TODO.md`, tabla de progreso (Fase 2 → 6/6) y registro de cambios.
- [ ] Commit `feat: frontend mvp - login, dashboard, runners, env vars, executions (phase 2)`.
