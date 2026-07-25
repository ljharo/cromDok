# Plan de Implementación - Fase 4: Dockerización y Release

> **Basado en:** `docs/ESPECIFICACION_TECNICA_CRONDOK.md` v0.2.0 (secciones 1.3, 3.3, 9.3) · `docs/TODO.md` (tareas 4.1-4.4)
> **Duración estimada:** 1 semana
> **Objetivo de la fase:** Que cualquiera pueda levantar CronDok con **un solo comando**
> (`docker compose up`), con datos persistentes, el riesgo del socket de Docker documentado
> sin rodeos, y cerrar el MVP con una release v0.1.0 en GitHub.

**Puerta de calidad (obligatoria para cerrar la fase):**
1. `docker build` de la imagen sin errores; `docker compose up` levanta el stack completo.
2. E2E real contra el contenedor: login con el admin bootstrapeado (contraseña en logs) →
   crear proyecto → runner → trigger → ejecución `succeeded` con logs — todo dentro de Docker,
   sin `poetry run` / `npm run dev` locales.
3. Reinicio del contenedor (`docker compose restart`) conserva usuarios, proyectos y ejecuciones
   (volumen persistente verificado).
4. `pre-commit run --all-files` verde (incluye el Dockerfile/compose vía hooks generales).
5. `docs/TODO.md` actualizado (4.1-4.4), tabla de progreso y registro de cambios.

**Decisión de arquitectura (spec 1.3, "pocos servicios"):** un único contenedor sirve la API
y los estáticos del frontend ya compilado (FastAPI monta el build de Vite y hace fallback de
SPA para las rutas de React Router). Nada de un servicio nginx aparte solo para archivos
estáticos — añadir un segundo servicio por eso erosiona el diferencial de "un solo comando".

---

## Paso 4.1 - Dockerfile multi-stage

**Archivos:** `Dockerfile` (raíz), `deploy/entrypoint.sh`, `backend/src/cron_dok/main.py` (mount de estáticos), `backend/src/cron_dok/config.py` (`static_dir`, `host_data_dir`), `backend/src/cron_dok/adapters/output/executor/docker_executor.py`

1. **Stage `frontend-build`** (`node:20-slim`): `npm ci` + `npm run build` sobre `frontend/`
   → produce `frontend/dist/`.
2. **Stage final** (`python:3.12-slim`): instala solo dependencias de producción del backend
   (`poetry install --only main --no-root` o export a `requirements.txt` + `pip install`),
   copia `backend/src`, `backend/alembic*`, y el `frontend/dist` del stage anterior a
   `/app/static`.
3. `config.py`: nuevo `static_dir: str | None = None` (`CRONDOK_STATIC_DIR`). En `main.py`,
   **solo si** `settings.static_dir` apunta a un directorio existente: montar
   `StaticFiles` en `/assets` y registrar un catch-all `GET /{full_path:path}` (registrado
   **después** de todos los routers de `/api/v1/*`) que sirve `index.html` para cualquier ruta
   que no empiece por `api/` — necesario para que las rutas de React Router (`/projects/5`)
   no den 404 al refrescar. Sin `static_dir` (tests, dev), el comportamiento actual no cambia.
4. `deploy/entrypoint.sh`: `alembic upgrade head` (mismo `DATABASE_URL` que la app) y luego
   `exec uvicorn cron_dok.main:app --host 0.0.0.0 --port 8000`. **Ojo con el nombre**: no
   `docker/entrypoint.sh` — un directorio llamado `docker/` en la raíz del repo colisiona con
   el paquete pip `docker` cuando mypy corre desde la raíz (namespace package implícito que
   shadowea al paquete real); descubierto al integrar esta fase, ver riesgos.
5. `.dockerignore`: excluir `node_modules`, `.venv`, `data/`, `__pycache__`, `.git`.
6. Test manual: `docker build -t crondok:local .` construye sin errores; `docker run --rm -p 8000:8000 crondok:local` sirve `/` (index.html del frontend) y `/api/v1/health`.

