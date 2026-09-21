from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from openpyxl import Workbook

from inventory.forms import PackageForm, ReagentForm
from inventory.management.commands.import_inventory import normalize_cas, parse_quantity
from inventory.models import ImportBatch, Location, Package, Reagent, StockMovement
from inventory.services import use_package, write_off_package

pytestmark = pytest.mark.django_db


@pytest.fixture
def package():
    reagent = Reagent.objects.create(name="Acetone", cas_number="67-64-1", formula="C3H6O")
    location = Location.objects.create(name="Shelf", code="A", location_type="shelf")
    return Package.objects.create(
        reagent=reagent, location=location, initial_quantity=10, current_quantity=10, unit="g"
    )


@pytest.mark.parametrize("quantity", ["0", "-1", "11"])
def test_invalid_consumption_leaves_stock_unchanged(package, quantity):
    with pytest.raises(ValidationError):
        use_package(package=package, quantity=Decimal(quantity))
    package.refresh_from_db()
    assert package.current_quantity == 10
    assert not StockMovement.objects.exists()


@pytest.mark.parametrize("amount,status", [(8, "low_stock"), (10, "written_off")])
def test_consumption_status_transition(package, amount, status):
    use_package(package=package, quantity=amount)
    package.refresh_from_db()
    assert package.status == status
    assert package.current_quantity == 10 - amount


@pytest.mark.parametrize("status,quantity", [("reserved", 10), ("available", None)])
def test_unusable_package_rejected(package, status, quantity):
    package.status, package.current_quantity = status, quantity
    package.save()
    with pytest.raises(ValidationError):
        use_package(package=package, quantity=1)


