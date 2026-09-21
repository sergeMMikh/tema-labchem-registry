import hashlib
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from openpyxl import load_workbook

from inventory.management.commands.import_inventory import canonical_header
from inventory.models import ImportBatch, Package


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
        links_found = unmatched = 0

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
                    continue
                sds_column = headers.get("sds")
                if not sds_column:
                    continue
                cell = cells.get(sds_column)
                target = cell.hyperlink.target if cell and cell.hyperlink else ""
                if not target or not target.startswith(("http://", "https://")):
                    continue
                links_found += 1
                package = (
                    Package.objects.select_related("reagent")
                    .filter(source_key__endswith=f":{sheet.title}:{row_number}")
                    .first()
                )
                if not package:
                    unmatched += 1
                    continue
                reagent = package.reagent
                if reagent.sds_url != target:
                    reagent.sds_url = target
                    reagent.save(update_fields=["sds_url", "updated_at"])
                updated_reagents.add(reagent.pk)

        self.stdout.write(
            self.style.SUCCESS(
                f"Found {links_found} SDS hyperlinks; updated {len(updated_reagents)} reagents; "
                f"{unmatched} source rows were not present in the imported inventory."
            )
        )