**Riesgo conocido (spec 9.3):** el contenedor de CronDok necesita `/var/run/docker.sock` para
lanzar los jobs (Docker-out-of-Docker) — no se sandboxea a sí mismo (no tendría sentido: quien
controla este proceso ya tiene root sobre el host vía el socket). Los contenedores de **jobs**
sí se sandboxean (9.2): `--rm`, límites de recursos, `--network none` por defecto, usuario
`nobody`, filesystem efímero.

**Bug real descubierto al dockerizar (no estaba en el plan original):** el `DockerExecutor`
(fase 1) escribía el script del runner en un `tempfile.TemporaryDirectory()` y montaba esa
ruta en el contenedor del job. Eso funciona cuando CronDok corre directo en el host, pero
al correr CronDok **dentro** de un contenedor con el socket del host montado, el daemon
resuelve las rutas de bind-mount contra el **host**, no contra el contenedor de CronDok — el
job fallaba con `No such file or directory`. Arreglado con `host_data_dir` (`CRONDOK_HOST_DATA_DIR`):
el workspace de cada ejecución vive bajo `data_dir/workspaces/<uuid>` (dentro del volumen ya
montado) y el executor traduce esa ruta a su equivalente en el host antes de pedirle al
daemon que la monte. `docker-compose.yml` lo calcula solo (`${PWD}/data`); en dev (sin
`host_data_dir`) no hay traducción, igual que antes.

---

## Paso 4.2 - Docker Compose con volumen persistente

**Archivos:** `docker-compose.yml`, `.env.example` (raíz)

1. Un único servicio `crondok`:
   - `build: .`
   - `ports: ["8000:8000"]`
   - `volumes`:
     - `${PWD}/data:/app/data` — SQLite (WAL), `data/.master_key`, `data/logs/` y los
       workspaces de ejecución (persistencia real; ruta absoluta, no `./data`, porque el
       daemon la resuelve contra el host — spec 9.3).
     - `/var/run/docker.sock:/var/run/docker.sock` — requerido para lanzar jobs (9.3).
   - `environment`: `CRONDOK_HOST_DATA_DIR=${PWD}/data` (mismo valor que el volumen, para que
     el executor traduzca las rutas de los workspaces) + el resto de `CRONDOK_*` de
     `config.py`, con valores por defecto sensatos y comentario en cada una remitiendo a
     `.env.example`.
   - `restart: unless-stopped`.
2. `.env.example`: `CRONDOK_MASTER_KEY` (vacío = se autogenera y persiste, recomendado fijarlo
   en producción para poder migrar de host), `CRONDOK_MAX_CONCURRENT_JOBS`,
   `CRONDOK_LOG_RETENTION_DAYS`, `CRONDOK_WEBHOOK_URL`, `CRONDOK_RATE_LIMIT_TRIGGERS`.
3. Verificación: `docker compose up -d` → `docker compose logs -f crondok` muestra el bootstrap
   del admin; `docker compose down && docker compose up -d` conserva los datos (volumen
   `./data` en el host, no un volumen anónimo).

**Depende de:** 4.1. **Verificación:** stack completo arriba con un solo comando (spec 1.2/1.3).

---

## Paso 4.3 - Documentación de despliegue

**Archivos:** `README.md` (raíz, nuevo)

1. Qué es CronDok (2-3 líneas), quickstart: `git clone` → `docker compose up -d` →
   credenciales del admin (`docker compose logs crondok | grep "First boot"`) → abrir
   `http://localhost:8000`.
2. Tabla de variables de entorno (`CRONDOK_*`) con default y propósito (reutilizar
   `config.py` como fuente de verdad).