def test_audit_failure_rolls_back_stock(package):
    with patch("inventory.services.StockMovement.objects.create", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            use_package(package=package, quantity=1)
    package.refresh_from_db()
    assert package.current_quantity == 10


@pytest.mark.parametrize("quantity", [10, None])
def test_write_off_preserves_record_and_history(package, quantity):
    package.current_quantity = quantity
    package.save()
    write_off_package(package=package, reason="Consumed")
    package.refresh_from_db()
    assert package.status == "written_off"
    event = package.movements.get()
    assert event.reason == "Consumed"
    assert event.quantity_before == quantity


@pytest.mark.parametrize("route", ["overview", "location-list", "attention-list", "reagent-list"])
def test_pages_render(client, package, route):
    assert client.get(reverse(f"inventory:{route}")).status_code == 200


def test_application_accepts_arbitrary_host(client, package):
    response = client.get(reverse("inventory:reagent-list"), HTTP_HOST="192.168.10.25:8767")
    assert response.status_code == 200


@pytest.mark.parametrize("action", ["package-use", "package-move", "package-write-off"])
def test_mutations_require_permission(client, django_user_model, package, action):
    user = django_user_model.objects.create_user(username="viewer")
    client.force_login(user)
    response = client.post(reverse(f"inventory:{action}", args=[package.pk]), {})
    assert response.status_code == 403
    assert not package.movements.exists()


@pytest.mark.parametrize(
    "action,permission,data",
    [
        ("package-use", "use_package", {"quantity": "1"}),
        ("package-move", "move_package", {}),
        ("package-write-off", "write_off_package", {"reason": "Expired"}),
    ],
)
def test_authorized_actions_audited(client, django_user_model, package, action, permission, data):
    user = django_user_model.objects.create_user(username="chemist")
    user.user_permissions.add(Permission.objects.get(codename=permission))
    client.force_login(user)
    data = dict(data)
    if action == "package-move":
        data["location"] = str(package.location_id)
    url = reverse(f"inventory:{action}", args=[package.pk])
    assert client.get(url).status_code == 200
    assert client.post(url, data).status_code == 302
    assert package.movements.get().performed_by == user


def test_invalid_consumption_shows_form_error(client, admin_user, package):
    client.force_login(admin_user)
    response = client.post(reverse("inventory:package-use", args=[package.pk]), {"quantity": 100})
    assert response.status_code == 200
    assert response.context["form"].non_field_errors()


@pytest.mark.parametrize("query", ["Acet", "67-64-1", "C3H6O"])
def test_search_api(client, package, query):
    response = client.get(reverse("inventory:api-reagent-list"), {"q": query})
    assert response.json()["results"][0]["id"] == str(package.reagent_id)


def test_sds_link_is_visible_in_list_quick_view_and_detail(client, package):
    package.reagent.sds_url = "https://example.test/acetone-sds.pdf"
    package.reagent.save()
    urls = [
        reverse("inventory:reagent-list"),
        reverse("inventory:reagent-quick", args=[package.reagent_id]),
        reverse("inventory:reagent-detail", args=[package.reagent_id]),
    ]
    for url in urls:
        response = client.get(url)
        assert 'href="https://example.test/acetone-sds.pdf"' in response.content.decode()


def test_filters_pagination_and_locations(client, package):
    Reagent.objects.bulk_create([Reagent(name=f"Other {i}") for i in range(24)])
    response = client.get("/", {"per_page": 10, "page": 2, "ordering": "-name"})
    assert len(response.context["page_obj"]) == 10
    response = client.get("/", {"location": str(package.location_id), "status": "available"})
    assert response.context["page_obj"].paginator.count == 1
    response = client.get("/locations/", {"location": str(package.location_id)})
    assert list(response.context["packages"]) == [package]


@pytest.mark.parametrize(
    "url",
    [
        "/?per_page=bad",
        "/?location=bad",
        "/locations/?location=bad",
        "/api/v1/reagents/?location=bad",
    ],
)
def test_invalid_query_is_not_server_error(client, url):
    assert client.get(url).status_code in {200, 400, 404}


def test_forms_reject_invalid_fields_and_image():
    form = ReagentForm(data={"name": "Test", "cas_number": "invalid", "physical_state": "solid"})
    assert not form.is_valid()
    assert "cas_number" in form.errors
    form = PackageForm(
        data={"initial_quantity": 1, "current_quantity": 2, "status": "available"},
        files={
            "label_photo": SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
        },
    )
    assert not form.is_valid()
    assert {"current_quantity", "label_photo"} <= set(form.errors)


def test_create_reagent(client, admin_user):
    client.force_login(admin_user)
    url = reverse("inventory:reagent-create")
    assert client.get(url).status_code == 200
    assert (
        client.post(
            url, {"name": "New", "physical_state": "solid", "package-status": "available"}
        ).status_code
        == 302
    )
    assert Package.objects.get().reagent.name == "New"


def test_import_is_idempotent_and_skips_old_snapshot(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Inventário Gases (agosto 2026)"
    sheet.append(["Name", "CAS", "Quantity", "Supplier", "Storage", "Link to SDS"])
    sheet.append(["Acetone", "67-64-1", "2.5 L", "Supplier", "Lab 3.2.7", "Safety sheet"])
    sheet["F2"].hyperlink = "https://example.test/acetone-sds.pdf"
    sheet.append(["Unknown", "bad", "?", "Supplier", "Lab 3.2.7", ""])
    sheet.append(["Inventário", None, None, None, None])
    old = workbook.create_sheet("Inventário Gases (abril 2026)")
    old.append(["Name", "CAS"])
    old.append(["Old", "67-64-1"])
    path = tmp_path / "source.xlsx"
    workbook.save(path)
    for _ in range(2):
        call_command("import_inventory", source=str(path), stdout=StringIO())
    call_command("import_sds_links", source=str(path), stdout=StringIO())
    assert Package.objects.count() == 2
    assert StockMovement.objects.count() == 2
    batch = ImportBatch.objects.get()
    assert batch.imported_rows == 2
    assert len(batch.warnings) == 2
    assert Reagent.objects.get(name="Acetone").sds_url == "https://example.test/acetone-sds.pdf"


@pytest.mark.parametrize("raw,expected", [(" 67-64-1 ", "67-64-1"), ("67-64-2", ""), ("?", "")])
def test_cas_validation(raw, expected):
    assert normalize_cas(raw) == expected


@pytest.mark.parametrize(
    "raw,expected", [("2,5 L", (Decimal("2.5"), "l")), ("unknown", (None, ""))]
)
def test_quantity_parsing(raw, expected):
    assert parse_quantity(raw) == expected


def test_roles_are_idempotent():
    from django.contrib.auth.models import Group

    for _ in range(2):
        call_command("setup_roles", stdout=StringIO())
    assert Group.objects.count() == 3
    assert not Group.objects.get(name="Viewer").permissions.filter(codename="use_package").exists()
