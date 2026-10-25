# Resonance Lite

**Make long-form functional sound videos for YouTube — rain, fireplace, sleep piano, lofi playlists — from a single prompt in Claude Code.**

The toolkit behind the [Resonance](#credits) channel, packaged so you can run it on **your** channel, with **your** accounts, on **your** computer.

```
/resonance-lite rain on a tent, 2 hours
```
…and about an hour later you get a folder with the finished video, a thumbnail, and a copy-paste sheet with title, description, chapters and tags for YouTube Studio.

> 🧪 **Private beta.** You are one of the first testers. Please report everything that confuses you, even if it seems small (see [Beta feedback](#beta-feedback)).

---

## What it does

| | |
|---|---|
| 🎧 **Three audio modes** | `ambient` (rain, fire, waves, forest…), `functional` (slow single-texture music: sleep piano, pads, binaural), `playlist` (many distinct tracks with chapters) |
| 🎞️ **Seamless visuals** | A living still (cinemagraph) that loops invisibly for hours, a static frame, or your own image/clip |
| 💸 **Cost before you spend** | Every video shows its cost in USD before anything is generated. Per-video and monthly caps. |
| 🔁 **Resumable** | Close the laptop lid, lose Wi-Fi, run out of credits — resume later without paying twice for what was already generated |
| ✅ **Quality checks** | No silences, no sudden loud sounds, no visible loop seam, checked automatically before delivery |
| 🧑‍🎨 **You stay in charge** | One approval per video (concept, still, cost). Nothing is generated in bulk or published automatically. |

Claude is the creative director (concept, composition, prompts, SEO). A small CLI, `rlite`, does the work that costs money: it calls the providers, assembles with ffmpeg and tracks state and budget.

---

## Requirements

- **Claude Code**
- **macOS** or **Linux** (Windows via WSL2: experimental)
- An **[ElevenLabs](https://elevenlabs.io)** account. A paid plan is needed for commercial use; the free plan requires attribution and does not allow monetization.
- *Optional:* **[Higgsfield](https://higgsfield.ai)** for animated visuals. Without it, you get static backgrounds.
- *Optional:* **Suno via [Apiframe](https://apiframe.ai)** for playlists. Off by default; read [Risks](#risks-read-this) first.
- ~10 GB of free disk space while producing a 2-hour video.

The setup installs everything else (`uv`, `ffmpeg`).

---

## Install (beta)

You need access to the private repo and git credentials on your machine (`gh auth login`).

**1. In Claude Code, add the plugin**
```
/plugin marketplace add <owner>/resonance-lite
/plugin install resonance-lite@resonance-lite
```

**2. Run the guided setup**
```
/resonance-lite setup
```
Claude checks your machine and tells you exactly what to run for anything missing. Two things happen **outside** the chat:
- **Your API key.** Each user brings their own. Open a separate terminal and run `rlite key set elevenlabs` (hidden prompt), or copy the key and run `rlite key set elevenlabs --from-clipboard`. Keys are stored in your OS keychain. **Never paste keys into the Claude chat**: Claude is instructed not to accept them, and `rlite` refuses to read keys when it is not running in your own terminal.
- **Higgsfield login** (optional): `higgsfield auth login`.

**3. Make a test video** (~10 min, under USD 1)
```
/resonance-lite demo
```

> If `/resonance-lite` collides with another command, use the full name: `/resonance-lite:resonance-lite`.

---

## Usage

```
/resonance-lite fireplace for sleeping, 90 minutes
/resonance-lite lofi study playlist, 2 hours
/resonance-lite resume <job-id>        # continue an interrupted job
/resonance-lite next                   # take the next idea from your backlog
```

**What a run looks like**
1. Claude designs the video and validates it against the composition rules.
2. You see **one checkpoint**: concept, track list, title, the still image and the cost. Approve or ask for changes.
3. Audio and visuals are produced in the background. You can close Claude Code; ask "how is my video going?" anytime.
4. Automatic quality check.
5. You get `~/ResonanceLite/jobs/<id>/final/`:
   - `video.mp4`
   - `thumbnail.png`
   - `UPLOAD.md`: title, description with chapters, tags, and the YouTube Studio checklist (including the *altered or synthetic content* disclosure)

**Upload it yourself in YouTube Studio** (5 minutes, everything is ready to paste). Automatic upload is planned for a later version; see [docs/upload-in-studio.md](docs/upload-in-studio.md) for why.

**Direction edits are free.** "Remove tracks 2 and 6" re-assembles the playlist without regenerating anything.

---

## What it costs

You pay the providers directly. Approximate, October 2026:

| Per video | With animated visual | With static visual |
|---|---|---|
| Ambient, 90 min | ~USD 4–6 | ~USD 1–2 |
| Functional music, 90 min | ~USD 10–11 | ~USD 7 |
| Playlist, 2 h (ElevenLabs) | ~USD 23–24 | ~USD 20 |
| Playlist, 2 h (Suno, optional) | ~USD 8 | ~USD 5 |

Monthly subscriptions are the real floor, because several providers' credits expire:
- 4 ambient videos/month: ~USD 40–45.
- 4 music videos/month: ~USD 115–120 (needs ElevenLabs Pro).

Run `rlite estimate --monthly 4 --mode ambient` for your own numbers. Details in [docs/costs.md](docs/costs.md).

---

## Risks (read this)

- **YouTube's "inauthentic content" policy.** Since July 2026, YouTube explicitly demonetizes and removes mass-produced, low-variation AI content. This tool keeps a human in the loop on purpose and varies visuals and thumbnails, but **nothing guarantees monetization**. See [docs/youtube-policy.md](docs/youtube-policy.md).
- **Disclose synthetic content.** Photorealistic AI visuals need the "altered or synthetic" box ticked in Studio. `UPLOAD.md` reminds you.
- **Music rights.**
  - ElevenLabs paid plans include commercial use.
  - **Suno via Apiframe is high-risk for monetized channels.** Suno has no official API, Suno grants usage rights rather than ownership, and the generating account isn't yours. That's why it ships disabled.
- **Monetization takes time.** YouTube Partner Program needs 1,000 subscribers and 4,000 watch hours. Expect months of cost first.
- This is not legal advice. The software is provided "as is" (MIT).

---

## Privacy

No telemetry. `rlite` only talks to the providers you configure. The one exception is an optional once-a-day version check, which sends no data and can be disabled with `RL_NO_UPDATE_CHECK=1`. API keys live in your OS keychain.

---

## Beta feedback

After each video, open an issue with the **Beta feedback** template:
- total time;
- where you got stuck;
- estimated vs real cost (check your provider dashboards);
- quality (1–5);
- what you'd change.

For anything blocking, message Nano directly.

Useful when reporting a bug: `rlite doctor --report`. It never includes keys or personal paths.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Higgsfield session expired` | `higgsfield auth login` |
| `quota exceeded` / out of credits | Top up the provider, then `/resonance-lite resume <job>` |
| `rlite: command not found` | `uv tool update-shell`, then restart Claude Code |
| Job stopped when the Mac slept | Keep the lid open and plugged in; `/resonance-lite resume <job>` |
| Anything else | `rlite doctor`, then [docs/troubleshooting.md](docs/troubleshooting.md) |

---

## Credits

Built by **Mariano "Nano" Pfeiffer**. The composition and audience rules in `plugin/skills/resonance-lite/knowledge/` were developed for the **Resonance** channel. Channels made with this tool are independent and not affiliated with Resonance.

## License

[MIT](LICENSE) © Mariano Pfeiffer
