# Troubleshooting

Start with `rlite doctor`: every problem comes with the exact fix. For bug reports, paste
`rlite doctor --report` (it contains no keys and no personal paths).

| Symptom | Fix |
|---|---|
| `No elevenlabs API key configured` | In a separate terminal: `rlite key set elevenlabs` |
| `ElevenLabs rejected the API key` | Create a new key in ElevenLabs, then `rlite key set elevenlabs` |
| `Your Higgsfield session expired` | In your terminal: `higgsfield auth login`, then resume |
| `credits are exhausted` (exit 22) | Top up the provider, then `/resonance-lite resume <job>` |
| Over budget (exit 21) | Ask yourself if it is worth it; raise it in your terminal: `rlite budget allow <job> --usd 5` |
| `rlite: command not found` | `uv tool update-shell`, then restart Claude Code |
| Run reported `dead` | The computer slept or the process died. Keep it plugged in and the lid open; `rlite run <job> --detach` resumes without paying twice |
| `Corrupt state` (exit 33) | `rlite repair <job>`, then resume. If it quarantined jobs in progress, check provider dashboards first |
| Loop seam visible / QC fails | Install OpenCV: `uv tool install --force "resonance-lite[stabilize] ..."` and re-run `rlite run <job> --from produce --detach` |
| Jobs folder in iCloud/Drive/Dropbox | Set `RL_HOME` to a local folder |
| WSL: keys cannot be saved | No keychain on WSL: `rlite key set elevenlabs --allow-file-storage` (0600 file). WSL is experimental |
