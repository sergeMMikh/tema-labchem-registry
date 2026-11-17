import wave
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError

from inventory.telegram import ReagentBot, TelegramClient
from inventory.voice import MAX_VOICE_BYTES, VoiceError, load_model, transcribe

pytest.importorskip("faster_whisper", reason="Install requirements-voice.txt for voice tests")


def test_setup_voice():
    with (
        patch("faster_whisper.utils.download_model") as download,
        patch("inventory.voice.load_model") as model,
    ):
        call_command("setup_voice")
    download.assert_called_once()
    model.assert_called_once()


def test_setup_failure():
    with (
        patch("faster_whisper.utils.download_model", side_effect=OSError),
        pytest.raises(CommandError),
    ):
        call_command("setup_voice")


def update(**voice):
    return {
        "message": {
            "chat": {"id": 12, "type": "private"},
            "from": {"id": 12},
            "voice": {"file_id": "voice", "duration": 3, **voice},
        }
    }


@pytest.fixture
def bot(settings):
    settings.TELEGRAM_VOICE_ENABLED = True
    settings.TELEGRAM_ALLOWED_USER_IDS = set()
    cache.clear()
    return ReagentBot(MagicMock())


@pytest.mark.parametrize("text", ["Ácido nítrico", "Nitric acid", "Acetona", "Acetone"])
def test_voice_uses_same_search(bot, text):
    with (
        patch("inventory.telegram.transcribe", return_value=text),
        patch.object(bot, "search") as search,
    ):
        bot.handle(update())
    search.assert_called_once_with(12, 12, text)
    assert text in bot.client.call.call_args.kwargs["text"]


@pytest.mark.parametrize(
    "voice", [{"duration": 31}, {"file_size": MAX_VOICE_BYTES + 1}, {"file_id": ""}]
)
def test_limits_before_download(bot, voice):
    bot.handle(update(**voice))
    bot.client.download_voice.assert_not_called()


def test_auth_and_disable_before_download(bot, settings):
    settings.TELEGRAM_ALLOWED_USER_IDS = {99}
    bot.handle(update())
    settings.TELEGRAM_ALLOWED_USER_IDS = set()
    settings.TELEGRAM_VOICE_ENABLED = False
    bot.handle(update())
    bot.client.download_voice.assert_not_called()


def test_failure_does_not_crash_worker(bot):
    with (
        patch("inventory.telegram.transcribe", side_effect=VoiceError),
        patch.object(bot, "search") as search,
    ):
        bot.handle(update())
    search.assert_not_called()
    assert "send text" in bot.client.call.call_args.kwargs["text"]


@pytest.mark.parametrize("language", ["pt", "en", "auto"])
def test_language_command(bot, language):
    msg = update()["message"]
    msg.pop("voice")
    msg["text"] = f"/{language}"
    bot.handle({"message": msg})
    with (
        patch("inventory.telegram.transcribe", return_value="Acetone") as speech,
        patch.object(bot, "search"),
    ):
        bot.handle(update())
    assert speech.call_args.args[1] == (None if language == "auto" else language)
    assert cache.get("tg:language:99:99") is None


def wav(seconds=1):
    buffer = BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * int(seconds * 16000))
    return buffer.getvalue()


@pytest.mark.parametrize("language,text", [("en", "Nitric acid."), ("pt", "Ácido nítrico.")])
def test_decode_and_transcribe(language, text):
    model = MagicMock()
    model.transcribe.return_value = (
        [SimpleNamespace(text=text)],
        SimpleNamespace(language=language),
    )
    with patch("inventory.voice.load_model", return_value=model):
        assert transcribe(wav(), language) == text.rstrip(".")
    assert len(model.transcribe.call_args.args[0]) == 16000


@pytest.mark.parametrize("audio", [b"bad", wav(31), wav(0)], ids=["invalid", "long", "empty"])
def test_bad_or_long_decoded_audio(audio):
    with patch("inventory.voice.load_model") as model, pytest.raises(VoiceError):
        transcribe(audio)
    model.assert_not_called()


@pytest.mark.parametrize("language,text", [("fr", "Acetone"), ("pt", ""), ("en", "x" * 201)])
def test_invalid_recognition(language, text):
    model = MagicMock()
    model.transcribe.return_value = (
        [SimpleNamespace(text=text)],
        SimpleNamespace(language=language),
    )
    with patch("inventory.voice.load_model", return_value=model), pytest.raises(VoiceError):
        transcribe(wav())


def test_model_offline_cpu():
    load_model.cache_clear()
    with patch("faster_whisper.WhisperModel") as model:
        load_model("model-test")
    assert model.call_args.kwargs["local_files_only"] is True
    assert model.call_args.kwargs["device"] == "cpu"
    load_model.cache_clear()


@pytest.mark.parametrize("path", ["../secret", "https://evil.org/a.ogg", "/voice/a.ogg", ""])
def test_invalid_download_path(path):
    client = TelegramClient("secret")
    with patch.object(client, "call", return_value={"file_path": path}), pytest.raises(VoiceError):
        client.download_voice("file")


@pytest.mark.parametrize(
    "data", [b"audio", b"", b"x" * (MAX_VOICE_BYTES + 1)], ids=["valid", "empty", "large"]
)
def test_download_size_bound(data):
    client = TelegramClient("secret")
    response = MagicMock()
    response.__enter__.return_value.read.return_value = data
    with (
        patch.object(client, "call", return_value={"file_path": "voice/file.oga"}),
        patch("urllib.request.urlopen", return_value=response),
    ):
        if data == b"audio":
            assert client.download_voice("id") == data
        else:
            with pytest.raises(VoiceError):
                client.download_voice("id")
    response.__enter__.return_value.read.assert_called_once_with(MAX_VOICE_BYTES + 1)


def test_download_error_redacts_token():
    client = TelegramClient("secret-token")
    with (
        patch.object(client, "call", return_value={"file_path": "voice/file.oga"}),
        patch("urllib.request.urlopen", side_effect=URLError("secret-token")),
        pytest.raises(VoiceError) as error,
    ):
        client.download_voice("id")
    assert "secret-token" not in str(error.value)
