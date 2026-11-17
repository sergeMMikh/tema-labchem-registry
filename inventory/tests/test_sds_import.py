import hashlib
from io import StringIO

import pytest
from django.core.management import call_command
from openpyxl import Workbook

from inventory.models import ImportBatch, Package, Reagent, Supplier

pytestmark = pytest.mark.django_db


def test_sds_sync_separates_products_and_uses_current_batch(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Stock"
    sheet.append(["Name", "Supplier", "CAS", "Link   to SDS (safety data sheet)"])
    sheet.append(["Molybdate", "Supelco", "12054-85-2", "1.01180"])
    sheet["D2"].hyperlink = "https://example.test/supelco.pdf"
    sheet.append(["Molybdate", "Alfa Aesar", "12054-85-2", "Alfa SDS"])
    sheet["D3"].hyperlink = "https://example.test/alfa.pdf"
    path = tmp_path / "products.xlsx"
    workbook.save(path)
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    ImportBatch.objects.create(source_name=path.name, checksum=checksum)
    supplier = Supplier.objects.create(name="Supelco")
    reagent = Reagent.objects.create(name="Molybdate", cas_number="12054-85-2", supplier=supplier)
    historical = Package.objects.create(reagent=reagent, source_key="old:Stock:3")
    packages = [
        Package.objects.create(reagent=reagent, source_key=f"{checksum}:Stock:{row}")
        for row in (2, 3)
    ]
    for _ in range(2):
        call_command("import_sds_links", source=str(path), stdout=StringIO())
    for package in packages:
        package.refresh_from_db()
    historical.refresh_from_db()
    assert packages[0].reagent.sds_url == "https://example.test/supelco.pdf"
    assert packages[1].reagent.sds_url == "https://example.test/alfa.pdf"
    assert packages[1].reagent.supplier.name == "Alfa Aesar"
    assert packages[0].reagent_id != packages[1].reagent_id
    assert historical.reagent_id == reagent.pk
    assert Reagent.objects.count() == 2
    assert Package.objects.count() == 3


def test_primary_sds_fallback_and_invalid_supplier(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Name", "CAS", "Supplier", "Safety Sheet Data (SDS)", "Other SDS"])
    sheet.append(["Molybdate", "12054-85-2", "250 g", "1.01180", ""])
    sheet.append(["Molybdate", "12054-85-2", "Supelco", "1.01180", ""])
    sheet["D3"].hyperlink = "https://example.test/primary.pdf"
    sheet["E3"] = "Alternative"
    sheet["E3"].hyperlink = "https://example.test/alternative.pdf"
    path = tmp_path / "fallback.xlsx"
    workbook.save(path)
    call_command("import_inventory", source=str(path), stdout=StringIO())
    call_command("import_sds_links", source=str(path), stdout=StringIO())
    packages = list(Package.objects.order_by("source_key").select_related("reagent"))
    assert len(packages) == 2
    assert packages[0].reagent.supplier is None
    assert packages[0].reagent.sds_url == "https://example.test/primary.pdf"
    assert packages[1].reagent.supplier.name == "Supelco"
    assert packages[1].reagent.sds_url == "https://example.test/primary.pdf"


def test_inventory_does_not_merge_different_suppliers_by_cas(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Name", "CAS", "Supplier"])
    sheet.append(["Acetone", "67-64-1", "Supplier A"])
    sheet.append(["Acetone", "67-64-1", "Supplier B"])
    path = tmp_path / "suppliers.xlsx"
    workbook.save(path)
    call_command("import_inventory", source=str(path), stdout=StringIO())
    assert Reagent.objects.count() == 2
    assert set(Reagent.objects.values_list("supplier__name", flat=True)) == {
        "Supplier A",
        "Supplier B",
    }


def test_inventory_ignores_quantity_in_supplier_column(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Name", "CAS", "Supplier", "Quantity"])
    sheet.append(["Molybdate", "12054-85-2", "250 g", "1 kg"])
    path = tmp_path / "bad-supplier.xlsx"
    workbook.save(path)
    call_command("import_inventory", source=str(path), stdout=StringIO())
    assert Reagent.objects.get().supplier is None
    assert Supplier.objects.count() == 0


def test_inventory_skips_duplicate_print_tab(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Stock"
    sheet.append(["Name", "CAS", "Quantity"])
    sheet.append(["Molybdate", "12054-85-2", "1 kg"])
    printed = workbook.create_sheet("Vapour extract cabinet_print 26")
    printed.append(["Name", "CAS", "Quantity"])
    printed.append(["Molybdate", "12054-85-2", "1 kg"])
    path = tmp_path / "print-tab.xlsx"
    workbook.save(path)
    call_command("import_inventory", source=str(path), stdout=StringIO())
    assert Package.objects.count() == 1
