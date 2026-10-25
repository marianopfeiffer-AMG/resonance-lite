# CODESTYLE.md — Resonance Lite

Reglas para cualquier persona o agente que escriba código en este repo. Si una regla choca con `SPEC.md`, gana el SPEC y se corrige este archivo.

## Idioma
- **Todo el código en inglés:** nombres, comentarios, mensajes de commit, mensajes de log y de error del CLI, docstrings.
- La skill (`SKILL.md`) y el knowledge se escriben en inglés. Claude le responde al usuario en su idioma igual.
- La documentación de usuario: `README.md` en inglés + `README.es.md`.

## Python
- Python **3.12**. Type hints en todas las funciones públicas. `mypy --strict` sobre `cli/src/rl/`.
- Formato y lint con **ruff** (`ruff format` + `ruff check`, line length 100). CI falla si no pasa.
- Estructura: un módulo = una responsabilidad (ver el árbol de §10.3). Sin "utils.py" cajón de sastre.
- **Sin dependencias nuevas sin justificar** en el PR. Cada una con rango con tope superior en `pyproject.toml`.
- Preferir la stdlib: `argparse`, `subprocess`, `json`, `pathlib`, `fcntl`. `requests` solo en proveedores HTTP.
- Rutas con `pathlib.Path`. **Nunca** rutas absolutas hardcodeadas; todo sale de `RL_HOME` / `RL_CONFIG`.

## Comentarios
- Solo comentarios **técnicos y necesarios**: el *por qué* de algo no obvio (un workaround de un proveedor, una fórmula, un límite de una API con su fuente).
- Nada de comentarios que repiten el código, ni historial ("antes hacía X"), ni TODOs sin issue (`# TODO(#123): ...`).
- Docstring corto en cada función pública: qué hace, qué devuelve, qué excepciones lanza.

## Errores y salida
- Cada error esperable es una excepción tipada (`RlError` y subclases) con su **código de salida de §5**. Nada de `sys.exit` disperso: el código lo mapea un solo lugar (`cli.py`).
- Toda excepción no manejada → código 1 con un mensaje que pide `rlite doctor --report`.
- Los comandos que consume Claude aceptan `--json` y escriben **solo JSON** en stdout. Los logs humanos van a stderr.
- Mensajes de error accionables: qué pasó + qué hacer ("Higgsfield session expired. Run: higgsfield auth login").

## Estado, dinero y procesos externos (reglas duras)
- El estado se escribe **solo** vía `rl.state` (atómico + flock). Prohibido `json.dump` directo sobre archivos de `state/`.
- **Toda llamada paga pasa por `rl.budget.reserve()` antes de ejecutarse.** Un PR que llama a un proveedor sin reserva no se aprueba.
- Proveedores reanudables: guardar `provider_job_id` en el estado **antes** de esperar. Nunca reintentar un `create` después de un timeout sin consultar el id.
- Subprocesos (`ffmpeg`, `higgsfield`) con `subprocess.run([...], check=True)` y lista de args. **Nunca `shell=True`.** Nunca secretos en argv.
- ffmpeg siempre con `-nostdin -y -v error` y salida a `.partial`, renombrada después de validar.
- Secretos: solo vía `rl.secrets`. Jamás en logs, excepciones, `state/` ni argv.

## Tests
- `pytest`. Cada módulo con su test. Sin red en CI: proveedores mockeados (`responses` / fakes del CLI higgsfield).
- Medios sintéticos generados en el test con ffmpeg (tonos, ruido, video `testsrc`). Nada de archivos binarios grandes en el repo.
- Todo bug que hizo cobrar de más tiene un test de regresión antes de cerrarse.

## Commits y PRs
- **Conventional Commits:** `feat(scope):`, `fix(scope):`, `docs:`, `test(scope):`, `refactor(scope):`, `ci:`, `build:`, `chore:`. Scopes: `core`, `cli`, `validate`, `estimate`, `providers`, `audio`, `visual`, `build`, `qc`, `run`, `doctor`, `plugin`, `schema`.
- Un commit = una tarea del ROADMAP. El mensaje en imperativo y en inglés.
- Los PRs que tocan `plugin/` llevan la etiqueta `skill-change` y revisión de Nano.
- Cambios que rompen `plan.json` → `feat!:` + migración en `rl migrate` + versión mayor.

## Production-ready
- Sin `print` de debug, sin código muerto, sin flags experimentales sin documentar.
- Todo comando nuevo documentado en `--help` y en el README antes del merge.
- Ningún valor mágico suelto: límites de API, precios y umbrales de QC en constantes con nombre o en `pricing.yaml`, con su fuente.
