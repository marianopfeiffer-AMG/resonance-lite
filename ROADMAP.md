# ROADMAP.md — Resonance Lite

> Hoja de ruta ejecutable derivada de `SPEC.md` v0.4. Cada bullet es una tarea chica que termina en **un commit** (Conventional Commits, ver `CODESTYLE.md`).
> Formato: `- [ ] <tarea> — §<sección del SPEC> — commit: <tipo(scope): mensaje>`.
> Regla: no se arranca una fase sin la anterior en verde (CI pasando + criterios de la fase cumplidos).
> Las tareas marcadas **(Nano)** son manuales: cuentas, dinero, decisiones. Todo lo demás lo puede ejecutar un agente de código.

---

## Fase 0 — Preparación (Nano, antes de escribir código)
- [x] **(Nano)** Decidir el owner del repo → cuenta personal `marianopfeiffer-AMG` (2026-10-25) — §14 ABIERTO-5.
- [x] **(Nano)** Crear el repo **privado** `resonance-lite` bajo ese owner — §10.0.1.
- [ ] **(Nano)** Verificar que `resonance-lite` y `rlite` están libres en PyPI y registrar un *pending publisher* (Trusted Publishing) sin publicar nada — §8.1, SUPUESTO-9.
- [ ] **(Nano)** Elegir el canal de reportes de seguridad (recomendado: GitHub Private Vulnerability Reporting) — ABIERTO-6.
- [ ] ~~Crear una cuenta de ElevenLabs dedicada para tests~~ → **no hace falta** (decisión de Nano 2026-10-25: el sistema le pide las claves a cada usuario; ninguna clave de Nano entra al repo ni a sus secrets). El smoke test nocturno queda opcional y apagado por defecto (Fase 13).
- [ ] **(Nano)** Decidir si hay más testers además del amigo — ABIERTO-7.
- [ ] **(Nano)** Correr la prueba de bloqueo de privados (subir un video de prueba por API e intentar publicarlo) — ABIERTO-1.

