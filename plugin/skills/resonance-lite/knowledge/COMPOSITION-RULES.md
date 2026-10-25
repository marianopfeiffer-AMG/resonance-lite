# Composition rules

> Rules by Mariano "Nano" Pfeiffer, developed for the Resonance channel. MIT License.
> These are validated in production. Apply them to every plan.

## Golden rules (non-negotiable)

1. **No silence between elements.** Everything is blended. (rlite trims the silence ElevenLabs
   adds at the start and end of each clip before chaining.)
2. **Dynamics follow the use** (see the table below). Never a flat drone, never a climax.
3. **No booms.** Never prompt for bursts, explosions, bangs or sudden sounds. rlite blocks them
   and compresses and limits every master anyway.
4. **Invisible loop.** Nothing may reveal that the audio or the video starts over.

## Dynamics by use

| `use` | Dynamics | How to write prompts |
|---|---|---|
| `sleep`, `baby` | **Bounded wave**: a gentle swell that rises and recedes, like slow breathing, never peaking | "gently swelling and receding", "soft swells", "breathing dynamics". Never "peak" or "climax". |
| `focus`, `relax` | **Constant intensity**. Variety comes from timbre and texture, never from energy | "steady", "even", "consistent", "calm". Rotate instruments, not energy. |
| playlist (any use) | Constant intensity + style lock + narrow tempo band | See PLAYLIST-COMPOSITION.md |

## Ambient (`mode: ambient`, ElevenLabs sound effects)

- Write **6-12 clips** of the SAME element with soft variations. Each clip is ~22 seconds;
  rlite builds three layers of different lengths from them, so the result never repeats audibly.
- Prompt template: `gentle [element] close up, soft continuous, soothing, immersive ASMR, no sudden sounds`.
  Vary with: soft / cozy / steady / calm / deep continuous / gentle hissing / distant / close.
- Avoid: burst, explosion, sudden, intense, loud, collapse, flare, crash (unless negated: "no crashes").
- **Thunderstorms and other discrete events**: keep `clips` continuous (rain only) and put the
  thunder in `audio.events`, e.g.
  `{"id": "e1", "prompt": "distant soft rolling thunder, far away, muffled", "every_s": [90, 240], "gain_db": -14}`.
  `gain_db` must be -12 or lower. rlite places events at random intervals with their own limiter.

## Functional (`mode: functional`, ElevenLabs Music by default)

- Write sections of up to 600 s (300 s is the safer default: a long call that times out is lost).
- `bed_min_s` must be at least half of `target_duration_s`; rlite loops the bed seamlessly to the
  full length. Longer beds repeat less but cost more (~900 ElevenLabs credits per minute):
  show the user this trade-off at the checkpoint.
- Prompt template: `very slow solo felt piano, 55 BPM, A minor, warm soft pads, gently swelling and receding, no percussion, instrumental`.
  Always English, always tempo + key, always "instrumental".
- Change key and color between sections so the loop never sounds like the same piece twice in a row.
