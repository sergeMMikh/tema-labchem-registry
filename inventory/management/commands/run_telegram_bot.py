import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from inventory.telegram import ReagentBot, TelegramClient, TelegramError


class Command(BaseCommand):
    help = "Run the read-only reagent search Telegram bot using long polling."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check", action="store_true", help="Verify token and webhook without polling"
        )

    def handle(self, *args, **options):
        try:
            client = TelegramClient(settings.TELEGRAM_BOT_TOKEN)
            identity = client.call("getMe")
            webhook = client.call("getWebhookInfo")
        except (TelegramError, ValueError) as exc:
            raise CommandError(str(exc)) from None
        if webhook.get("url"):
            raise CommandError(
                "A webhook is configured. Remove it before running a polling worker."
            )
        self.stdout.write(f"Telegram @{identity['username']}: connected; webhook absent.")
        if options["check"]:
            return
        bot = ReagentBot(client)
        offset = 0
        self.stdout.write("Polling started. Stop with Ctrl+C. Run only one worker per token.")
        try:
            while True:
                update = None
                try:
                    updates = client.call(
                        "getUpdates",
                        offset=offset,
                        timeout=25,
                        allowed_updates=["message", "callback_query"],
                    )
                    for update in updates:
                        close_old_connections()
                        bot.handle(update)
                        offset = update["update_id"] + 1
                except TelegramError as exc:
                    if exc.code in (401, 404, 409):
                        raise CommandError(str(exc)) from None
                    if exc.code in (400, 403) and update is not None:
                        # A blocked/deleted chat must not prevent other users' searches.
                        offset = update["update_id"] + 1
                    self.stderr.write(str(exc))
                    time.sleep(exc.retry_after)
        except KeyboardInterrupt:
            self.stdout.write("Telegram worker stopped.")
