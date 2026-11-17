import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from inventory.models import Location, Package, Reagent
from inventory.voice import VoiceError
from inventory.whatsapp import WhatsAppBot, WhatsAppClient, WhatsAppError

pytestmark = pytest.mark.django_db


@pytest.fixture
def bot(settings):
    settings.WHATSAPP_ALLOWED_USER_IDS = set()
    settings.WHATSAPP_VOICE_ENABLED = True
    cache.clear()
    return WhatsAppBot(MagicMock())


@pytest.fixture
def stock():
    lab = Location.objects.create(name="Laboratory", code="3.2.7", location_type="laboratory")
    cabinet = Location.objects.create(name="Cabinet", code="A2", parent=lab, location_type="cabinet")
    shelf = Location.objects.create(name="Shelf", code="2", parent=cabinet, location_type="shelf")
    reagent = Reagent.objects.create(name="Acetone", cas_number="67-64-1")
    Package.objects.create(reagent=reagent, location=shelf, unit="L", current_quantity=2)
    return reagent


def inbound(text, sender="351918415948"):
    return {"from": sender, "type": "text", "text": {"body": text}}


@pytest.mark.parametrize("query", ["acet", "67-64-1", "/search acetone"])
def test_single_result_shows_locations(bot, stock, query):
    bot.handle(inbound(query))
    text = bot.client.text.call_args.args[1]
    assert "Acetone" in text
    assert "3.2.7 · A2 · 2" in text


def test_list_selection_and_pagination(bot, stock):
    for index in range(9):
        reagent = Reagent.objects.create(name=f"Acetone {index}")
        Package.objects.create(reagent=reagent)
    bot.handle(inbound("acetone"))
    rows = bot.client.list.call_args.args[2]
    assert len(rows) == 9
    assert all(len(row["title"]) <= 24 for row in rows)
    next_id = rows[-1]["id"]
    bot.handle({"from": "351918415948", "type": "interactive", "interactive": {"list_reply": {"id": next_id}}})
    assert "2/2" in bot.client.list.call_args.args[1]
    bot.handle({"from": "351918415948", "type": "interactive", "interactive": {"list_reply": {"id": f"r:{stock.pk}"}}})
    assert "3.2.7" in bot.client.text.call_args.args[1]
    bot.handle({"from": "351918415949", "type": "interactive", "interactive": {"list_reply": {"id": next_id}}})
    assert "expired" in bot.client.text.call_args.args[1]


def test_written_off_and_allowlist(bot, settings, stock):
    stock.packages.update(status="written_off")
    bot.handle(inbound("acetone"))
    assert "No available" in bot.client.text.call_args.args[1]
    settings.WHATSAPP_ALLOWED_USER_IDS = {"351918415949"}
    bot.handle(inbound("acetone"))
    assert "not authorized" in bot.client.text.call_args.args[1]


def test_voice_uses_shared_transcriber(bot, stock):
    with patch("inventory.whatsapp.transcribe", return_value="acetone") as transcribe:
        bot.client.download_audio.return_value = b"audio"
        bot.handle(inbound("/pt"))
        bot.handle({"from": "351918415948", "type": "audio", "audio": {"id": "12345"}})
    transcribe.assert_called_once_with(b"audio", "pt")
    assert "3.2.7" in bot.client.text.call_args.args[1]


def test_cloud_api_list_payload_and_audio_download():
    client = WhatsAppClient("secret", "1513874418467607", "v25.0")
    with patch.object(client, "_open", return_value=b'{"messages":[{"id":"wamid.test"}]}') as open_request:
        client.list("351918415948", "Choose", [{"id": "r:1", "title": "Acetone"}])
    request = open_request.call_args.args[0]
    payload = json.loads(request.data)
    assert payload["type"] == "interactive"
    assert payload["interactive"]["type"] == "list"
    assert payload["interactive"]["action"]["sections"][0]["rows"][0]["id"] == "r:1"
    with patch.object(client, "_open", side_effect=[
        json.dumps({"url": "https://lookaside.fbsbx.com/media", "file_size": 5}).encode(),
        b"audio",
    ]) as open_request:
        assert client.download_audio("12345") == b"audio"
        assert open_request.call_count == 2
    with patch.object(client, "_open", return_value=b'{"url":"https://example.com/media"}'):
        with pytest.raises(VoiceError):
            client.download_audio("12345")


def test_webhook_signature_and_duplicate(client, settings):
    settings.META_APP_SECRET = "test-secret"
    settings.ALLOWED_HOSTS = ["testserver"]
    cache.clear()
    event = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": {"messages": [
            {"id": "test-wa-unique", **inbound("acetone")}
        ]}}]}],
    }
    payload = json.dumps(event).encode()
    signature = "sha256=" + hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
    with patch("inventory.whatsapp_webhook.WhatsAppBot") as bot_class, patch(
        "inventory.whatsapp_webhook.WhatsAppClient"
    ):
        first = client.post(
            "/whatsapp/webhook/", data=payload, content_type="application/json",
            secure=True, HTTP_X_HUB_SIGNATURE_256=signature,
        )
        duplicate = client.post(
            "/whatsapp/webhook/", data=payload, content_type="application/json",
            secure=True, HTTP_X_HUB_SIGNATURE_256=signature,
        )
        invalid = client.post(
            "/whatsapp/webhook/", data=payload, content_type="application/json",
            secure=True, HTTP_X_HUB_SIGNATURE_256="sha256=wrong",
        )
    assert (first.status_code, duplicate.status_code, invalid.status_code) == (200, 200, 403)
    bot_class.return_value.handle.assert_called_once_with(event["entry"][0]["changes"][0]["value"]["messages"][0])


def test_expired_token_does_not_block_webhook_workers(client, settings):
    settings.META_APP_SECRET = "test-secret"
    settings.ALLOWED_HOSTS = ["testserver"]
    cache.clear()
    event = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": {"messages": [
            {"id": "test-wa-expired", **inbound("/start")}
        ]}}]}],
    }
    payload = json.dumps(event).encode()
    signature = "sha256=" + hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
    with patch("inventory.whatsapp_webhook.WhatsAppBot") as bot_class, patch(
        "inventory.whatsapp_webhook.WhatsAppClient"
    ):
        bot_class.return_value.handle.side_effect = WhatsAppError(401)
        statuses = [
            client.post(
                "/whatsapp/webhook/", data=payload, content_type="application/json",
                secure=True, HTTP_X_HUB_SIGNATURE_256=signature,
            ).status_code
            for _ in range(2)
        ]
    assert statuses == [503, 503]
    bot_class.return_value.handle.assert_called_once()
