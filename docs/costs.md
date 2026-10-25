# Costs

You pay the providers directly, with your own accounts. Prices change; `rlite estimate <job>` uses
a dated table (`cli/src/rl/pricing.yaml`) and asks Higgsfield for live prices when you are logged in.

## Per video (approximate, October 2026)

| Video | Audio | Animated visual (6+1 clips) | Total |
|---|---|---|---|
| Ambient, 90 min | ~USD 0.5-2 | ~USD 3-4 | ~USD 4-6 |
| Functional music, 90 min (45-min bed) | ~USD 7 | ~USD 3-4 | ~USD 10-11 |
| Playlist, 2 h, ElevenLabs | ~USD 20 | ~USD 3-4 | ~USD 23-24 |
| Playlist, 2 h, Suno (optional) | ~USD 4.4 | ~USD 3-4 | ~USD 8 |
| Any mode with a still background | — | ~USD 0.15 | audio + 0.15 |

## Monthly floor
Several providers' credits expire at the end of the month, so the subscription is the real cost.

| 4 videos per month of… | ElevenLabs plan | Higgsfield | Approx. per month |
|---|---|---|---|
| ambient | Creator | Starter | USD 40-45 |
| functional music | Pro | Starter | USD 115-120 |
| playlists (ElevenLabs) | Pro | Starter | USD 115-120 |
| playlists (Suno) | optional | Starter | USD 75-80 (Apiframe 39 + Higgsfield) |
| any mode with still backgrounds | as above | not needed | subtract USD 15-19 |

The ElevenLabs free plan does not allow commercial use and requires attribution.

## Budget caps
`channel.yaml` → `budget.per_job_usd` and `budget.per_month_usd` (defaults 15 and 120). `rlite`
checks them before every paid call. `rlite budget show <job>` shows the spend.
