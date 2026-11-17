from unittest.mock import MagicMock

import pytest

from django.core.management import call_command

from inventory.management.commands.import_inventory import Command as ImportCommand
from inventory.models import Location, Package, Reagent, StockMovement
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
    assert package in response.context["packages"]
    if collapsed:
        assert client.get("/", {"location": cabinet.pk}).context["page_obj"].paginator.count == 1
        assert package in client.get("/locations/", {"location": shelf.pk}).context["packages"]
        transport = MagicMock()
        ReagentBot(transport).locations(1, search_reagents("Acetone", available_only=True).get())
        assert "Unspecified shelf" not in transport.call.call_args.kwargs["text"]
        assert "Cabinet 1" in transport.call.call_args.kwargs["text"]


def test_empty_cabinet_is_not_collapsed(cabinet):
    assert cabinet.collapsed_shelf is None


def test_reagent_filter_lists_laboratories_only(client, cabinet):
    shelf = Location.objects.create(name="Unspecified shelf", location_type="shelf", parent=cabinet)
    labs = client.get("/").context["labs"]
    assert cabinet.parent in labs
    assert cabinet not in labs
    assert shelf not in labs


def test_merge_hyphen_variants_preserves_packages_and_movements(cabinet):
    cabinet.parent.code = "3.2.21"
    cabinet.parent.save(update_fields=["code"])
    cabinet.name = "Cabinet 4 - Professor Completo"
    cabinet.code = cabinet.name
    cabinet.save(update_fields=["name", "code"])
    other = Location.objects.create(
        name="Cabinet 4- Professor Completo", code="Cabinet 4- Professor Completo",
        location_type="cabinet", parent=cabinet.parent,
    )
    first_shelf = Location.objects.create(
        name="Unspecified shelf", code="Unspecified shelf", location_type="shelf", parent=cabinet,
    )
    second_shelf = Location.objects.create(
        name="Unspecified shelf", code="Unspecified shelf", location_type="shelf", parent=other,
    )
    reagent = Reagent.objects.create(name="Acetone")
    package = Package.objects.create(reagent=reagent, location=second_shelf)
    movement = StockMovement.objects.create(
        package=package, movement_type=StockMovement.Type.MOVE,
        from_location=second_shelf, to_location=second_shelf,
    )
    call_command("merge_duplicate_locations")
    package.refresh_from_db()
    movement.refresh_from_db()
    assert package.location_id == first_shelf.pk
    assert movement.from_location_id == first_shelf.pk
    assert movement.to_location_id == first_shelf.pk
    assert not Location.objects.filter(pk=other.pk).exists()
    assert not Location.objects.filter(pk=second_shelf.pk).exists()
    assert ImportCommand().get_location(
        cabinet.parent.parent, "3.2.21", "Cabinet 4-Professor Completo", ""
    ).pk == first_shelf.pk
    assert Location.objects.filter(parent=cabinet.parent, location_type="cabinet").count() == 1


def test_broken_desiccator_aliases_share_one_cabinet_and_shelf(client, cabinet):
    cabinet.parent.code = "3.2.21"
    cabinet.parent.save(update_fields=["code"])
    cabinet.name = "Broken Desiccator"
    cabinet.code = cabinet.name
    cabinet.save(update_fields=["name", "code"])
    canonical_shelf = Location.objects.create(
        name="Broken Desiccator", code="Broken Desiccator",
        location_type="shelf", parent=cabinet,
    )
    alias = Location.objects.create(
        name="Broken Dessicator", code="Broken Dessicator",
        location_type="cabinet", parent=cabinet.parent,
    )
    alias_shelf = Location.objects.create(
        name="Unspecified shelf", code="Unspecified shelf",
        location_type="shelf", parent=alias,
    )
    package = Package.objects.create(reagent=Reagent.objects.create(name="Acetone"), location=alias_shelf)
    movement = StockMovement.objects.create(
        package=package, movement_type=StockMovement.Type.IMPORT, to_location=alias_shelf,
    )
    call_command("merge_duplicate_locations")
    package.refresh_from_db()
    movement.refresh_from_db()
    assert package.location_id == canonical_shelf.pk
    assert movement.to_location_id == canonical_shelf.pk
    assert list(cabinet.children.values_list("pk", flat=True)) == [canonical_shelf.pk]
    assert not Location.objects.filter(pk=alias.pk).exists()
    assert not Location.objects.filter(pk=alias_shelf.pk).exists()
    assert canonical_shelf not in client.get("/").context["labs"]
    for variant in ("Broken Desicador", "Broken Dessicator", "Broken Desiccator"):
        imported = ImportCommand().get_location(cabinet.parent.parent, "3.2.21", variant, "")
        assert imported.pk == canonical_shelf.pk
    assert Location.objects.filter(parent=cabinet.parent, location_type="cabinet").count() == 1


def test_reagent_filter_selects_lab_and_excel_sheet(client, cabinet):
    cabinet.parent.code = "3.2.22"
    cabinet.parent.save(update_fields=["code"])
    cabinet.name = "Freezer 1 Shelf 2"
    cabinet.save(update_fields=["name"])
    first = Location.objects.create(name="(Paula)", code="Paula", location_type="shelf", parent=cabinet)
    second = Location.objects.create(name="(Nathalie)", code="Nathalie", location_type="shelf", parent=cabinet)
    other = Location.objects.create(name="Gil cabinet", code="Gil cabinet", location_type="cabinet", parent=cabinet.parent)
    reagents = [Reagent.objects.create(name=f"Reagent {n}") for n in range(3)]
    source_sheets = (
        "Inventário 3.2.22", "Inventário 3.2.22",
        "Inventário 3.2.22 (Vapour cab)",
    )
    for index, (reagent, place, sheet) in enumerate(zip(reagents, (first, second, other), source_sheets)):
        Package.objects.create(reagent=reagent, location=place, source_key=f"checksum:{sheet}:{index + 1}")
    Package.objects.create(
        reagent=reagents[0], location=other,
        source_key="checksum:Inventário 3.2.22 (Vapour cab):4",
    )

    response = client.get("/")
    html = response.content.decode()
    assert cabinet.parent in response.context["labs"]
    assert 'id="filter-lab"' in html and 'id="filter-sheet"' in html
    assert "Inventário 3.2.22 (Vapour cab)" in html
    assert first.full_path.startswith("3.2.22 · ")
    assert not first.full_path.startswith("TEMA")

    for params, expected in (
        ({"lab": str(cabinet.parent.pk)}, 3),
        ({"lab": str(cabinet.parent.pk), "sheet": "Inventário 3.2.22"}, 2),
        ({"lab": str(cabinet.parent.pk), "sheet": "Inventário 3.2.22 (Vapour cab)"}, 2),
        ({"location": str(first.pk)}, 1),
    ):
        filtered = client.get("/", params)
        assert filtered.context["page_obj"].paginator.count == expected
    primary = client.get("/", {"lab": str(cabinet.parent.pk), "sheet": "Inventário 3.2.22"})
    assert len(primary.context["page_obj"][0].packages.all()) == 1
    assert "Vapour cab" not in primary.context["page_obj"][0].packages.all()[0].source_key
    assert client.get("/locations/", {"location": cabinet.parent.pk}).context["packages"].count() == 4