3. **Sección de seguridad, sin suavizar el mensaje de spec 9.3**: CronDok monta el socket de
   Docker del host → quien controle el proceso controla el host. Recomendación explícita:
   correr en un host/VM dedicado, o Docker rootless; mencionar como mitigación futura (no
   construida) un socket-proxy con allowlist (`wolflu05/docker-socket-proxy`) restringido a
   `containers/*`.
4. Backup: qué archivos respaldar (`data/crondok.db`, `data/.master_key` — sin la master key
   los secrets cifrados son irrecuperables, sección 9.1).
5. Enlaces a `docs/ESPECIFICACION_TECNICA_CRONDOK.md`, `backend/README.md` (desarrollo local)
   y licencia (MIT, ya declarada en la spec).

**Depende de:** 4.1, 4.2 (los comandos documentados deben ser los reales, ya probados).

---

## Paso 4.4 - Release v0.1.0 en GitHub

**Bloqueante conocido:** este repositorio **no tiene remoto configurado todavía** (`git remote -v`
vacío). Este paso no se ejecuta sin que el usuario decida y confirme el remoto — crear/enlazar
el repo en GitHub es una decisión suya, no una que se tome de forma autónoma.

1. Confirmar con el usuario el repositorio de GitHub de destino (nuevo o existente) y
   conectar el remoto (`git remote add origin ...`).
2. Push de `main` con el historial completo de las fases 0-3 + el commit de esta fase.
3. Tag anotado `v0.1.0` con resumen del MVP; `gh release create v0.1.0` con notas generadas a
   partir del Registro de Cambios de `docs/TODO.md` (fases 0-4).
4. Verificación: la release aparece en GitHub con el changelog; CI (`ci-backend`/`ci-frontend`)
   corre verde sobre `main` tras el push.

**Depende de:** 4.1-4.3 completos y commiteados. **Acción que requiere confirmación explícita**
antes de ejecutar (push, tag y release son visibles externamente y difíciles de revertir).

---

## Orden de ejecución

```
4.1 ──► 4.2 ──► 4.3 ──► 4.4 (requiere confirmación + remoto)
```
Secuencial: cada paso depende del anterior (el compose necesita la imagen; los docs
documentan comandos ya probados; la release cierra con todo lo demás commiteado).

## Riesgos de la fase

| Riesgo | Mitigación |
|--------|------------|
| Servir el build de React desde FastAPI rompe el refresh en rutas cliente (`/projects/5` → 404) | Catch-all `GET /{full_path:path}` que devuelve `index.html` salvo bajo `/api` |
| `static_dir` activo interfiere con los tests (`create_app()` sin build de frontend) | Montaje condicional: solo si el directorio existe; default `None` en `Settings` |
| Imagen de producción con dependencias de desarrollo (poetry dev-deps, node_modules) | Multi-stage: el stage final solo instala `--only main`; `.dockerignore` agresivo |
| Confundir "un solo comando" con ocultar el riesgo del socket | README explícito, mismo tono que spec 9.3, sin suavizarlo |
| Release antes de tener remoto | 4.4 explícitamente bloqueada hasta confirmación + `git remote add` |
| Docker-out-of-Docker: bind mounts del workspace resueltos contra el contenedor equivocado | `host_data_dir`/`CRONDOK_HOST_DATA_DIR` traduce la ruta; verificado con un job real end-to-end dentro de Docker |
| Un directorio `docker/` en la raíz shadowea el paquete pip `docker` para mypy (corre desde la raíz vía pre-commit) | Renombrado a `deploy/entrypoint.sh`; evitar nombres de carpeta que colisionen con paquetes Python importados |

## Al terminar la fase

- [ ] Marcar 4.1-4.3 como `[x]` en `docs/TODO.md` (4.4 queda `[ ]` hasta tener remoto y
  confirmación), tabla de progreso (Fase 4 → 3/4 o 4/4 si se completa 4.4) y registro de cambios.
- [ ] Commit `feat: dockerization and deployment docs (phase 4)`.
