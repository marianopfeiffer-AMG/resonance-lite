from pathlib import Path

import pytest
from audio_utils import noise, tone

from rl import ffmpeg
from rl.audio.ambient import build_ambient, layer_orders
from rl.audio.common import crossfade_concat, measure, ring_close, trim_silence
from rl.audio.events import EventSpec, build_event_track, schedule
from rl.audio.functional import build_functional
from rl.audio.playlist import TrackAudio, build_playlist, format_timestamp
from rl.audio.takes import choose_takes


def test_trim_removes_leading_silence(tmp_path: Path) -> None:
    src = tone(tmp_path / "t.wav", 3, lead_silence=2.0)
    out = trim_silence(src, tmp_path / "trim.wav")
    assert ffmpeg.duration(out) == pytest.approx(3.0, abs=0.3)


def test_crossfade_concat_length(tmp_path: Path) -> None:
    files = [noise(tmp_path / f"n{i}.wav", 6) for i in range(3)]
    out = crossfade_concat(files, tmp_path / "c.wav", 2.0)
    assert ffmpeg.duration(out) == pytest.approx(6 * 3 - 2 * 2, abs=0.2)


def test_ring_close_has_no_silence_and_keeps_length(tmp_path: Path) -> None:
    src = noise(tmp_path / "n.wav", 20)
    ring = ring_close(src, tmp_path / "ring.wav", 3.0)
    assert ffmpeg.duration(ring) == pytest.approx(17.0, abs=0.2)
    looped = tmp_path / "looped.wav"
    ffmpeg.run(["-stream_loop", "2", "-i", str(ring), "-c:a", "pcm_s16le", str(looped)], looped)
    assert measure(looped, min_silence_s=0.3).silences == []


def test_layer_orders_have_coprime_lengths() -> None:
    a, b, c = layer_orders(6, seed=1)
    assert (len(a), len(b), len(c)) == (6, 5, 7)
    assert a != b[: len(a)] and a != c[: len(a)]


def test_ambient_has_exact_duration_and_no_silence(tmp_path: Path) -> None:
    clips = [
        noise(tmp_path / f"c{i}.wav", 12, color=("pink", "brown", "white")[i % 3]) for i in range(6)
    ]
    out = build_ambient(clips, 75, tmp_path / "bed.m4a", tmp_path / "work", seed=3)
    report = measure(out)
    assert report.duration_s == pytest.approx(75, abs=0.3)
    assert report.silences == []
    assert report.true_peak_db is not None and report.true_peak_db < 0.5


def test_event_schedule_never_overlaps_or_overflows() -> None:
    events = schedule(600, (30, 60), [8.0, 5.0], seed=7)
    assert events
    for (t1, i1), (t2, _) in zip(events, events[1:], strict=False):
        assert t2 >= t1 + [8.0, 5.0][i1]
    last_t, last_i = events[-1]
    assert last_t + [8.0, 5.0][last_i] <= 600


def test_event_track_length(tmp_path: Path) -> None:
    spec = EventSpec([tone(tmp_path / "e.wav", 3, freq=80)], (10, 20), -14)
    out = build_event_track(spec, 60, tmp_path / "events.wav", tmp_path / "w", seed=1)
    assert ffmpeg.duration(out) == pytest.approx(60, abs=0.3)


def test_functional_tiles_to_length(tmp_path: Path) -> None:
    sections = [tone(tmp_path / f"s{i}.wav", 15, freq=220 + 110 * i) for i in range(3)]
    out = build_functional(sections, 100, tmp_path / "bed.m4a", tmp_path / "work")
    report = measure(out)
    assert report.duration_s == pytest.approx(100, abs=0.3)
    assert report.silences == []


def test_choose_takes_minimizes_worst_jump() -> None:
    levels = [
        [(-20, -20), (-20, -10)],
        [(-10, -18), (-25, -20)],
        [(-19, -20), (-5, -5)],
    ]
    choice = choose_takes(levels)
    assert choice.takes == [1, 0, 0]
    assert choice.max_jump_db == pytest.approx(1.0)


def test_playlist_chapters_and_exclude(tmp_path: Path) -> None:
    tracks = [
        TrackAudio(f"t{i}", f"Song {i}", [tone(tmp_path / f"t{i}.wav", 20, freq=200 + 50 * i)])
        for i in range(4)
    ]
    result = build_playlist(
        tracks,
        tmp_path / "mix.m4a",
        tmp_path / "work",
        exclude={"t2"},
        crossfade_s=4,
        lufs=-14,
        acts={"t0": "I · Dusk"},
    )
    lines = result.timestamps.read_text().splitlines()
    assert lines[0] == "0:00 I · Dusk — Song 0"
    assert len(lines) == 3 and "Song 2" not in result.timestamps.read_text()
    assert result.duration_s == pytest.approx(3 * 20 - 2 * 4, abs=1.0)


def test_format_timestamp() -> None:
    assert format_timestamp(65) == "1:05"
    assert format_timestamp(3725) == "1:02:05"
