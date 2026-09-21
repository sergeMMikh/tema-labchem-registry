import json
from io import BytesIO, StringIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError

from inventory.models import Location, Package, Reagent
from inventory.telegram import ReagentBot, TelegramClient, TelegramError

pytestmark = pytest.mark.django_db


@pytest.fixture
def bot(settings):
    settings.TELEGRAM_ALLOWED_USER_IDS = set()
    cache.clear()
    return ReagentBot(MagicMock())


@pytest.fixture
def stock():
    lab = Location.objects.create(name="Laboratory", code="3.2.7", location_type="laboratory")
    cabinet = Location.objects.create(
        name="Cabinet", code="A2", parent=lab, location_type="cabinet"
    )
    shelf = Location.objects.create(name="Shelf", code="2", parent=cabinet, location_type="shelf")
    reagent = Reagent.objects.create(name="Acetone", cas_number="67-64-1")
    Package.objects.create(reagent=reagent, location=shelf, unit="L", current_quantity=2)
    return reagent


def message(text, user=12, chat_type="private"):
    return {
        "message": {"chat": {"id": user, "type": chat_type}, "from": {"id": user}, "text": text}
    }


def callback(data, user=12):
    return {
        "callback_query": {
            "id": "callback-id",
            "data": data,
            "from": {"id": user},
            "message": {"chat": {"id": user, "type": "private"}},
        }
    }


@pytest.mark.parametrize("query", ["acet", "67-64-1", "/search acetone"])
def test_single_result_shows_full_location(bot, stock, query):
    bot.handle(message(query))
    text = bot.client.call.call_args.kwargs["text"]
    assert "Acetone" in text
    assert "3.2.7 · A2 · 2" in text


def test_multiple_results_and_selection(bot, stock):
    other = Reagent.objects.create(name="Acetone pure")
    Package.objects.create(reagent=other)
    bot.handle(message("acetone"))
    keyboard = bot.client.call.call_args.kwargs["reply_markup"]["inline_keyboard"]
    assert len(keyboard) == 2
    assert all(len(row[0]["callback_data"].encode()) <= 64 for row in keyboard)
    bot.handle(callback(keyboard[0][0]["callback_data"]))
    assert "3.2.7" in bot.client.call.call_args.kwargs["text"]
    assert any(c.args[0] == "answerCallbackQuery" for c in bot.client.call.call_args_list)


def test_retired_stock_excluded_and_stale_selection(bot, stock):
    stock.packages.update(status="written_off")
    bot.handle(message("acetone"))
    assert "No available" in bot.client.call.call_args.kwargs["text"]
    bot.handle(callback(f"r:{stock.pk}"))
    assert "no longer available" in bot.client.call.call_args.kwargs["text"]


def test_pagination_is_scoped_to_user_and_expires(bot):
    for index in range(10):
        reagent = Reagent.objects.create(name=f"Acetone {index}")
        Package.objects.create(reagent=reagent)
    bot.handle(message("acetone"))
    data = bot.client.call.call_args.kwargs["reply_markup"]["inline_keyboard"][-1][0][
        "callback_data"
    ]
    bot.handle(callback(data))
    assert "2/2" in bot.client.call.call_args.kwargs["text"]
    bot.handle(callback(data, user=99))
    assert "expired" in bot.client.call.call_args.kwargs["text"]
    cache.clear()
    bot.handle(callback(data))
    assert "expired" in bot.client.call.call_args.kwargs["text"]


def test_allowlist_and_groups(bot, settings, stock):
    settings.TELEGRAM_ALLOWED_USER_IDS = {99}
    bot.handle(message("acetone"))
    assert "not authorized" in bot.client.call.call_args.kwargs["text"]
    bot.client.reset_mock()
    bot.handle(message("acetone", chat_type="group"))
    bot.client.call.assert_not_called()


@pytest.mark.parametrize("text", ["/start", "/help", "", "a", "x" * 201, "/unknown"])
def test_help_and_invalid_queries(bot, text):
    bot.handle(message(text))
    assert bot.client.call.call_args.args[0] == "sendMessage"


@pytest.mark.parametrize("data", ["r:bad", "p:bad", "p:key:not-number"])
def test_invalid_callbacks(bot, data):
    bot.handle(callback(data))
    assert bot.client.call.call_args.args[0] == "sendMessage"


def test_all_packages_and_long_response(bot, stock):
    stock.sds_url = "https://example.test/sds.pdf"
    stock.save()
    Package.objects.bulk_create([Package(reagent=stock) for _ in range(60)])
    bot.handle(message("acetone"))
    texts = [call.kwargs["text"] for call in bot.client.call.call_args_list]
    assert len(texts) > 1
    assert all(len(t) <= 1900 for t in texts)
    assert "https://example.test/sds.pdf" in "".join(texts)
    assert "Unknown" in "".join(texts)


def test_transport_and_redacted_errors():
    client = TelegramClient("secret-token")
    with patch("inventory.telegram.urllib.request.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value = BytesIO(
            json.dumps({"ok": True, "result": []}).encode()
        )
        assert client.call("getUpdates") == []
        urlopen.side_effect = URLError("URL with secret-token")
        with pytest.raises(TelegramError) as error:
            client.call("getMe")
        assert "secret-token" not in str(error.value)
        urlopen.side_effect = HTTPError(
            "secret-token", 429, "rate limit", {}, BytesIO(b'{"parameters":{"retry_after":2}}')
        )
        with pytest.raises(TelegramError) as error:
            client.call("getMe")
        assert error.value.retry_after == 2
    with pytest.raises(ValueError):
        TelegramClient("")


def test_worker_check_and_webhook(settings):
    settings.TELEGRAM_BOT_TOKEN = "test"
    with patch("inventory.management.commands.run_telegram_bot.TelegramClient") as cls:
        cls.return_value.call.side_effect = [{"username": "testbot"}, {}]
        call_command("run_telegram_bot", check=True, stdout=StringIO())
        cls.return_value.call.side_effect = [
            {"username": "testbot"},
            {"url": "https://example.test"},
        ]
        with pytest.raises(CommandError):
            call_command("run_telegram_bot", check=True, stdout=StringIO())


def test_worker_processes_update_and_offset(settings):
    settings.TELEGRAM_BOT_TOKEN = "test"
    module = "inventory.management.commands.run_telegram_bot"
    with patch(f"{module}.TelegramClient") as cls, patch(f"{module}.ReagentBot") as bot_cls:
        update = {"update_id": 40, **message("acetone")}
        cls.return_value.call.side_effect = [
            {"username": "testbot"},
            {},
            [update],
            KeyboardInterrupt(),
        ]
        call_command("run_telegram_bot", stdout=StringIO())
        bot_cls.return_value.handle.assert_called_once_with(update)
        assert cls.return_value.call.call_args.kwargs["offset"] == 41
