import re
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import (
    Location, Package, StockMovement, canonical_location_name, location_name_key,
)


def preferred_location(locations):
    def rank(location):
        canonical = re.sub(r"\s*-\s*", " - ", canonical_location_name(location.name))
        return (
            location.name != canonical,
            location.name != location.name.title(),
            location.created_at,
            str(location.pk),
        )

    return min(locations, key=rank)


class Command(BaseCommand):
    help = "Merge sibling locations whose names differ only by hyphen spacing or case."

    def handle(self, *args, **options):
        self.merged = 0
        self.moved_packages = 0
        self.moved_movements = 0
        with transaction.atomic():
            groups = defaultdict(list)
            for location in Location.objects.select_related("parent").all():
                groups[(location.parent_id, location.location_type, location_name_key(location.name))].append(location)

            for group in groups.values():
                if len(group) < 2:
                    continue
                survivor = preferred_location(group)
                for duplicate in group:
                    if duplicate.pk != survivor.pk:
                        self.merge(survivor, duplicate)
                canonical = re.sub(r"\s*-\s*", " - ", canonical_location_name(survivor.name))
                if canonical != survivor.name:
                    if Location.objects.filter(parent=survivor.parent, code=canonical[:80]).exclude(pk=survivor.pk).exists():
                        raise CommandError(f"Code collision while renaming {survivor.pk}")
                    survivor.name = canonical[:200]
                    survivor.code = canonical[:80]
                    survivor.save(update_fields=["name", "code", "updated_at"])
        self.stdout.write(
            f"Merged {self.merged} locations; reassigned {self.moved_packages} packages "
            f"and {self.moved_movements} movement references."
        )

    def merge(self, survivor, duplicate, recursive=False):
        if survivor.location_type != duplicate.location_type or (
            not recursive and survivor.parent_id != duplicate.parent_id
        ):
            raise CommandError("Only sibling locations of the same type can be merged")
        for child in list(duplicate.children.all()):
            counterpart = next(
                (
                    sibling
                    for sibling in survivor.children.all()
                    if sibling.location_type == child.location_type
                    and location_name_key(sibling.name) == location_name_key(child.name)
                ),
                None,
            )
            if counterpart is None and survivor.location_type == Location.Type.CABINET:
                survivor_shelf = survivor.collapsed_shelf
                duplicate_shelf = duplicate.collapsed_shelf
                if duplicate_shelf and child.pk == duplicate_shelf.pk:
                    counterpart = survivor_shelf
            if counterpart:
                self.merge(counterpart, child, recursive=True)
            else:
                if Location.objects.filter(parent=survivor, code=child.code).exists():
                    raise CommandError(f"Code collision while moving child {child.pk}")
                child.parent = survivor
                child.save(update_fields=["parent", "updated_at"])
        self.moved_packages += Package.objects.filter(location=duplicate).update(location=survivor)
        self.moved_movements += StockMovement.objects.filter(from_location=duplicate).update(
            from_location=survivor
        )
        self.moved_movements += StockMovement.objects.filter(to_location=duplicate).update(
            to_location=survivor
        )
        duplicate.delete()
        self.merged += 1
