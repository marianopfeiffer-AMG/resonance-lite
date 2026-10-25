# Plan example (ambient, 2 hours, cinemagraph)

A complete, valid `plan.json`. Use it as the shape reference; write your own content.

```json
{
  "schema_version": 1,
  "idea": "rain on a tent, 2 hours",
  "mode": "ambient",
  "engine": "elevenlabs",
  "use": "sleep",
  "target_duration_s": 7200,
  "demo": false,
  "concept": "Soft steady rain on a canvas tent in a pine forest at night. Close, enveloping, no surprises.",
  "audio": {
    "clips": [
      {"id": "c1", "prompt": "gentle steady rain on a canvas tent, close up, soft continuous, soothing, no sudden sounds"},
      {"id": "c2", "prompt": "soft rain pattering on tent fabric, calm, even, immersive ASMR"},
      {"id": "c3", "prompt": "light rain on canvas with distant soft rain on pine needles, cozy, continuous"},
      {"id": "c4", "prompt": "steady medium rain on a tent roof, warm, enveloping, no thunder"},
      {"id": "c5", "prompt": "gentle rain drips from tent edge onto soft ground, calm, continuous"},
      {"id": "c6", "prompt": "deep continuous rain ambience inside a tent, soft, soothing"}
    ]
  },
  "assembly": {"exclude": [], "crossfade_s": 3, "lufs": -18},
  "visual": {
    "tier": "cinemagraph",
    "image_prompt": "inside view of a small camping tent at night, rain streaks on the translucent fabric, warm lantern glow, pine forest silhouettes outside, cinematic, photorealistic, wide 16:9, everything motionless except the rain streaks",
    "motion_prompt": "Living cinemagraph. Only the rain streaks on the tent fabric move, gently and continuously, never reversing. The lantern glow flickers very slightly. Static locked tripod camera, absolutely no camera movement.",
    "n_clips": 6,
    "mode": "pro"
  },
  "metadata": {
    "title": "Rain on a Tent ⛺ {duration} | Sleep, ASMR, Camping Ambience",
    "description": "Soft rain on a canvas tent for deep sleep, studying or relaxing. Continuous, seamless, no harsh sounds.",
    "tags": ["rain sounds", "rain on tent", "sleep sounds", "camping ambience", "asmr", "white noise"],
    "category_id": "10",
    "made_for_kids": false,
    "default_language": "en",
    "synthetic_media": true
  }
}
```

Other modes:
- `functional`: `audio.sections` = `[{"id", "prompt", "duration_s"}]` + `audio.bed_min_s`.
- `playlist`: `audio.tracks` = `[{"id", "title", "style", "instrumental": true, "duration_s"}]` +
  `audio.bpm_band` `[min, max]`; optional `assembly.acts` `{"t01": "I · Dusk", ...}`; `assembly.crossfade_s` 8-12; `assembly.lufs` -14.
- `demo: true`: `target_duration_s` 600-900 and `visual.tier` `still` or `byo`.
- Allowed `use`: sleep, baby, focus, relax. Allowed `engine`: elevenlabs, suno (only if enabled).
- Ids: lowercase letters, digits, `-` or `_`, up to 32 characters.
