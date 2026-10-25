# Playlist composition

> Rules by Mariano "Nano" Pfeiffer, developed for the Resonance channel. MIT License.

## No climax: constant intensity
These playlists are background for people who are concentrating. An energy peak in the middle
startles them. So:

- **Constant intensity** from start to end. Allowed variation: minimal (±1 out of 10), as
  micro-waves of **texture and timbre**, never of energy or tempo.
- **Narrow tempo band**: at most 8 BPM wide for the whole playlist (e.g. 66-74), and at most
  4 BPM between consecutive tracks. rlite enforces both (`audio.bpm_band`).
- Split into 3-6 **acts** (`assembly.acts`) as chapters of **timbre and scene**: rotate the lead
  instruments and the scenery, not the energy.
- No escalation adjectives: avoid "driving, powerful, dense, peak, exhilarated, triumphant,
  rising, building". Use "steady, gentle, even, calm, consistent".
- **Style lock**: one genre lane for the whole playlist. Never drift into EDM / house / dance /
  four-on-the-floor unless the whole concept is dance music (rlite blocks those words).

## How many tracks
At least `ceil(target_duration_s / 200)` active tracks (about 3:20 per track after crossfades).
A 2-hour playlist needs about 36-40 tracks. Give each track `duration_s` (180-300) with the
ElevenLabs engine.

## Style prompt template
English, 5-7 descriptors, genre first, one **different solo instrument** per track, and always
the tempo as `NN BPM` (rlite requires it):

`[genre + era], [mood], [NN BPM], [key], [instrument] solo, [rhythm], [bass], instrumental, [vinyl/tape texture], [mood image]`

Example: `warm lofi jazz hip hop, 70 BPM, mellow, relaxed, rhodes solo, soft brushed drums, round bass, vinyl crackle, instrumental`

## Genre cheatsheet
- **Lofi / jazz-hop**: 60-90 BPM · Rhodes, upright bass, brushed drums · maj7/min7/9 chords · vinyl crackle.
- **Trip-hop**: 80-95 BPM · deep bass, downtempo drums, moody keys, muted trumpet or sax · tape saturation.
- **Synthwave (calm)**: 80-100 BPM · analog pads, soft arpeggios, sax or guitar solo · chorus, VHS texture.
- **Ambient / sleep**: no pulse or very slow · evolving pads, drones, long reverb · no transients.
- **Bossa / samba jazz**: 90-120 BPM · nylon guitar, Rhodes, brushes, flute, vibraphone · warm, sunny.

## Suno (optional engine)
Only if the user enabled it. Instrumentals never put the style in the lyrics field (rlite handles
it). Remind the user that Suno via Apiframe is high-risk for monetized channels.
