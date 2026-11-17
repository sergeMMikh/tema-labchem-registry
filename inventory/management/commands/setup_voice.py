from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Download and verify the multilingual small voice model (one-time setup)."

    def handle(self, *args, **options):
        try:
            from faster_whisper.utils import download_model

            from inventory.voice import load_model

            download_model("small", output_dir=str(settings.TELEGRAM_VOICE_MODEL))
            load_model(settings.TELEGRAM_VOICE_MODEL)
        except Exception:
            raise CommandError(
                "Voice setup failed. Check requirements-voice.txt and network."
            ) from None
        self.stdout.write(self.style.SUCCESS("Local PT/EN voice model ready."))
