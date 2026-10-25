"""The audio step: generate missing items, then assemble (SPEC §4.3, §4.1, §7.0).

Rules enforced here:
- Only items whose input hash changed or that never finished are generated.
- A changed item that was already paid for is "stale": regenerating it needs --regen-stale.
- Every paid call reserves its cost first (rl.budget).
- Resumable providers: the provider job id is stored BEFORE waiting; a resume polls it.
- Non-resumable providers (ElevenLabs): a timeout is counted as spent and never auto-retried.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rl.audio.ambient import build_ambient
from rl.audio.common import measure
from rl.audio.events import EventSpec, build_event_track
from rl.audio.functional import build_functional
from rl.audio.playlist import TrackAudio, build_playlist
from rl.budget import Budget
from rl.config import plans
from rl.exitcodes import ConfigError, ProviderError, RlError, StaleItems
from rl.hashing import assemble_hash, audio_item_hash, plan_hash
from rl.locks import step_lock
from rl.plan import Plan
from rl.pricing import pricing, usd_per_credit
from rl.providers.apiframe import Apiframe
from rl.providers.base import download
from rl.providers.elevenlabs import ElevenLabs
from rl.stage import require_approval
from rl.state import State, StateStore, now_iso

SUNO_POOL = 5
DEFAULT_TRACK_S = 240


@dataclass
class AudioProviders:
    elevenlabs: Any = None
    apiframe: Any = None
    downloader: Callable[[str, Path], Path] = download
    sleep: Callable[[float], None] = time.sleep
    poll_interval_s: float = 10.0
    poll_timeout_s: float = 900.0


@dataclass
class Item:
    id: str
    kind: str  # sfx | event | music | suno
    prompt: str
    seconds: float
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def hash(self) -> str:
        return audio_item_hash(
            {"kind": self.kind, **self.raw, "seconds": self.seconds}, self.kind, None
        )


def plan_items(plan: Plan) -> list[Item]:
    audio, mode, engine = plan["audio"], plan["mode"], plan["engine"]
    sfx_s = float(pricing()["elevenlabs"]["sfx_clip_seconds"])
    if mode == "ambient":
        items = [Item(c["id"], "sfx", c["prompt"], sfx_s, c) for c in audio["clips"]]
        items += [Item(e["id"], "event", e["prompt"], sfx_s, e) for e in audio.get("events", [])]
        return items
    if mode == "functional":
        kind = "suno" if engine == "suno" else "music"
        return [
            Item(s["id"], kind, s["prompt"], float(s["duration_s"]), s) for s in audio["sections"]
        ]
    kind = "suno" if engine == "suno" else "music"
    extra = {"model_version": audio.get("model_version", "V4_5PLUS")} if engine == "suno" else {}
    return [
        Item(t["id"], kind, t["style"], float(t.get("duration_s", DEFAULT_TRACK_S)), {**t, **extra})
        for t in audio["tracks"]
    ]


def _usd(item: Item) -> tuple[str, float]:
    p, user_plans = pricing(), plans()
    if item.kind == "suno":
        credits = p["apiframe"]["suno_credits_per_generation"]
        return "apiframe", credits * usd_per_credit("apiframe", user_plans.get("apiframe"))
    el = p["elevenlabs"]
    if item.kind in ("sfx", "event"):
        credits = item.seconds * el["sfx_credits_per_second"]
    else:
        credits = item.seconds / 60 * el["music_credits_per_minute"]
    return "elevenlabs", credits * usd_per_credit("elevenlabs", user_plans.get("elevenlabs"))


class AudioStep:
    def __init__(self, job_dir: Path, plan: Plan, providers: AudioProviders | None = None) -> None:
        self.job = job_dir
        self.plan = plan
        self.p = providers or AudioProviders()
        self.store = StateStore(job_dir)
        self.budget = Budget(job_dir)
        self.dir = job_dir / "audio"
        self.items_dir = self.dir / "items"

    # ---- state helpers -------------------------------------------------------------------
    def _item_state(self, item_id: str) -> State:
        items: dict[str, State] = self.store.read("audio").get("items", {})
        return items.get(item_id, {})

    def _set_item(self, item_id: str, **fields: Any) -> None:
        def _apply(state: State) -> None:
            state.setdefault("items", {}).setdefault(item_id, {}).update(fields)

        self.store.update("audio", _apply)

    def _set(self, **fields: Any) -> None:
        self.store.update("audio", lambda s: s.update(fields))

    # ---- public --------------------------------------------------------------------------
    def run(self, *, assemble_only: bool = False, regen_stale: bool = False) -> State:
        require_approval(self.job, self.plan)
        with step_lock(self.job, "audio"):
            self.items_dir.mkdir(parents=True, exist_ok=True)
            items = plan_items(self.plan)
            self._set(status="running", started=now_iso(), error=None)
            try:
                if assemble_only:
                    missing = [i.id for i in items if not self._is_done(i)]
                    if missing:
                        raise ConfigError(f"Cannot assemble: items not generated yet: {missing}")
                else:
                    self._check_stale(items, regen_stale)
                    self._generate(items)
                result = self._assemble(items)
            except RlError as err:
                self._set(status="failed", error={"code": int(err.code), "message": str(err)})
                raise
            self._set(status="done", finished=now_iso(), **result)
            return self.store.read("audio")

    # ---- generation ----------------------------------------------------------------------
    def _outputs(self, item_id: str) -> list[Path]:
        return [Path(p) for p in self._item_state(item_id).get("outputs", [])]

    def _is_done(self, item: Item) -> bool:
        st = self._item_state(item.id)
        return (
            st.get("status") == "done"
            and st.get("hash") == item.hash
            and all(p.exists() for p in self._outputs(item.id))
            and bool(st.get("outputs"))
        )

    def _check_stale(self, items: list[Item], regen_stale: bool) -> None:
        stale = [
            i.id
            for i in items
            if self._item_state(i.id).get("status") == "done"
            and self._item_state(i.id).get("hash") != i.hash
        ]
        if stale and not regen_stale:
            raise StaleItems(
                f"These items changed after being generated (and paid for): {stale}",
                hint="Show the user the cost of regenerating them; "
                "if they agree, re-run with --regen-stale.",
            )

    def _generate(self, items: list[Item]) -> None:
        pending = [i for i in items if not self._is_done(i)]
        sync = [i for i in pending if i.kind != "suno"]
        for item in sync:
            self._generate_sync(item)
        suno = [i for i in pending if i.kind == "suno"]
        if suno:
            self._generate_suno(suno)

    def _generate_sync(self, item: Item) -> None:
        provider, usd = _usd(item)
        reservation = self.budget.reserve(provider, usd, f"{item.kind} {item.id}")
        out = self.items_dir / f"{item.id}.mp3"
        eleven = self.p.elevenlabs or ElevenLabs()
        self._set_item(item.id, hash=item.hash, status="running", provider=provider)
        try:
            if item.kind in ("sfx", "event"):
                eleven.generate_sfx(item.prompt, item.seconds, out, loop=item.kind == "sfx")
            else:
                eleven.generate_music(item.prompt, int(item.seconds), out)
        except ProviderError as err:
            if err.retryable:
                self.budget.release(reservation)  # rejected before running: not charged
            else:
                self.budget.commit(reservation)  # may have been charged (timeout)
            self._set_item(item.id, status="failed", error=str(err))
            raise
        except RlError as err:
            self.budget.release(reservation)
            self._set_item(item.id, status="failed", error=str(err))
            raise
        self.budget.commit(reservation)
        self._set_item(item.id, status="done", outputs=[str(out)], error=None, at=now_iso())

    def _generate_suno(self, items: list[Item]) -> None:
        api = self.p.apiframe or Apiframe()
        queue = list(items)
        in_flight: dict[str, tuple[Item, str, float]] = {}
        # Resume first: anything already submitted is polled, never re-submitted.
        for item in list(queue):
            st = self._item_state(item.id)
            if (
                st.get("provider_job_id")
                and st.get("hash") == item.hash
                and st.get("status") == "submitted"
            ):
                in_flight[item.id] = (item, st["reservation"], time.monotonic())
                queue.remove(item)
        while queue or in_flight:
            while queue and len(in_flight) < SUNO_POOL:
                item = queue.pop(0)
                provider, usd = _usd(item)
                reservation = self.budget.reserve(provider, usd, f"suno {item.id}")
                try:
                    job_id = api.submit(item.raw, item.raw.get("model_version", "V4_5PLUS"))
                except ProviderError as err:
                    if err.retryable:
                        self.budget.release(reservation)
                    else:
                        self.budget.commit(reservation)
                    self._set_item(item.id, hash=item.hash, status="failed", error=str(err))
                    raise
                self._set_item(
                    item.id,
                    hash=item.hash,
                    status="submitted",
                    provider_job_id=job_id,
                    reservation=reservation,
                    provider="apiframe",
                )
                in_flight[item.id] = (item, reservation, time.monotonic())
            for item_id, (_item, reservation, started) in list(in_flight.items()):
                job_id = self._item_state(item_id)["provider_job_id"]
                result = api.poll(job_id)
                if result.status == "running":
                    if time.monotonic() - started > self.p.poll_timeout_s:
                        # Do not mark failed: the job may still finish. A resume polls it again.
                        raise ProviderError(
                            f"Suno track {item_id} is taking too long; resume later to collect it.",
                            retryable=True,
                        )
                    continue
                del in_flight[item_id]
                if result.status == "failed":
                    self.budget.release(reservation)  # Apiframe bills successful generations only
                    self._set_item(item_id, status="failed", error=result.error)
                    raise ProviderError(f"Suno failed on track {item_id}: {result.error}")
                outputs = []
                for k, url in enumerate(result.urls[:2]):
                    outputs.append(
                        str(self.p.downloader(url, self.items_dir / f"{item_id}-v{k + 1}.mp3"))
                    )
                self.budget.commit(reservation)
                self._set_item(item_id, status="done", outputs=outputs, error=None, at=now_iso())
            if in_flight:
                self.p.sleep(self.p.poll_interval_s)

    # ---- assembly ------------------------------------------------------------------------
    def _assemble(self, items: list[Item]) -> dict[str, Any]:
        assembly = self.plan["assembly"]
        a_hash = assemble_hash(
            [i.hash for i in items],
            {**assembly, "mode": self.plan["mode"], "duration": self.plan["target_duration_s"]},
        )
        current = self.store.read("audio").get("assemble", {})
        out = self.dir / "audio.m4a"
        if current.get("hash") == a_hash and out.exists():
            return {"assemble": current}

        work = self.dir / "work"
        seed = int(plan_hash(self.plan)[:8], 16)
        seconds = float(self.plan["target_duration_s"])
        info: dict[str, Any] = {"hash": a_hash, "output": str(out)}
        mode = self.plan["mode"]
        if mode == "ambient":
            clips = [self._outputs(i.id)[0] for i in items if i.kind == "sfx"]
            events = [i for i in items if i.kind == "event"]
            event_track = None
            if events:
                specs = [i.raw for i in events]
                spec = EventSpec(
                    clips=[self._outputs(i.id)[0] for i in events],
                    every_s=(
                        min(s["every_s"][0] for s in specs),
                        max(s["every_s"][1] for s in specs),
                    ),
                    gain_db=min(s["gain_db"] for s in specs),
                )
                event_track = build_event_track(spec, seconds, work / "events.wav", work, seed)
            build_ambient(clips, seconds, out, work, seed=seed, events=event_track)
        elif mode == "functional":
            build_functional([self._outputs(i.id)[0] for i in items], seconds, out, work)
        else:
            tracks = [TrackAudio(i.id, i.raw["title"], self._outputs(i.id)) for i in items]
            result = build_playlist(
                tracks,
                out,
                work,
                exclude=set(assembly.get("exclude", [])),
                crossfade_s=float(assembly.get("crossfade_s", 8)),
                lufs=float(assembly.get("lufs", -14)),
                acts=assembly.get("acts", {}),
            )
            info.update(
                timestamps=str(result.timestamps),
                chosen_takes=result.chosen_takes,
                max_jump_db=round(result.max_jump_db, 1),
                warnings=result.warnings,
            )
        report = measure(out)
        info.update(report=report.to_dict(), duration_s=round(report.duration_s, 2))
        return {"assemble": info}
