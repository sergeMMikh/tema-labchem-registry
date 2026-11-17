from io import BytesIO

import pytest
from django.urls import reverse
from openpyxl import Workbook, load_workbook

from inventory.models import Location, Package, Reagent, Supplier

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def synthetic_export_template(tmp_path, monkeypatch):
    workbook = Workbook()
    workbook.active.title = "Inventário 3.2.22"
    workbook.active.append(["Name", "Formula", "Supplier", "CAS", "Quantity"])
    template = tmp_path / "inventory_template.xlsx"
    workbook.save(template)
    monkeypatch.setattr("inventory.exports.EXPORT_TEMPLATE", template)


def test_export_uses_source_sheets_and_adds_manual_packages(client):
    supplier = Supplier.objects.create(name="Sigma-Aldrich")
    reagent = Reagent.objects.create(
        name="Acetone",
        formula="C3H6O",
        cas_number="67-64-1",
        supplier=supplier,
        sds_url="https://example.test/acetone.pdf",
    )
    lab = Location.objects.create(
        name="Laboratory 3.2.22", code="3.2.22", location_type="laboratory"
    )
    cabinet = Location.objects.create(
        name="Cabinet 1", code="Cabinet 1", location_type="cabinet", parent=lab
    )
    shelf = Location.objects.create(name="A1", code="A1", location_type="shelf", parent=cabinet)
    Package.objects.create(
        reagent=reagent,
        initial_quantity=500,
        current_quantity=450,
        unit="g",
        raw_quantity="500 g",
        location=shelf,
    )

    response = client.get(reverse("inventory:export-inventory"))

    assert response.status_code == 200
    assert response["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook["Registry additions"]
    assert sheet["A1"].value == "Name"
    assert sheet["A2"].value == "Acetone"
    assert sheet["D2"].value == "67-64-1"
    assert sheet["F2"].value == 450
    assert sheet["G2"].value == "Cabinet 1"
    assert sheet["H2"].value == "A1"
    assert sheet["I2"].hyperlink.target == "https://example.test/acetone.pdf"


def test_export_places_imported_package_on_original_sheet_row(client):
    reagent = Reagent.objects.create(name="Acetone", cas_number="67-64-1")
    Package.objects.create(
        reagent=reagent,
        initial_quantity=1,
        current_quantity=1,
        unit="L",
        raw_quantity="1 L",
        source_key="source-hash:Inventário 3.2.22:10",
    )
    response = client.get(reverse("inventory:export-inventory"))
    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook["Inventário 3.2.22"]
    assert sheet[10][0].value == "Acetone"
    assert sheet[10][3].value == "67-64-1"
    assert sheet[10][4].value == "1 L"
