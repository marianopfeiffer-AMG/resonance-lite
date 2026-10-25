# Architecture

Resonance Lite has two parts that ship separately:

| Part | What it is | Ships as |
|---|---|---|
| **Plugin** (`plugin/`) | A Claude Code skill plus knowledge files. Markdown only: it never runs code. | Claude Code marketplace (this repository) |
| **CLI** (`cli/`, command `rlite`) | Everything that spends money or touches media: providers, ffmpeg, state, budget. | Python package installed with `uv tool` |

Claude is the creative director: it writes a **plan**. `rlite` executes it.

## Flow
```
idea → plan.json (Claude) → validate → estimate → still → checkpoint (user) → approve
     → run --detach:  audio ∥ visual  →  build  →  qc
     → final/ (video.mp4, thumbnail.png, UPLOAD.md, provenance.json) → user uploads in Studio
```

## Data
Each job is a folder under `RL_HOME/jobs/<id>/`:

- `plan.json`: written only by Claude. JSON Schema: `cli/src/rl/schemas/plan.v1.json`.
- `state/<step>.json`: written only by `rlite`, one file per step (validate, still, audio, visual,
  build, qc, approval, cost, run). Writes are atomic (temp file + rename) under `flock`, so audio
  and visual can run in parallel without overwriting each other.
- `audio/`, `visual/`, `final/`: media.

The **stage** of a job (draft, validated, still_ready, approved, producing, built, delivered,
failed) is derived from the state files, never stored, so it cannot drift.

## Paying once
- Every generated item (sound clip, music section, track, still, video clip) carries a hash of the
  inputs that produce it. Finished items with the same hash are reused; a changed item that was
  already paid for is **stale** and needs explicit consent to regenerate.
- Resumable providers (Higgsfield, Apiframe): the provider job id is saved before waiting; a resume
  polls that job instead of creating a new one.
- Non-resumable providers (ElevenLabs): a timed-out call is counted as spent and never retried
  automatically.
- Every paid call first **reserves** its estimated cost against a per-job and per-month cap in USD.
  Raising a cap needs a typed confirmation in the user's own terminal.
- Approval records the hash of the plan and of the still. If either changes, production stops until
  the user approves again.

## Audio recipes
- **Ambient**: 6-12 short sound-effect clips → three ring-closed layers of N-1, N and N+1 clips in
  different orders → mixed with offsets and tiled to the full duration. The combined pattern only
  repeats after hours. Optional sparse events (distant thunder) at random, level-capped intervals.
- **Functional**: music sections crossfaded, closed into a ring, tiled to length.
- **Playlist**: per-track loudness normalization, crossfades, -14 LUFS, chapters; with Suno (two
  takes per track) a dynamic-programming pass picks the takes that minimize level jumps.

## Visual
- **cinemagraph**: still → chain of 5-second clips (each starts from the previous clip's last frame)
  → a closing clip that ends on the first frame → micro-crossfade concat → stabilization and loop
  closure in a single warp and encode → one delivery encode. The final video tiles the loop with
  `-c copy` (minutes, not hours). No camera movement.
- **still**: a single image encoded with `-tune stillimage`.
- **byo**: the user's own image or clip.

## Security
- API keys are the user's: OS keychain, entered in the user's own terminal, never through the chat.
- The plugin is Markdown-only; CI rejects hooks, MCP servers, executables or shell injection in it.
- No telemetry. The only call that is not to a configured provider is an optional, cached update
  check against PyPI (`RL_NO_UPDATE_CHECK=1` disables it).
