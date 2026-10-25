import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
import requests
import responses

from rl.exitcodes import ConfigError, ProviderError, QuotaExhausted
from rl.providers.apiframe import API as APIFRAME
from rl.providers.apiframe import Apiframe
from rl.providers.elevenlabs import API as ELEVEN
from rl.providers.elevenlabs import ElevenLabs
from rl.providers.higgsfield import Higgsfield

AUDIO = b"ID3" + b"\x00" * 4096


@responses.activate
def test_elevenlabs_sfx_writes_audio_atomically(tmp_path: Path) -> None:
    responses.post(f"{ELEVEN}/v1/sound-generation", body=AUDIO)
    out = ElevenLabs(api_key="k").generate_sfx("gentle rain", 22, tmp_path / "c1.mp3")
    assert out.read_bytes() == AUDIO
    sent = json.loads(responses.calls[0].request.body or b"{}")
    assert sent["loop"] is True and sent["duration_seconds"] == 22
    assert not list(tmp_path.glob("*.partial"))


@responses.activate
def test_elevenlabs_music_clamps_length_and_forces_instrumental(tmp_path: Path) -> None:
    responses.post(f"{ELEVEN}/v1/music", body=AUDIO)
    ElevenLabs(api_key="k").generate_music("slow piano", 900, tmp_path / "s1.mp3")
    sent = json.loads(responses.calls[0].request.body or b"{}")
    assert sent["music_length_ms"] == 600_000
    assert sent["force_instrumental"] is True


@responses.activate
def test_elevenlabs_error_mapping(tmp_path: Path) -> None:
    eleven = ElevenLabs(api_key="k")
    responses.post(f"{ELEVEN}/v1/sound-generation", status=401, json={"detail": "bad key"})
    with pytest.raises(ConfigError):
        eleven.generate_sfx("rain", 22, tmp_path / "a.mp3")
    responses.replace(
        responses.POST,
        f"{ELEVEN}/v1/sound-generation",
        status=400,
        json={"detail": "quota_exceeded"},
    )
    with pytest.raises(QuotaExhausted):
        eleven.generate_sfx("rain", 22, tmp_path / "a.mp3")
    responses.replace(responses.POST, f"{ELEVEN}/v1/sound-generation", body=b'{"error":"x"}')
    with pytest.raises(ProviderError):
        eleven.generate_sfx("rain", 22, tmp_path / "a.mp3")


def test_elevenlabs_timeout_is_not_retried(tmp_path: Path) -> None:
    calls = []

    class Session(requests.Session):
        def post(self, *args: object, **kwargs: object) -> requests.Response:  # type: ignore[override]
            calls.append(1)
            raise requests.Timeout()

    with pytest.raises(ProviderError) as exc:
        ElevenLabs(api_key="k", session=Session()).generate_sfx("rain", 22, tmp_path / "a.mp3")
    assert exc.value.retryable is False
    assert len(calls) == 1


@responses.activate
def test_elevenlabs_retries_rate_limits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda s: None)
    responses.post(f"{ELEVEN}/v1/sound-generation", status=429)
    responses.post(f"{ELEVEN}/v1/sound-generation", body=AUDIO)
    ElevenLabs(api_key="k").generate_sfx("rain", 22, tmp_path / "a.mp3")
    assert len(responses.calls) == 2


@responses.activate
def test_apiframe_instrumental_never_sends_style_as_prompt() -> None:
    responses.post(f"{APIFRAME}/v2/music/generate", json={"jobId": "J1", "status": "QUEUED"})
    track = {"id": "t01", "title": "T", "style": "lofi, 70 BPM", "instrumental": True}
    assert Apiframe(api_key="k").submit(track) == "J1"
    request = responses.calls[0].request
    sent = json.loads(request.body or b"{}")
    assert sent["prompt"] == "[Instrumental]"
    assert sent["sunoParams"]["style"] == "lofi, 70 BPM"
    assert "Mozilla" in request.headers["User-Agent"]


@responses.activate
def test_apiframe_poll_states() -> None:
    api = Apiframe(api_key="k")
    responses.get(f"{APIFRAME}/v2/jobs/J1", json={"status": "PROCESSING"})
    assert api.poll("J1").status == "running"
    responses.replace(
        responses.GET,
        f"{APIFRAME}/v2/jobs/J1",
        json={"status": "COMPLETED", "result": {"tracks": [{"audioUrl": "https://x/a.mp3"}]}},
    )
    result = api.poll("J1")
    assert result.status == "done" and result.urls == ["https://x/a.mp3"]


def test_apiframe_submit_timeout_is_not_retryable() -> None:
    class Session(requests.Session):
        def post(self, *args: object, **kwargs: object) -> requests.Response:  # type: ignore[override]
            raise requests.Timeout()

    track = {"id": "t01", "title": "T", "style": "lofi", "instrumental": True}
    with pytest.raises(ProviderError) as exc:
        Apiframe(api_key="k", session=Session()).submit(track)
    assert exc.value.retryable is False


class FakeCli:
    def __init__(self, responses_: dict[str, tuple[int, str]]) -> None:
        self.responses = responses_
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        key = " ".join(args[:2])
        code, out = self.responses.get(key, (0, "{}"))
        return subprocess.CompletedProcess(list(args), code, stdout=out, stderr="")


def test_higgsfield_submit_poll_cost() -> None:
    cli = FakeCli(
        {
            "generate create": (0, json.dumps({"id": "11111111-2222-3333-4444-555555555555"})),
            "generate get": (
                0,
                json.dumps({"status": "completed", "result_url": "https://x/v.mp4"}),
            ),
            "generate cost": (0, json.dumps({"credits": 7.5})),
        }
    )
    hf = Higgsfield(runner=cli)
    job = hf.submit("kling3_0", {"prompt": "rain", "duration": 5, "mode": "pro"})
    assert job == "11111111-2222-3333-4444-555555555555"
    assert cli.calls[0][-1] == "--json"
    assert hf.poll(job).urls == ["https://x/v.mp4"]
    assert hf.cost("kling3_0", {"prompt": "rain"}) == 7.5


def test_higgsfield_account_never_returns_email() -> None:
    cli = FakeCli(
        {
            "account status": (
                0,
                json.dumps({"credits": 100, "email": "x@y.z", "subscription_plan_type": "starter"}),
            )
        }
    )
    assert Higgsfield(runner=cli).account() == {"credits": 100, "plan": "starter"}


def test_higgsfield_expired_session() -> None:
    cli = FakeCli({"generate create": (1, "Error: session expired, please login")})
    with pytest.raises(ConfigError) as exc:
        Higgsfield(runner=cli).submit("nano_banana_2", {"prompt": "x"})
    assert "higgsfield auth login" in (exc.value.hint or "")
