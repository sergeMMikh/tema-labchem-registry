from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the Viewer, Laboratory user and Administrator groups."

    def handle(self, *args, **options):
        definitions = {
            "Viewer": ["view_reagent", "view_package", "view_location", "view_stockmovement"],
            "Laboratory user": [
                "view_reagent",
                "view_package",
                "view_location",
                "view_stockmovement",
                "add_reagent",
                "add_package",
                "use_package",
                "move_package",
            ],
            "Administrator": None,
        }
        inventory_permissions = Permission.objects.filter(content_type__app_label="inventory")
        for name, codes in definitions.items():
            group, _ = Group.objects.get_or_create(name=name)
            permissions = (
                inventory_permissions
                if codes is None
                else inventory_permissions.filter(codename__in=codes)
            )
            group.permissions.set(permissions)
            self.stdout.write(f"{name}: {permissions.count()} permissions")
        self.stdout.write(self.style.SUCCESS("Roles configured."))
