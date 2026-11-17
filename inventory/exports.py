from datetime import datetime
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.utils import get_column_letter

from .management.commands.import_inventory import canonical_header
from .models import Package

EXPORT_TEMPLATE = Path(__file__).resolve().parent / "data" / "inventory_export_template.xlsx"


def _package_row(package):
    reagent = package.reagent
    location = package.location
    cabinet = location.parent if location and location.parent_id else location
    shelf = location if location and location.location_type == "shelf" else None
    if shelf:
        cabinet = shelf.parent
    return {
        "name": reagent.name,
        "formula": reagent.formula,
        "supplier": reagent.supplier.name if reagent.supplier_id else "",
        "cas": reagent.cas_number,
        "quantity": package.raw_quantity
        or _format_quantity(package.initial_quantity, package.unit),
        "remaining": package.current_quantity,
        "storage": cabinet.name if cabinet else "",
        "shelf": (
            ""
            if shelf and shelf.name.casefold() == "unspecified shelf"
            else shelf.name
            if shelf
            else ""
        ),
        "sds": reagent.sds_url,
        "reference": reagent.catalog_number,
        "expiry": package.expires_at,
        "notes": package.notes,
        "physical_state": reagent.get_physical_state_display(),
        "responsible": str(package.responsible_user) if package.responsible_user_id else "",
        "status": package.get_status_display(),
    }


def _format_quantity(quantity, unit):
    if quantity is None:
        return ""
    return f"{quantity:g} {unit}".strip()


def _safe_cell_value(value):
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return f"'{value}"
    return value


def build_inventory_export():
    workbook = load_workbook(EXPORT_TEMPLATE)
    row_headers = {}
    for sheet in workbook.worksheets:
        headers = {}
        populated = {}
        for cell in sheet._cells.values():
            if cell.value is not None:
                populated.setdefault(cell.row, {})[cell.column] = cell.value
        for row_number in range(1, sheet.max_row + 1):
            mapped = {
                canonical_header(value): column
                for column, value in populated.get(row_number, {}).items()
                if canonical_header(value)
            }
            if "name" in mapped and len(mapped) >= 2:
                headers = mapped
            if headers:
                row_headers[sheet.title, row_number] = headers

    additions = []
    packages = Package.objects.select_related(
        "reagent__supplier", "location__parent", "responsible_user"
    ).order_by("source_key", "reagent__name", "created_at")
    for package in packages:
        parts = (package.source_key or "").split(":")
        row_number = int(parts[-1]) if len(parts) > 2 and parts[-1].isdigit() else None
        sheet_title = ":".join(parts[1:-1]) if row_number else ""
        headers = row_headers.get((sheet_title, row_number))
        values = _package_row(package)
        if not headers:
            additions.append(values)
            continue
        sheet = workbook[sheet_title]
        for field, value in values.items():
            column = headers.get(field)
            if not column:
                continue
            cell = sheet.cell(row_number, column)
            if isinstance(cell, MergedCell):
                continue
            cell.value = _safe_cell_value(value)
            if field == "sds" and value:
                cell.hyperlink = value
                cell.style = "Hyperlink"

    if additions:
        sheet = workbook.create_sheet("Registry additions")
        headers = [
            "Name",
            "Formula",
            "Supplier",
            "CAS",
            "Quantity",
            "Estimated quantity left",
            "Storage",
            "Shelf",
            "Link to SDS",
            "Reference",
            "Expiry",
            "Notes",
            "Status",
        ]
        sheet.append(headers)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(additions) + 1}"
        for values in additions:
            sheet.append(
                [
                    _safe_cell_value(values[key])
                    for key in (
                        "name",
                        "formula",
                        "supplier",
                        "cas",
                        "quantity",
                        "remaining",
                        "storage",
                        "shelf",
                        "sds",
                        "reference",
                        "expiry",
                        "notes",
                        "status",
                    )
                ]
            )
            if values["sds"]:
                cell = sheet.cell(sheet.max_row, 9)
                cell.hyperlink = values["sds"]
                cell.style = "Hyperlink"

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def export_filename():
    return f"TEMA_inventory_{datetime.now():%Y%m%d_%H%M}.xlsx"
