import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Location(TimeStampedModel):
    class Type(models.TextChoices):
        BUILDING = "building", _("Building")
        LABORATORY = "laboratory", _("Laboratory")
        CABINET = "cabinet", _("Cabinet / storage unit")
        SHELF = "shelf", _("Shelf")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=80, blank=True)
    location_type = models.CharField(max_length=20, choices=Type.choices)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "code"], name="unique_location_code_per_parent"
            )
        ]

    def __str__(self):
        return self.full_path

    @property
    def collapsed_shelf(self):
        """Hide a sole placeholder or a shelf repeating its cabinet's name."""
        if self.location_type != self.Type.CABINET:
            return None
        children = list(self.children.all())
        if len(children) == 1:
            child = children[0]
            if child.location_type == self.Type.SHELF and " ".join(
                child.name.split()
            ).casefold() in {"unspecified shelf", " ".join(self.name.split()).casefold()}:
                return child
        return None

    @property
    def inventory_location_ids(self):
        shelf = self.collapsed_shelf
        return [self.pk, shelf.pk] if shelf else [self.pk]

    @property
    def full_path(self):
        nodes, current = [], self
        while current:
            if (
                current.location_type == self.Type.SHELF
                and current.parent_id
                and current.parent.collapsed_shelf is not None
            ):
                current = current.parent
                continue
            nodes.append(current.code or current.name)
            current = current.parent
        return " · ".join(reversed(nodes))


cas_validator = RegexValidator(r"^\d{2,7}-\d{2}-\d$", _("Enter a CAS number such as 67-64-1."))


class Reagent(TimeStampedModel):
    class PhysicalState(models.TextChoices):
        SOLID = "solid", _("Solid")
        LIQUID = "liquid", _("Liquid")
        GAS = "gas", _("Gas")
        MIXTURE = "mixture", _("Mixture")
        OTHER = "other", _("Other")
        UNKNOWN = "unknown", _("Unknown")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=300)
    formula = models.CharField(max_length=200, blank=True)
    cas_number = models.CharField(max_length=20, blank=True, validators=[cas_validator])
    description = models.TextField(blank=True)
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name="reagents"
    )
    catalog_number = models.CharField(max_length=120, blank=True)
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="reagents"
    )
    physical_state = models.CharField(
        max_length=20, choices=PhysicalState.choices, default=PhysicalState.UNKNOWN
    )
    default_unit = models.CharField(max_length=20, blank=True)
    sds_url = models.URLField(blank=True, max_length=500)
    source_sheet = models.CharField(max_length=200, blank=True)
    source_row = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"]), models.Index(fields=["cas_number"])]
        permissions = [("view_attention", "Can view items requiring attention")]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("inventory:reagent-detail", args=[self.pk])

    @property
    def total_quantity(self):
        return self.packages.filter(status=Package.Status.AVAILABLE).aggregate(
            total=models.Sum("current_quantity")
        )["total"] or Decimal("0")


class Package(TimeStampedModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", _("In stock")
        LOW_STOCK = "low_stock", _("Low stock")
        RESERVED = "reserved", _("Reserved")
        PENDING = "pending_review", _("Pending review")
        NOT_FOUND = "not_found", _("Not found")
        WRITTEN_OFF = "written_off", _("Written off")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reagent = models.ForeignKey(Reagent, on_delete=models.PROTECT, related_name="packages")
    barcode = models.CharField(max_length=120, blank=True, unique=True, null=True)
    lot_number = models.CharField(max_length=120, blank=True)
    initial_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    current_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    unit = models.CharField(max_length=20, blank=True)
    concentration = models.CharField(max_length=120, blank=True)
    received_at = models.DateField(null=True, blank=True)
    opened_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="packages"
    )
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responsible_packages",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    label_photo = models.ImageField(upload_to="labels/%Y/%m/", blank=True)
    notes = models.TextField(blank=True)
    source_key = models.CharField(max_length=300, blank=True, unique=True, null=True)
    raw_quantity = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["reagent__name", "created_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["expires_at"])]
        permissions = [
            ("use_package", "Can use package stock"),
            ("move_package", "Can move packages"),
            ("write_off_package", "Can write off packages"),
        ]

    def __str__(self):
        return f"{self.reagent} — {self.barcode or str(self.pk)[:8]}"

    @property
    def display_quantity(self):
        if self.current_quantity is None:
            return self.raw_quantity or "—"
        return f"{self.current_quantity:g} {self.unit}".strip()


class StockMovement(models.Model):
    class Type(models.TextChoices):
        IMPORT = "import", _("Import")
        ADD = "add", _("Addition")
        USE = "use", _("Use")
        ADJUST = "adjust", _("Adjustment")
        MOVE = "move", _("Move")
        WRITE_OFF = "write_off", _("Write off")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(Package, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=Type.choices)
    quantity_before = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    quantity_delta = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    from_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="movements_from"
    )
    to_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="movements_to"
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["package", "created_at"])]

    def __str__(self):
        return f"{self.get_movement_type_display()} — {self.package}"


class ImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_name = models.CharField(max_length=300)
    checksum = models.CharField(max_length=64, unique=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    imported_rows = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    warnings = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.source_name} ({self.imported_at:%Y-%m-%d})"
