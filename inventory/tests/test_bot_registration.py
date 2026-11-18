from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.core.cache import cache

from inventory.models import Location, Package, Reagent, StockMovement
from inventory.telegram import ReagentBot
from inventory.whatsapp import WhatsAppBot

pytestmark = pytest.mark.django_db


@pytest.fixture(params=["telegram", "whatsapp"])
def chat(request, settings):
    settings.TELEGRAM_ALLOWED_USER_IDS = set()
    settings.WHATSAPP_ALLOWED_USER_IDS = set()
    settings.TELEGRAM_SAVE_USER_IDS = set()
    settings.WHATSAPP_SAVE_USER_IDS = set()
    cache.clear()
    client = MagicMock()
    if request.param == "telegram":
        bot = ReagentBot(client)

        def send(text, who=12):
            client.call.reset_mock()
            bot.handle({"message": {"chat": {"id": who, "type": "private"},
                                    "from": {"id": who}, "text": text}})
            return "\n".join(call.kwargs["text"] for call in client.call.call_args_list)
    else:
        bot = WhatsAppBot(client)

        def send(text, who=12):
            client.text.reset_mock()
            bot.handle({"from": f"3519184159{who}", "type": "text", "text": {"body": text}})
            return "\n".join(call.args[1] for call in client.text.call_args_list)
    return send


def test_search_only_then_explicit_registration_and_repeated_edits(chat):
    for index in range(9):
        Location.objects.create(name=f"Shelf {index}", code=f"A{index}", location_type="shelf")
    assert "Search for the reagent first" in chat("/add")
    assert "Not found in the database" in chat("Reagent X")
    assert Reagent.objects.count() == 0
    assert "Название" in chat("Добавь, пожалуйста!")
    assert "Search for the reagent first" in chat("add", who=13)
    assert "Формула" in chat("Reagent X")
    assert "CAS" in chat("пропустить")
    assert "Неверное" in chat("invalid-cas")
    for value in (
        "67-64-1", "Demo Supplier", "PRODUCT-1", "Demo category", "2",
        "mL", "https://example.test/sds", "Demo description", "XYZ-1", "batch",
        "10,5", "12", "mL", "99%", "05/11/2026", "06/11/2026", "07/11/2027",
    ):
        chat(value)
    assert "A8" in chat("далее")
    assert "A0" in chat("назад")
    chat("далее")
    chat("1")
    card = chat("Пропустить")
    assert "Карточка реагента" in card
    assert "A8" in card
    assert "05/11/2026" in card
    assert "Остаток не может превышать" in chat("подтвердить")
    assert "Какой пункт" in chat("изменить")
    assert "номер из списка" in chat("неизвестное поле")
    assert "Остаток" in chat("14")
    assert "Остаток: 8.5" in chat("8,5")
    assert "Какой пункт" in chat("3")
    assert "Формула" in chat("Формула")
    assert "Формула: C3H6O" in chat("C3H6O")
    assert Reagent.objects.count() == 0
    assert "сохранён" in chat("1")
    reagent = Reagent.objects.get()
    package = reagent.packages.get()
    assert reagent.formula == "C3H6O"
    assert reagent.supplier.name == "Demo Supplier"
    assert reagent.category.name == "Demo category"
    assert package.location.code == "A8"
    assert package.current_quantity == Decimal("8.5")
    assert package.received_at == date(2026, 11, 5)
    assert package.status == Package.Status.PENDING
    assert StockMovement.objects.get().package == package
    chat("1")
    assert Reagent.objects.count() == 1


def test_portuguese_cancel_and_existing_pending_is_not_missing(chat):
    reagent = Reagent.objects.create(name="Existing reagent")
    Package.objects.create(reagent=reagent, status=Package.Status.PENDING)
    assert "No available" in chat("Existing reagent")
    assert "Pesquise" in chat("adicione")
    assert "Not found in the database" in chat("Another reagent")
    assert "Nome" in chat("adicionar")
    assert "Rascunho cancelado" in chat("cancelar")
    assert Reagent.objects.count() == 1


def test_duplicate_at_confirmation_preserves_existing_stock(chat):
    Location.objects.create(name="Shelf", location_type="shelf")
    chat("Unlisted")
    chat("please add")
    chat("Unlisted")
    for _ in range(18):
        chat("skip")
    chat("1")
    chat("skip")
    existing = Reagent.objects.create(name="Unlisted")
    assert "Already in inventory" in chat("confirm")
    assert Reagent.objects.get() == existing
    assert Package.objects.count() == 0
