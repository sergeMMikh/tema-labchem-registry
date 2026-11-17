import hashlib
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from openpyxl import load_workbook

from inventory.management.commands.import_inventory import (
    canonical_header,
    clean,
    normalize_cas,
    parse_quantity,
)
from inventory.models import ImportBatch, Package, Reagent, Supplier


class Command(BaseCommand):
    help = "Import SDS hyperlink targets embedded in the source XLSX workbook."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="Path to the XLSX workbook")

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["source"])
        if not path.exists():
            raise CommandError(f"Workbook not found: {path}")

        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if not ImportBatch.objects.filter(checksum=checksum).exists():
            raise CommandError(
                "Import this workbook with import_inventory before syncing SDS links."
            )

        workbook = load_workbook(path, read_only=False, data_only=True)
        updated_reagents = set()
        links_found = unmatched = split_packages = 0
        source_rows = []
        label_targets = defaultdict(set)

        for sheet in workbook.worksheets:
            rows = defaultdict(dict)
            for cell in sheet._cells.values():
                rows[cell.row][cell.column] = cell

            headers = {}
            for row_number in sorted(rows):
                cells = rows[row_number]
                mapped = {
                    canonical_header(cell.value): column
                    for column, cell in cells.items()
                    if canonical_header(cell.value)
                }
                if "name" in mapped and len(mapped) >= 2:
                    headers = mapped
                    # Preserve primary and alternative SDS columns in workbook order.
                    sds_columns = [
                        column
                        for column, cell in sorted(cells.items())
                        if canonical_header(cell.value) == "sds"
                    ]
                    continue
                if not headers or not headers.get("sds"):
                    continue
                links = []
                labels = []
                record = {
                    key: clean(cells[column].value) if column in cells else ""
                    for key, column in headers.items()
                }
                identity = normalize_cas(record.get("cas", "")) or record.get("name", "").casefold()
                for column in sds_columns:
                    cell = cells.get(column)
                    if cell is None:
                        continue
                    label = clean(cell.value)
                    target = cell.hyperlink.target if cell.hyperlink else label
                    if target and target.startswith(("http://", "https://")):
                        links.append(target)
                        if label:
                            label_targets[identity, label].add(target)
                    elif label:
                        labels.append(label)
                source_rows.append((sheet.title, row_number, record, identity, links, labels))

        for sheet_title, row_number, record, identity, links, labels in source_rows:
            target = next(iter(links), "")
            if not target:
                # A repeated product reference may have a hyperlink on another row.
                # Only use an exact label with a single unambiguous target.
                target = next(
                    (
                        next(iter(label_targets[identity, label]))
                        for label in labels
                        if len(label_targets[identity, label]) == 1
                        and len(label) >= 4
                        and any(char.isdigit() for char in label)
                    ),
                    "",
                )
            if not target:
                continue
            links_found += 1
            package = (
                Package.objects.select_related("reagent")
                .filter(source_key=f"{checksum}:{sheet_title}:{row_number}")
                .first()
            )
            if not package:
                unmatched += 1
                continue
            reagent = package.reagent
            supplier = reagent.supplier
            if "supplier" in record:
                name = record["supplier"]
                # A quantity in the manufacturer's column is a source error.
                if parse_quantity(name)[0] is not None:
                    name = ""
                supplier = Supplier.objects.get_or_create(name=name[:200])[0] if name else None
            supplier_id = supplier.pk if supplier else None
            if (
                reagent.supplier
                and parse_quantity(reagent.supplier.name)[0] is not None
                and reagent.source_sheet == sheet_title
                and reagent.source_row == row_number
            ):
                # Retain the existing card URL when correcting a source-column error.
                reagent.supplier = supplier
                reagent.save(update_fields=["supplier", "updated_at"])
            if reagent.supplier_id != supplier_id or (
                reagent.sds_url and reagent.sds_url != target
            ):
                # CAS identifies the chemical, not the supplier's product/SDS.
                lookup = {"cas_number": reagent.cas_number, "supplier": supplier, "sds_url": target}
                if not reagent.cas_number:
                    lookup["name"] = record.get("name") or reagent.name
                product = Reagent.objects.filter(**lookup).first()
                if product is None:
                    fields = {
                        field.name: getattr(reagent, field.name)
                        for field in Reagent._meta.fields
                        if field.name not in {"id", "created_at", "updated_at"}
                    }
                    fields.update(
                        name=record.get("name") or reagent.name,
                        supplier=supplier,
                        sds_url=target,
                        source_sheet=sheet_title,
                        source_row=row_number,
                    )
                    product = Reagent.objects.create(**fields)
                package.reagent = product
                package.save(update_fields=["reagent", "updated_at"])
                reagent = product
                split_packages += 1
            if reagent.sds_url != target:
                reagent.sds_url = target
                reagent.save(update_fields=["sds_url", "updated_at"])
            updated_reagents.add(reagent.pk)

        self.stdout.write(
            self.style.SUCCESS(
                f"Found {links_found} SDS hyperlinks; updated {len(updated_reagents)} reagents; "
                f"{unmatched} source rows were not present in the imported inventory; "
                f"{split_packages} packages assigned to their supplier's SDS."
            )
        )
