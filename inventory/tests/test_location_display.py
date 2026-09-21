from unittest.mock import MagicMock

import pytest

from inventory.models import Location, Package, Reagent
from inventory.search import search_reagents
from inventory.telegram import ReagentBot

pytestmark = pytest.mark.django_db


@pytest.fixture
def cabinet():
    building = Location.objects.create(name="TEMA", location_type="building")
    lab = Location.objects.create(name="3.2.21", location_type="laboratory", parent=building)
    return Location.objects.create(name="Cabinet 1", location_type="cabinet", parent=lab)


@pytest.mark.parametrize(
    "name,extra,collapsed",
    [
        ("Unspecified shelf", False, True),
        ("Unspecified shelf", True, False),
        ("Shelf 1", False, False),
        ("Cabinet 1", False, True),
        ("Cabinet 1", True, False),
        (" cabinet  1 ", False, True),
    ],
)
def test_tree_paths_and_cabinet_contents(client, cabinet, name, extra, collapsed):
    shelf = Location.objects.create(name=name, location_type="shelf", parent=cabinet)
    if extra:
        Location.objects.create(name="Shelf 2", code="2", location_type="shelf", parent=cabinet)
    reagent = Reagent.objects.create(name="Acetone")
    package = Package.objects.create(reagent=reagent, location=shelf)
    assert bool(cabinet.collapsed_shelf) is collapsed
    expected = cabinet.full_path if collapsed else f"{cabinet.full_path} · {name}"
    assert shelf.full_path == expected
    response = client.get("/locations/", {"location": cabinet.pk})
    assert response.status_code == 200
    assert (f"?location={shelf.pk}" in response.content.decode()) is not collapsed
    assert (package in response.context["packages"]) is collapsed
    if collapsed:
        assert client.get("/", {"location": cabinet.pk}).context["page_obj"].paginator.count == 1
        assert package in client.get("/locations/", {"location": shelf.pk}).context["packages"]
        transport = MagicMock()
        ReagentBot(transport).locations(1, search_reagents("Acetone", available_only=True).get())
        assert "Unspecified shelf" not in transport.call.call_args.kwargs["text"]
        assert "Cabinet 1" in transport.call.call_args.kwargs["text"]


def test_empty_cabinet_is_not_collapsed(cabinet):
    assert cabinet.collapsed_shelf is None
