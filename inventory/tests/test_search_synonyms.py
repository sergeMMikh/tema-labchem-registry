from unittest.mock import MagicMock

import pytest

from inventory.models import Package, Reagent
from inventory.search import search_reagents
from inventory.telegram import ReagentBot

pytestmark = pytest.mark.django_db


@pytest.fixture
def reagents():
    records = [
        ("Nitric acid, 65% (Duncan)", ""),
        ("Nitric acid, 65%", "7697-37-2"),
        ("Ácido nítrico, 30%", ""),
        ("Acetone, HPLC grade", "67-64-1"),
        ("Acetona", ""),
        ("Iron(III) acetylacetonate, 97%", "14024-18-1"),
    ]
    result = []
    for name, cas in records:
        reagent = Reagent.objects.create(name=name, cas_number=cas)
        Package.objects.create(reagent=reagent)
        result.append(reagent)
    return result


@pytest.mark.parametrize(
    "query", ["Ácido nitrico", "acido nitrico", "ÁCIDO NÍTRICO", "nitric acid", "ácido   nítrico"]
)
def test_nitric_acid_equivalents(query, reagents):
    assert set(search_reagents(query)) == set(reagents[:3])


@pytest.mark.parametrize("query", ["Acetona", "acetone", "ACETONA"])
def test_acetone_does_not_match_acetylacetonate(query, reagents):
    assert set(search_reagents(query)) == set(reagents[3:5])


def test_concentration_and_partial_search(reagents):
    assert set(search_reagents("ácido nítrico 65%")) == set(reagents[:2])
    assert list(search_reagents("acetylacetonate")) == [reagents[5]]
    assert list(search_reagents("67-64-1")) == [reagents[3]]


def test_aliases_respect_availability(client, settings, reagents):
    settings.TELEGRAM_ALLOWED_USER_IDS = set()
    reagents[3].packages.update(status="written_off")
    assert list(search_reagents("acetone", available_only=True)) == [reagents[4]]
    transport = MagicMock()
    bot = ReagentBot(transport)
    bot.handle(
        {
            "message": {
                "chat": {"id": 1, "type": "private"},
                "from": {"id": 1},
                "text": "Ácido nitrico",
            }
        }
    )
    buttons = transport.call.call_args.kwargs["reply_markup"]["inline_keyboard"]
    assert len(buttons) == 3
    response = client.get("/api/v1/reagents/", {"q": "Ácido nitrico"})
    assert response.json()["count"] == 3