## Fase 1 — Esqueleto del repo y CI
- [x] Estructura de carpetas de §10.3 (`plugin/`, `cli/`, `schemas/`, `examples/`, `docs/`, `tests/`, `.github/`) con READMEs placeholder — commit: `chore: scaffold repository layout`
- [x] `LICENSE` MIT (copyright Mariano Pfeiffer) + `SECURITY.md` + `CODE_OF_CONDUCT.md` + `SUPPORT.md` (versión beta) + `CONTRIBUTING.md` — §10.4, §15 — commit: `docs: add license and community files`
- [x] `.gitignore` (jobs, secrets, tokens, `.venv`, **`SPEC.md`, `CAVEMAN.md`**) — §8, §10.0.4 — commit: `chore: add gitignore`
- [x] `cli/pyproject.toml` con Python `>=3.12,<3.14`, dependencias con tope superior, entrypoints `rlite` (y alias `rl`) — §8.1, §10.1 — commit: `build(cli): add pyproject with bounded dependencies`
- [x] `uv.lock` + `compat.toml` (fuente única del rango plugin↔CLI) — §10.1 — commit: `build: add lockfile and compat source`
- [x] `.claude-plugin/marketplace.json` + `plugin/.claude-plugin/plugin.json` (con `version` y `metadata.requires_cli`) — §10.1 — commit: `feat(plugin): add marketplace and plugin manifests`
- [x] Workflow CI: ruff + mypy + pytest en macOS y Ubuntu + `claude plugin validate --strict` — §15.3 — commit: `ci: add lint, type and test workflow`
- [x] Job de CI "guard": rechaza en `plugin/` todo lo que no sea `.md`/`.txt`/`plugin.json`, `hooks`, `mcpServers`, `bin/`, monitores y `` !` `` en SKILL.md — §8.1 — commit: `ci: forbid executable content in plugin`
- [x] Job de CI "leak": grep de rutas personales y patrones de keys + patrones privados desde el secret `LEAK_PATTERNS` + gitleaks — §8, §10.0.4 — commit: `ci: add secret and infra leak checks`
- [x] `CODEOWNERS` (`plugin/` y `cli/src/rl/providers/` → Nano) + plantillas de issues (bug, feature, `beta-feedback`) + plantilla de PR — §8.1, §10.0.2 — commit: `chore: add codeowners and issue templates`
- [x] Workflow para subir `plugin.json → version` y copiar `compat.toml` a `metadata.requires_cli` y a SKILL.md en cada tag — §10.1 — commit: `ci: sync plugin version and compat range on release`

## Fase 2 — Núcleo: plan, estado, validación
- [x] `schemas/plan.v1.json` completo (modos, engine, use, demo, audio, assembly, visual, metadata) — §4.1 — commit: `feat(schema): add plan v1 json schema`
- [ ] `schemas/state.v1.json` (ítems con hash, status, provider_job_id, outputs, cost, error) — §4.1 — se define cuando existan los ítems reales (Fase 3-5); hoy el estado se valida en código — commit: `feat(schema): add state v1 json schema`
- [x] `rl/plan.py`: carga, validación de schema, resolución de `{duration}` — §4.1 — commit: `feat(core): load and resolve plan`
- [x] `rl/state.py`: un archivo por paso, escritura atómica (tmp + `os.replace`) bajo `fcntl.flock` — §4.1 — commit: `feat(core): atomic per-step state store`
- [x] `rl/locks.py`: locks por paso con `flock` (código 75 si está tomado) — §4.1, §5 — commit: `feat(core): per-step flock locks`
- [x] `rl/hashing.py`: hash por ítem según la tabla de §4.1, con invalidación en cascada (still → clips) — commit: `feat(core): per-item input hashing`
- [x] `rl/stage.py`: stage derivado del estado + `approval.json` + regla "plan/still cambió → código 12" — §4.5 — commit: `feat(core): derive job stage from state`
- [x] `rl/validate.py`: todas las reglas de §4.4 con detección de negaciones, niveles bloquea/advertencia y salida `--json` — commit: `feat(validate): implement plan validation rules`
- [x] Listas léxicas en `cli/src/rl/rules/*.txt` (dentro del paquete, porque las usa el validador) + lista de energía + términos de evento — §4.4 — commit: `feat(validate): add lexical rule lists`
- [x] Tests: negaciones ("no sudden sounds" pasa), thunder solo en events, BPM band, título con 4K, demo 10-15 min — commit: `test(validate): cover lexical and structural rules`
- [x] `rl/exitcodes.py` + `ArgumentParser.error` → 64 — §5 — commit: `feat(cli): define exit codes`
- [x] `rl/cli.py`: `new`, `validate`, `status` (humano y `--json`) — §5 — commit: `feat(cli): add new, validate and status commands`

## Fase 3 — Proveedores
- [x] `rl/providers/base.py`: interfaces `SoundProvider`, `MusicProvider`, `ImageProvider`/`VideoProvider`, `Publisher`, con `resumable` y tabla de errores → código — §7.0 — commit: `feat(providers): define provider interfaces`
- [x] `rl/secrets.py`: claves **del usuario final** en el llavero de su SO (con fallback a archivo 0600 opcional), cargadas por él con `rlite key set <proveedor>` en su propia terminal o desde el portapapeles; nunca por el chat; enmascarado en logs — §8 — commit: `feat(core): keychain-backed secrets with masked logging`
- [x] `rl/budget.py`: reserva antes de cada llamada, tope por job y mes en USD, `--over-budget` con confirmación TTY y registro en `job.log` — §8 — commit: `feat(core): per-call budget enforcement`
- [x] `rl/providers/elevenlabs.py`: SFX (`loop`), Music (≤ 600 s, `force_instrumental`), backoff, `quota_exceeded` → 22, validación de respuesta, saldo — §7.1 — commit: `feat(providers): add elevenlabs provider`
- [x] `rl/providers/higgsfield.py`: `create --json` → guardar id → `wait <id>`, `generate cost`, `account status`, chequeo de versión del CLI — §7.3 — commit: `feat(providers): add higgsfield provider`
- [x] `rl/providers/apiframe.py`: `requests` + UA de navegador, submit sin reintento ciego, poll, reanudación por `jobId`, deshabilitado por defecto — §7.2 — commit: `feat(providers): add optional apiframe suno provider`
- [x] `rl/providers/registry.py` + `rl providers list|enable|disable` (reconocimiento de riesgos en TTY) — §7.0 — commit: `feat(cli): manage optional providers`
- [x] `rl/pricing.yaml` con fecha + conversión de créditos a USD por plan — §7.1, §13.1 — commit: `feat(estimate): add dated pricing table`
- [x] `rl/estimate.py` + `rl estimate [--monthly N --mode m]`: créditos, USD, tiempo, disco pico, comparación con saldo — §5, §13.1 — commit: `feat(estimate): cost, time and disk estimation`
- [x] Tests de contrato con mocks por proveedor (incluye: el timeout no re-crea el job; quota → 22; Suno sin activar → validate falla) — commit: `test(providers): add contract tests with mocks`

## Fase 4 — Audio
- [x] `rl/audio/common.py`: trim de silencio, crossfade, cierre en anillo, medición de LUFS/peak/silencios — §4.3 — commit: `feat(audio): shared ffmpeg audio helpers`
- [x] `rl/audio/ambient.py`: Receta A (3 capas de largos coprimos en anillo, tile con `aloop`, AAC una vez) — §4.3.A — commit: `feat(audio): ambient recipe with coprime ring layers`
- [x] `rl/audio/events.py`: Receta A+ (eventos esparcidos con ganancia y limiter propios) — §4.3.A+ — commit: `feat(audio): sparse event layer`
- [x] `rl/audio/functional.py`: secciones, `bed_min_s`, anillo, tile sin repetir secciones contiguas — §4.3.B — commit: `feat(audio): functional recipe`
- [x] `rl/audio/playlist.py`: ElevenLabs (default) y Suno, normalización por track, crossfade, −14 LUFS, `timestamps.txt`, `assembly.exclude` — §4.3.C — commit: `feat(audio): playlist assembly`
- [x] `rl/audio/takes.py`: programación dinámica de selección de tomas (solo Suno) + advertencia > 6 dB — §4.3.C — commit: `feat(audio): take selection by dynamic programming`
- [x] `rl audio <job> [--assemble-only] [--regen-stale]` — §5 — commit: `feat(cli): add audio command`
- [x] Tests con audio sintético (tonos/ruido): anillo sin clic, período combinado, exclude sin regenerar, DP con casos conocidos — commit: `test(audio): synthetic audio pipeline tests`

## Fase 5 — Visual
- [x] `rl/visual/still.py` + `rl still <job> [--reroll]` — §4.6 — commit: `feat(visual): still generation`
- [x] `rl/visual/chain.py`: cadena de clips desde el último frame (port de `chain.sh` a Python), reanudable por id — §4.6 — commit: `feat(visual): resumable clip chain`
- [x] `rl/visual/ring.py`: clip de cierre (start = último frame de clip_N, end = primer frame de clip_01) + concat con micro-crossfade — §4.6 — commit: `feat(visual): closed-ring loop clip`
- [x] `rl/visual/stabilize_close.py`: port parametrizado (un warp LANCZOS4, un encode) — §4.6 — commit: `feat(visual): single-pass stabilize and close`
- [x] Encode final del loop (crf 20 veryfast, recorte del frame duplicado) — §4.6 — commit: `feat(visual): final loop encode`
- [x] Tier `byo` (imagen y clip) con copia al job — §4.6 — commit: `feat(visual): bring-your-own media tier`
- [x] `rl visual <job>` — commit: `feat(cli): add visual command`
- [x] Tests con video sintético: cruce del loop ≤ 1,1× el movimiento normal, nitidez ≥ 75% — commit: `test(visual): loop seam and sharpness checks`

## Fase 6 — Build, QC y entregables
- [x] `rl/build.py`: tile `-c copy` + mux del audio, `.partial` + validación ffprobe ±0,5 s; tier `still` con `-loop 1 -tune stillimage` — §4.7 — commit: `feat(build): tile-copy master assembly`
- [x] `rl/thumbnail.py`: 3 plantillas, duración real, etiqueta por modo, fuentes OFL — §4.7 — commit: `feat(build): templated thumbnails`
- [x] `rl/deliver.py` (antes `upload_md.py`): `UPLOAD.md` (metadata resuelta, capítulos, sintético, atribución de plan gratis, checklist §13.3) + `provenance.json` — §4.7 — commit: `feat(build): upload sheet and provenance`
- [x] `rl/qc.py` + `rl qc <job>`: frames de minutos lejanos + métricas de video y audio (§3.2 paso 10, §4.3.0) — commit: `feat(qc): objective quality checks`
- [x] Tests end-to-end con medios sintéticos y proveedores mockeados: `new → … → final/` — commit: `test: end-to-end pipeline with mocks`

## Fase 7 — Orquestación
- [x] `rl approve <job>` (hash del plan + sha del still) — §4.5 — commit: `feat(cli): record approvals`
- [x] `rl/detach.py` + `rl run [--detach] [--from] [--regen-stale]`: audio ∥ visual → build → qc, `start_new_session`, pidfile, heartbeat — §3.2, §9 — commit: `feat(run): detached orchestrated run`
- [x] `caffeinate -ims -w <pid>` en darwin + aviso de batería (`pmset -g batt`) — §9 — commit: `feat(run): keep mac awake during runs`
- [x] `rl wait <job> [--timeout]` (0 / 11 / código de error) — §5 — commit: `feat(cli): add wait command`
- [x] `rl repair <job>` y `rl clean <job> [--keep-final]` — §5 — commit: `feat(cli): add repair and clean commands`
- [x] Test de reanudación: matar el run a mitad de la cadena y de Suno → reanudar sin crear jobs nuevos en los mocks — commit: `test(run): resume without double charges`

## Fase 8 — Setup y diagnóstico
- [x] `rl doctor [--quick] [--json] [--report]`: dependencias, versión de Higgsfield, saldos, disco, corriente, calibración, chequeo de versión nueva (tag git en beta / PyPI en público, caché 24 h, `RL_NO_UPDATE_CHECK`) — §5, §10.0.1, §10.2 — commit: `feat(doctor): environment diagnostics`
- [x] `rl init`: `channel.yaml`, `RL_HOME` y backlog sembrado; **no maneja claves** (eso es `rlite key set`, que corre el usuario en su terminal), `RL_HOME`, `backlog.md` sembrado, aviso de plan gratis — §10.2 — commit: `feat(cli): interactive init`
- [x] `rl purge` — §5 — commit: `feat(cli): add purge command`
- [x] `rl next` (backlog) — §3.3 — commit: `feat(cli): pick next backlog idea`

## Fase 9 — Skill y knowledge
- [x] `plugin/skills/resonance-lite/SKILL.md`: flujo §3.2, subcomandos `setup` / `demo` / `resume` / `next`, tablas 4.2 y 4.3.0, manejo de cada código de salida, reglas duras de §6, `allowed-tools: Bash(rl:*), Bash(rlite:*), Read, Write, Edit` — commit: `feat(plugin): add resonance-lite skill`
- [x] Portar `COMPOSITION-RULES.md` (regla 2 reescrita según §4.3.0) y `AUDIENCE-SEO.md` (sin 4K, sin marca) con encabezado de atribución — §6, §10.4 — commit: `feat(plugin): port composition and audience knowledge`
- [x] Portar `PLAYLIST-COMPOSITION.md`, `motion-safe.md`, `prompt-templates.md` + escribir `niches-seed.md` — §6, §13.2 — commit: `feat(plugin): port playlist and visual knowledge`
- [ ] Revisión manual de Nano de todo el knowledge portado **(Nano)** — §15.4

## Fase 10 — Documentación y ejemplos
- [x] `README.md` final (ver el borrador en la raíz) con comandos de instalación de la beta — §10.0.1 — commit: `docs: finalize readme for beta`
- [x] `README.es.md` (traducción) — commit: `docs: add spanish readme`
- [x] `docs/ARCHITECTURE.md` sanitizado desde el SPEC (sin infraestructura de Nano) — §10.3 — commit: `docs: add public architecture overview`
- [x] `docs/costs.md`, `docs/youtube-policy.md`, `docs/upload-in-studio.md`, `docs/troubleshooting.md`, `docs/providers/*.md` — commit: `docs: add operating guides`
- [x] `examples/`: un `plan.json` por modo (la demo sin Higgsfield usa una imagen del propio usuario: el plugin no puede llevar binarios) — commit: `docs: add examples`

## Fase 11 — Prueba real de Nano (antes de dárselo al amigo)
- [ ] **(Nano)** Instalar desde cero en su Mac siguiendo solo el README (repo privado) y verificar SUPUESTO-10. Nano carga **su propia** key como cualquier usuario (`rlite key set elevenlabs` en su terminal); nunca se la pasa a Claude ni queda en el repo.
- [ ] **(Nano)** Correr `demo` y un video por modo con presupuesto bajo (`RL_MAX_MIN`, `RL_MAX_TRACKS`).
- [ ] **(Nano)** Medir el costo real de SFX y actualizar `pricing.yaml` — SUPUESTO-2 — commit: `fix(estimate): calibrate elevenlabs sfx pricing`
- [ ] **(Nano)** Escucha de prueba de la Receta A+ (tormenta) — SUPUESTO-5.
- [ ] Tag `cli-v0.9.0` (beta) — commit: `chore(release): cli v0.9.0 beta`

## Fase 12 — Beta privada con el amigo
- [ ] **(Nano)** Invitar al amigo como colaborador (Read/Triage) — §10.0.1.
- [ ] **(Amigo)** Setup desde cero; Nano anota cada intervención como issue `docs` — §10.0.2.
- [ ] **(Amigo)** 1 video por modo + reanudación forzada + edición de dirección + subida en Studio — §10.0.2.
- [ ] **(Amigo)** Un issue `beta-feedback` por video.
- [ ] Corregir lo que surja (`fix:` / `docs:`) y sacar betas `cli-v0.9.x`.
- [ ] Verificar los criterios de salida de §10.0.3 (checklist en un issue fijado).

## Fase 13 — Lanzamiento público
- [ ] Verificar que ningún ref (incluidos PRs cerrados) contenga commits con el email personal; si los hay, publicar desde un repo nuevo con `main` limpio — §10.0.4 paso 2b.
- [ ] Ejecutar el checklist de §10.0.4 (gitleaks sobre el historial, trusted publisher, `cli-v1.0.0` a PyPI, README con PyPI, Discussions/stale/smoke test/CodeQL, repo público, migración del amigo).
- [ ] Workflow de release a PyPI con environment `pypi` + revisor + attestations — §8.1 — commit: `ci: add pypi trusted publishing release`
- [ ] Workflow de smoke test nocturno **opcional**: solo corre si el mantenedor configura por su cuenta el secret `RL_SECRET_ELEVENLABS`; sin él, se saltea sin fallar — §15.3 — commit: `ci: add optional nightly provider smoke test`
- [ ] `SUPPORT.md` versión pública ("best effort, sin SLA") — §15.2 — commit: `docs: public support policy`
- [ ] **(Nano)** Anuncio (canal Resonance, redes).

## v1.1 — Después del lanzamiento (si ABIERTO-1 lo permite)
- [ ] `rl auth youtube` (scopes `youtube.upload` + `youtube.readonly`, token en el llavero, `channel_id`) — §7.4
- [ ] `rl upload` con sesión resumable persistida, `video_id` inmediato, thumbnail como sub-paso, `containsSyntheticMedia` — §7.4
