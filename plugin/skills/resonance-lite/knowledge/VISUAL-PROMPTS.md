# Visual prompts (Higgsfield)

> Technique by Mariano "Nano" Pfeiffer, developed for the Resonance channel. MIT License.

A cinemagraph is a photo that breathes: 90% of the frame is frozen and only 1-3 elements move.
rlite chains several 5-second clips, adds a closing clip that returns to the first frame, and
stabilizes everything, so the loop is invisible for hours. **No camera movement, ever.**

## Loop-safe motion (use these)
| Element | Why it is safe |
|---|---|
| Smoke / steam (coffee, tea, incense, chimney) | Always rises and dissipates; never goes back down |
| Pond or lake water (ripples, reflections) | Ripples with no destination; any frame is valid |
| Leaves / foliage in a breeze | Gentle sway with no marked origin |
| Rain / drops on a window | Always falls downward |
| Light / flicker (candles, filtered sun, fireflies) | Continuous flicker with no memorable pattern |
| Dust / floating particles | Slow random drift |
| Slow background clouds | Very slow one-way movement |

## Dangerous motion (avoid; rlite blocks the worst)
| Element | Problem | Alternative |
|---|---|---|
| Breaking ocean waves | The wave advances and retreats: visible reverse | Calm water ripples, no breakers |
| Pendulum / swing | Goes and comes back | Leaves or light |
| People walking | Reverse + uncanny valley | Empty scene |
| Big intense flames | Can jump at the seam | Soft embers + smoke |

## Image prompt (still)
```
[Scene + atmosphere], [time of day + light], [foreground object that will move, already showing
that element at rest, e.g. "faint steam rising from the cup"], [background with the other
movable elements], [lens + depth of field], cinematic, photorealistic, ultra detailed, [mood],
16:9, static composition, everything motionless except [the elements to animate]
```
No people or animals in the foreground. Make the moving elements explicit in the still.

## Motion prompt (clips)
```
Living cinemagraph. Only [N] elements move, everything else is perfectly frozen.
1) [element 1: continuous motion verb, "never reversing, never looping back"].
2) [subtle element 2].
Static locked tripod camera, absolutely no camera movement: no zoom, no pan, no push-in,
no parallax, no drift. [The static objects] stay absolutely still.
Calm, slow, organic forward-flowing motion with no cuts.
```
rlite requires "static", "locked" or "tripod" in the motion prompt.

## Tiers
- `cinemagraph`: animated loop (default 6 clips + 1 closing clip, ~54 Higgsfield credits).
- `still`: a single image, no motion (~2 credits). Cheap and honest; good for music.
- `byo`: the user's own image or clip (`byo_path`), zero credits.
