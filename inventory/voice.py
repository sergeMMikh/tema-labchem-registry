"""Offline speech recognition. Model downloads are an explicit setup step only."""

from functools import lru_cache
from io import BytesIO

from django.conf import settings

MAX_VOICE_BYTES = 5 * 1024 * 1024
MAX_VOICE_SECONDS = 30


class VoiceError(Exception):
    pass


@lru_cache(maxsize=1)
def load_model(path):
    from faster_whisper import WhisperModel

    return WhisperModel(
        str(path), device="cpu", compute_type="int8", cpu_threads=4, local_files_only=True
    )


def transcribe(audio, language=None):
    try:
        import av
        import numpy as np

        # Enforce duration on decoded samples, not just untrusted Telegram metadata.
        chunks = []
        samples = 0
        with av.open(BytesIO(audio)) as container:
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
            for frame in container.decode(audio=0):
                for converted in resampler.resample(frame):
                    samples += converted.samples
                    if samples > MAX_VOICE_SECONDS * 16000:
                        raise VoiceError("Audio too long")
                    chunks.append(converted.to_ndarray().flatten())
            for converted in resampler.resample(None):
                samples += converted.samples
                chunks.append(converted.to_ndarray().flatten())
        if not chunks or samples > MAX_VOICE_SECONDS * 16000:
            raise VoiceError("Empty or long audio")
        waveform = np.concatenate(chunks).astype(np.float32) / 32768.0
        model = load_model(settings.TELEGRAM_VOICE_MODEL)
        segments, info = model.transcribe(
            waveform,
            language=language,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        if info.language not in ("en", "pt"):
            raise VoiceError("Use English or Portuguese")
        text = " ".join(segment.text.strip() for segment in segments).strip(" .!?\n")
        if not 2 <= len(text) <= 200:
            raise VoiceError("No short speech detected")
        return text
    except VoiceError:
        raise
    except Exception:
        # Backend failures must not terminate polling or leak paths/audio into logs.
        raise VoiceError("Local speech recognition unavailable") from None
