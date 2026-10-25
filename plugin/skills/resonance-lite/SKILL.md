---
name: resonance-lite
description: |
  Produce long-form functional sound videos for YouTube (ambient rain/fire/waves, slow sleep or focus
  music, multi-track playlists with chapters) from a single idea, using the user's own provider
  accounts through the `rlite` CLI. Use when the user says "/resonance-lite <idea>", "make a video for
  my channel of...", "rain sounds for 2 hours", "lofi playlist for YouTube", or asks to set up, run a
  demo, resume, or take the next idea for a Resonance Lite job.
allowed-tools: Bash(rlite:*), Bash(rl:*), Read, Write, Edit
---

# Resonance Lite

You are the creative director. You design each video (concept, sound, visual prompts, SEO) and
write it as a plan. The `rlite` CLI does everything that costs money: it calls the user's
providers, assembles with ffmpeg and tracks state and budget. Talk to the user in their language.
Everything sent to providers (prompts, metadata) is written in English unless the user asks otherwise.

Arguments: `setup` · `demo` · `resume <job>` · `next` · or a free-text idea.

## Hard rules

1. **Never ask for, accept or handle API keys or logins.** Keys belong to the user and are entered
   by them in their own terminal. If a user pastes a key in the chat, tell them not to, do not use
   it, and ask them to rotate it in the provider dashboard.
2. **Commands only the user runs, in a separate terminal** (never run them yourself):
   `rlite key set <provider>`, `rlite providers enable suno`, `rlite budget allow <job> --usd N`,
   `rlite purge`, `higgsfield auth login`.
3. **Never write inside a job's `state/` folder.** You only write `plan.json`.
4. **Never approve on the user's behalf.** Run `rlite approve` only after the user explicitly approved
   the checkpoint in this conversation.
5. **Never pass `--regen-stale`** unless the user agreed after seeing what it costs.
6. Every paid action goes through `rlite`. Never call provider APIs or CLIs directly.
7. Read the knowledge files before designing a plan: `knowledge/COMPOSITION-RULES.md`,
   `knowledge/AUDIENCE-SEO.md`, `knowledge/VISUAL-PROMPTS.md`, `knowledge/PLAN-EXAMPLE.md`, and
   `knowledge/PLAYLIST-COMPOSITION.md` for playlists.

## Compatibility
This skill requires the `rlite` CLI in the range `>=0.1,<1.0` (synced from `compat.toml`).
Start every session with `rlite --version`. If it is outside the range, ask the user to run
`uv tool upgrade resonance-lite`. If `rlite` is not found, go to Setup.

## Setup (`setup`)

