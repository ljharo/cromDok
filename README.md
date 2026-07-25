# CronDok

Scheduler de tareas **self-hosted**, open source y auto-contenido: define runners
(scripts en Bash, Python o Node.js) con su propia expresión cron, cada uno ejecutado
en un contenedor Docker efímero y aislado. Gestiona proyectos, variables de entorno
cifradas, ejecuciones manuales o programadas y sus logs desde una interfaz web única.

Ver `docs/ESPECIFICACION_TECNICA_CRONDOK.md` para la arquitectura completa.

## Quickstart

Requisitos: Docker y Docker Compose (v2). CronDok se levanta con **un solo comando**:

```bash
git clone <este-repo> crondok && cd crondok
docker compose up -d
```

El primer arranque crea un usuario `admin` con una contraseña generada, mostrada
**una única vez** en los logs:

```bash
docker compose logs crondok | grep "First boot"
```

Abre `http://localhost:8000`, entra con esas credenciales y cámbialas.

## Variables de entorno

Todas usan el prefijo `CRONDOK_` (ver `backend/src/cron_dok/config.py`, fuente de
verdad). Se configuran en un `.env` junto a `docker-compose.yml`.

| Variable                      | Default                                 | Propósito                                                                                                                                                                                               |
| ----------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CRONDOK_MASTER_KEY`          | _(autogenerada)_                        | Clave Fernet para cifrar variables de entorno en reposo. Si no se define, se genera en el primer arranque y se persiste en `data/.master_key`. Fíjala en producción si vas a migrar de host (spec 9.1). |
| `CRONDOK_MAX_CONCURRENT_JOBS` | `4`                                     | Ejecuciones concurrentes máximas (semáforo del executor).                                                                                                                                               |
| `CRONDOK_LOG_RETENTION_DAYS`  | `30`                                    | Días de retención de ejecuciones/logs terminados antes de la purga diaria.                                                                                                                              |
| `CRONDOK_RATE_LIMIT_TRIGGERS` | `100`                                   | Límite de `POST /triggers/{id}` por identidad (req/min).                                                                                                                                                |
| `CRONDOK_WEBHOOK_URL`         | _(vacío = no-op)_                       | Webhook opcional notificado en cada ejecución fallida.                                                                                                                                                  |
| `CRONDOK_HOST_DATA_DIR`       | `${PWD}/data` (compose lo calcula solo) | Path **absoluto en el host** que respalda `data/`. Ver "Docker-out-of-Docker" abajo — no suele hacer falta tocarlo.                                                                                     |

## Seguridad: el riesgo del socket de Docker

Para lanzar los jobs, CronDok monta `/var/run/docker.sock` en su propio contenedor
(patrón _Docker-out-of-Docker_). Esto significa, sin rodeos:

> **Quien controle el proceso de CronDok tiene control de root sobre el host.**
> Un escape de sandbox o una vulnerabilidad en la API equivale a compromiso total
> del host donde corre.

Cada ejecución de un runner sí está aislada (sandbox real): contenedor efímero
(`--rm`), límites de memoria/CPU/PIDs, `--network none` salvo que el runner lo pida
explícitamente, filesystem de solo `/workspace`, usuario no-root (`nobody`,
UID 65534) y timeout forzado. Pero el propio proceso de CronDok **no** se sandboxea
a sí mismo — no tendría sentido: ya tiene el socket.

**Recomendación:** corre CronDok en un host o VM dedicado (no en una máquina que
también aloje otras cargas sensibles), o con Docker rootless. La ruta de escalado
documentada (no construida en el MVP) es un socket-proxy con allowlist, por ejemplo
[`wolflu05/docker-socket-proxy`](https://github.com/wolfy1339/docker-socket-proxy),
restringido a los endpoints `containers/*` de la API de Docker.

### Docker-out-of-Docker: por qué existe `CRONDOK_HOST_DATA_DIR`

Cuando CronDok lanza el contenedor de un job, le pide al daemon de Docker que monte
el workspace del script. El daemon resuelve esa ruta contra el **filesystem del
host**, no contra el propio contenedor de CronDok — por eso el volumen de datos debe
vivir en una ruta absoluta del host, y esa misma ruta se le pasa a CronDok como
`CRONDOK_HOST_DATA_DIR` para que traduzca las rutas de los workspaces. `docker-compose.yml`
ya lo calcula solo con `${PWD}/data`; solo hace falta tocarlo si mueves `data/` a
otro sitio o corres el compose desde un directorio distinto al del repo.

## Backup

Para poder restaurar CronDok en otra máquina, respalda:

- `data/crondok.db` (+ `-wal`/`-shm` si existen) — proyectos, runners, ejecuciones, usuarios.
- `data/.master_key` — **sin esta clave, las variables de entorno cifradas son
  irrecuperables** (spec 9.1). Guárdala en un lugar seguro, separado de la base de
  datos si es posible.

## Desarrollo local

Ver `backend/README.md` (backend con Poetry) y `frontend/` (Vite + React) para
correr cada parte fuera de Docker, con hot-reload.

## Licencia

MIT.
