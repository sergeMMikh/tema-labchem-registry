from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from inventory.models import Location, Package, Reagent, StockMovement
from inventory.services import move_package, use_package


class InventoryTestMixin:
    def setUp(self):
        self.lab = Location.objects.create(
            name="Laboratory 3.2.7", code="3.2.7", location_type=Location.Type.LABORATORY
        )
        self.shelf = Location.objects.create(
            name="Shelf 1", code="1", location_type=Location.Type.SHELF, parent=self.lab
        )
        self.other_shelf = Location.objects.create(
            name="Shelf 2", code="2", location_type=Location.Type.SHELF, parent=self.lab
        )
        self.reagent = Reagent.objects.create(
            name="Acetone", formula="C3H6O", cas_number="67-64-1", default_unit="L"
        )
        self.package = Package.objects.create(
            reagent=self.reagent,
            initial_quantity=Decimal("2.5"),
            current_quantity=Decimal("2.5"),
            unit="L",
            location=self.shelf,
        )


class StockServiceTests(InventoryTestMixin, TestCase):
    def test_use_package_is_atomic_and_audited(self):
        use_package(package=self.package, quantity=Decimal("0.5"), reason="Experiment")
        self.package.refresh_from_db()
        self.assertEqual(self.package.current_quantity, Decimal("2.0"))
        movement = StockMovement.objects.get()
        self.assertEqual(movement.quantity_before, Decimal("2.5"))
        self.assertEqual(movement.quantity_after, Decimal("2.0"))

    def test_use_cannot_make_quantity_negative(self):
        with self.assertRaises(ValidationError):
            use_package(package=self.package, quantity=Decimal("3"))
        self.package.refresh_from_db()
        self.assertEqual(self.package.current_quantity, Decimal("2.5"))
        self.assertFalse(StockMovement.objects.exists())

    def test_move_package_is_audited(self):
        move_package(package=self.package, location=self.other_shelf, reason="Reorganization")
        self.package.refresh_from_db()
        self.assertEqual(self.package.location, self.other_shelf)
        self.assertEqual(StockMovement.objects.get().from_location, self.shelf)


class InventoryViewTests(InventoryTestMixin, TestCase):
    def test_search_by_name_and_cas(self):
        for query in ("acet", "67-64-1"):
            response = self.client.get(reverse("inventory:reagent-list"), {"q": query})
            self.assertContains(response, "Acetone")

    def test_quick_view_and_api(self):
        response = self.client.get(reverse("inventory:reagent-quick", args=[self.reagent.pk]))
        self.assertContains(response, "Acetone")
        response = self.client.get(reverse("inventory:api-reagent-list"), {"q": "acetone"})
        self.assertEqual(response.json()["count"], 1)

    def test_anonymous_user_cannot_change_stock(self):
        response = self.client.post(
            reverse("inventory:package-use", args=[self.package.pk]), {"quantity": "0.5"}
        )
        self.assertEqual(response.status_code, 403)
        self.package.refresh_from_db()
        self.assertEqual(self.package.current_quantity, Decimal("2.5"))

    def test_user_with_permission_can_change_stock(self):
        user = User.objects.create_user("chemist", password="test-password")
        user.user_permissions.add(Permission.objects.get(codename="use_package"))
        self.client.force_login(user)
        response = self.client.post(
            reverse("inventory:package-use", args=[self.package.pk]),
            {"quantity": "0.5", "reason": "Test"},
        )
        self.assertRedirects(response, self.reagent.get_absolute_url())

    def test_language_switch_sets_portuguese(self):
        response = self.client.post(
            reverse("set_language"), {"language": "pt", "next": reverse("inventory:overview")}
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("inventory:overview"))
        self.assertContains(response, "Visão geral")