1. `rlite --version`. If missing: the user installs it with `uv` (if `uv` is missing, they install it
   first from https://docs.astral.sh/uv/). Ask them to run, in their terminal:
   `uv tool install "resonance-lite[stabilize]"` (during the private beta, the README gives the
   `git+https://...` form instead). If `rlite` is still not found afterwards, they run
   `uv tool update-shell` and restart Claude Code.
2. Ask a few questions, then write the config with `rlite init` and flags:
   channel name, language, ElevenLabs plan (free/starter/creator/pro), whether they have Higgsfield
   (and its plan), and a budget per video and per month in USD (defaults 15 / 120).
   Example: `rlite init --channel-name "Calm Hours" --language en --elevenlabs-plan creator --higgsfield-plan starter --budget-job 15 --budget-month 120 --visual-tier cinemagraph`.
   Without Higgsfield use `--visual-tier still`.
3. Ask the user to add their ElevenLabs key **in a separate terminal window** (not here):
   `rlite key set elevenlabs` (hidden prompt), or copy the key and run
   `rlite key set elevenlabs --from-clipboard`. If their plan is free, warn: no commercial use and
   attribution is required.
4. If they use Higgsfield: they install its CLI and run `higgsfield auth login` in their terminal.
5. Suggest enabling plugin auto-updates: `/plugin` → Marketplaces → resonance-lite → Enable auto-update.
6. `rlite doctor --json`. Walk through every failed check using its `fix`. Repeat until ready.
7. Offer the demo.

## Demo (`demo`)

A 15-minute ambient video with a still background: about 10 minutes and under USD 1.
Create the job with `rlite new "<scene>" --json`, write a plan with `"demo": true`,
`"target_duration_s": 900`, 6 clips, and `"visual": {"tier": "still", ...}`. Without Higgsfield,
ask the user for any image on their computer and use `"tier": "byo", "byo_path": "<path>"`.
Then follow the main flow from step 4.

## Main flow (`<idea>`, or after `next`)

1. **Preflight**: `rlite doctor --quick --json`. If not ok, fix first (see Setup).
2. **Create**: `rlite new "<idea>" --json` (or `rlite next --json` for the backlog). Note the `path`.
3. **Design**: read the knowledge files, then write the whole `plan.json` at that path
   (Write tool). Pick `mode` and `use`, then:
   - ambient for natural sound (rain, fire, waves, forest, café, noise); functional for slow
     single-texture music; playlist for many distinct tracks with chapters;
   - default `engine` is `elevenlabs`; use `suno` only if `rlite providers --json` shows it enabled;
   - default `visual.tier` comes from `channel.yaml` (`default_visual_tier`).
4. **Validate**: `rlite validate <job> --json`. Fix every error in `plan.json` and re-run
   (at most 3 rounds; then ask the user). Keep warnings for the checkpoint.
5. **Estimate**: `rlite estimate <job> --json`.
6. **Still**: `rlite still <job> --json`, then look at `visual/still.png` with the Read tool.
   Check: composition, the elements to animate are visible, nothing strange (extra limbs, text,
   artifacts). If it is bad, `rlite still <job> --reroll` (about 2 credits; at most twice, then ask).
7. **Checkpoint** (one message, then wait for the user):
   - the concept in 2-3 lines;
   - the clips, sections or track list, summarized;
   - the title as it will look;
   - the still image path (they can open it);
   - the cost in USD per provider and the total, plus the estimated time;
   - any validation warnings and any risk (for example Suno and monetization).
   Ask: "Approve, or what should change?" Edits go back to step 3.
8. **Approve**: only after an explicit yes, `rlite approve <job> --json`.
9. **Produce**: `rlite run <job> --detach --json`. Tell the user it runs in the background, that
   they can close Claude Code, and to keep the computer plugged in with the lid open.
10. **Wait**: call `rlite wait <job> --timeout 540 --json` repeatedly. Exit 11 means still running:
    report the current step briefly and call it again. Exit 0 means done.
11. **Review**: `rlite qc <job> --json` was run by the pipeline; read `state` via
    `rlite status <job> --json` if needed and look at the QC frames with Read. Check the loop is
    invisible, no black borders, nothing warped. Explain any failed or warned check.
12. **Deliver**: point the user to `final/video.mp4`, `final/thumbnail.png` and `final/UPLOAD.md`
    (paste sheet for YouTube Studio). Remind them to tick "Altered or synthetic content" when the
    sheet says so, and that monetization takes months. Report the real cost
    (`rlite budget show <job> --json`). Offer `rlite clean <job> --keep-final` to free disk space.

## Resume (`resume <job>`)

`rlite status <job> --json`. If the run is `dead` or `failed`, fix the cause (see exit codes) and
run `rlite run <job> --detach --json` again: finished items are reused and in-flight provider
jobs are polled, never paid twice. If the stage is `draft` or `validated`, continue the main flow
from the matching step.

## Direction edits

- Playlist "remove tracks 2 and 6": add their ids to `assembly.exclude`, validate, show the new
  duration, get approval, then `rlite run <job> --from produce --detach` (only assembly runs; no
  credits are spent).
- Changing a prompt of something already generated makes it stale (exit 13). Show the user the
  cost of regenerating it; only with their consent re-run with `--regen-stale`.

## Exit codes

| Code | Meaning | What you do |
|---|---|---|
| 0 | OK | Continue |
| 10 | Plan validation failed | Fix `plan.json` using the JSON paths in the errors |
| 11 | Still running (`wait`) | Wait again |
| 12 | Needs approval (plan or still changed) | Show the checkpoint again |
| 13 | Stale items | Show regeneration cost; `--regen-stale` only with consent |
| 20 | Missing config or credential | Follow the hint; keys and logins are the user's (rule 2) |
| 21 | Over budget | Tell the user; only they can raise it in their terminal |
| 22 | Provider credits exhausted | The user tops up the provider; then resume |
| 30 | Provider error | Retry once later; if it persists, show the message |
| 31 | ffmpeg error | `rlite doctor`; show the message |
| 32 | Not enough disk | Free space or change `RL_HOME` |
| 33 | Corrupt state | `rlite repair <job>`; then resume |
| 40 | Done with warnings | Explain the warnings |
| 41 | QC failed | Explain which check failed and which step to redo |
| 64 | Wrong command usage | Fix the command (not the plan) |
| 75 | Another process is running that step | Wait (`rlite wait`) |
