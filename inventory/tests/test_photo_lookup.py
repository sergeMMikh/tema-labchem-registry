"""Photo lookup must prefer the inventory and preserve a safe fallback."""

from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest
from django.core.cache import cache

from inventory.models import Location, Package, Reagent
from inventory.photo_lookup import _official_sigma_url, inventory_match, sigma_lookup
from inventory.telegram import ReagentBot
from inventory.whatsapp import WhatsAppBot

pytestmark = pytest.mark.django_db

FIELDS = {
    "name": "Acetone", "cas": "67-64-1", "catalog_number": "179124",
    "manufacturer": "Sigma-Aldrich",
}


def test_inventory_match_by_cas_includes_unavailable_stock():
    reagent = Reagent.objects.create(name="Acetone", cas_number="67-64-1")
    Package.objects.create(reagent=reagent, status=Package.Status.WRITTEN_OFF)
    assert inventory_match(FIELDS).pk == reagent.pk


def test_telegram_photo_uses_inventory_without_sigma(settings):
    settings.TELEGRAM_ALLOWED_USER_IDS = set()
    reagent = Reagent.objects.create(name="Acetone", cas_number="67-64-1")
    location = Location.objects.create(name="Lab", code="3.2.7", location_type="laboratory")
    Package.objects.create(reagent=reagent, location=location)
    client = MagicMock()
    client.download_photo.return_value = b"photo"
    with patch("inventory.telegram.identify_label", return_value=FIELDS), patch(
        "inventory.telegram.sigma_lookup"
    ) as sigma:
        ReagentBot(client).handle({"message": {
            "chat": {"id": 12, "type": "private"}, "from": {"id": 12},
            "photo": [{"file_id": "photo-id", "file_size": 123}],
        }})
    sigma.assert_not_called()
    assert "3.2.7" in client.call.call_args.kwargs["text"]


def test_whatsapp_photo_falls_back_to_sigma(settings):
    settings.WHATSAPP_ALLOWED_USER_IDS = set()
    client = MagicMock()
    client.download_image.return_value = b"photo"
    with patch("inventory.whatsapp.identify_label", return_value=FIELDS), patch(
        "inventory.whatsapp.sigma_lookup", return_value={"url": "https://www.sigmaaldrich.com/PT/en/search/67-64-1"}
    ) as sigma:
        WhatsAppBot(client).handle({"from": "351918415948", "type": "image", "image": {"id": "123"}})
    sigma.assert_called_once()
    assert "sigmaaldrich.com" in client.text.call_args.args[1]


def test_sigma_uses_official_index_when_direct_site_unavailable():
    with patch("inventory.photo_lookup.urllib.request.urlopen", side_effect=URLError("offline")), patch(
        "inventory.photo_lookup._sigma_index_lookup",
        return_value={"summary": "Acetone CAS 67-64-1", "source_url": "https://www.sigmaaldrich.com/US/en/product/sigald/179124"},
    ) as indexed:
        result = sigma_lookup(FIELDS)
    indexed.assert_called_once_with(FIELDS)
    assert result["summary"] == "Acetone CAS 67-64-1"
    assert _official_sigma_url(result["source_url"])
    assert not _official_sigma_url("https://sigmaaldrich.com.evil.example/product")


def test_telegram_save_requires_yes_and_location(settings):
    settings.TELEGRAM_ALLOWED_USER_IDS = set()
    settings.TELEGRAM_SAVE_USER_IDS = set()
    cache.clear()
    location = Location.objects.create(name="Cabinet", code="A2", location_type="cabinet")
    client = MagicMock()
    client.download_photo.return_value = b"photo"
    bot = ReagentBot(client)
    with patch("inventory.telegram.identify_label", return_value=FIELDS), patch(
        "inventory.telegram.sigma_lookup", return_value={"url": "https://www.sigmaaldrich.com/PT/en/search/67-64-1"}
    ):
        bot.handle({"message": {"chat": {"id": 12, "type": "private"}, "from": {"id": 12},
                                "photo": [{"file_id": "photo-id"}]}})
    assert Reagent.objects.count() == 0
    yes = client.call.call_args.kwargs["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    def choose(action):
        bot.handle({"callback_query": {"id": "callback-id", "data": action,
                    "from": {"id": 12}, "message": {"chat": {"id": 12, "type": "private"}}}})
    choose(yes)
    assert Reagent.objects.count() == 0
    place = client.call.call_args.kwargs["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    assert str(location.pk) in place
    choose(place)
    reagent = Reagent.objects.get()
    package = reagent.packages.get()
    assert reagent.cas_number == "67-64-1"
    assert package.location == location
    assert package.status == Package.Status.PENDING
    assert package.current_quantity is None
    choose(place)
    assert Reagent.objects.count() == 1


def test_whatsapp_no_cancels_save(settings):
    settings.WHATSAPP_ALLOWED_USER_IDS = set()
    settings.WHATSAPP_SAVE_USER_IDS = set()
    cache.clear()
    client = MagicMock()
    client.download_image.return_value = b"photo"
    bot = WhatsAppBot(client)
    with patch("inventory.whatsapp.identify_label", return_value=FIELDS), patch(
        "inventory.whatsapp.sigma_lookup", return_value={"url": "https://www.sigmaaldrich.com/PT/en/search/67-64-1"}
    ):
        bot.handle({"from": "351918415948", "type": "image", "image": {"id": "123"}})
    no = client.buttons.call_args.args[2][1]["id"]
    bot.handle({"from": "351918415948", "type": "interactive",
                "interactive": {"button_reply": {"id": no}}})
    assert Reagent.objects.count() == 0
    assert "Not saved" in client.text.call_args.args[1]


def test_whatsapp_save_is_scoped_to_sender_and_location(settings):
    settings.WHATSAPP_ALLOWED_USER_IDS = set()
    settings.WHATSAPP_SAVE_USER_IDS = set()
    cache.clear()
    location = Location.objects.create(name="Shelf", code="B3", location_type="shelf")
    client = MagicMock()
    client.download_image.return_value = b"photo"
    bot = WhatsAppBot(client)
    with patch("inventory.whatsapp.identify_label", return_value=FIELDS), patch(
        "inventory.whatsapp.sigma_lookup", return_value={"url": "https://www.sigmaaldrich.com/PT/en/search/67-64-1"}
    ):
        bot.handle({"from": "351918415948", "type": "image", "image": {"id": "123"}})
    yes = client.buttons.call_args.args[2][0]["id"]
    def choose(sender, action):
        bot.handle({"from": sender, "type": "interactive", "interactive": {"button_reply": {"id": action}}})
    choose("351918415949", yes)
    assert Reagent.objects.count() == 0
    choose("351918415948", yes)
    place = client.list.call_args.args[2][0]["id"]
    assert str(location.pk) in place
    choose("351918415948", place)
    assert Reagent.objects.count() == 1
    assert Package.objects.get().location == location
    choose("351918415948", place)
    assert Reagent.objects.count() == 1
