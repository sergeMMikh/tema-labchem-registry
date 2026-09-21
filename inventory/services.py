from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from .models import Package, StockMovement


@transaction.atomic
def use_package(*, package, quantity, user=None, reason=""):
    package = Package.objects.select_for_update().get(pk=package.pk)
    if package.status not in {Package.Status.AVAILABLE, Package.Status.LOW_STOCK}:
        raise ValidationError(_("This package is not available for use."))
    if package.current_quantity is None:
        raise ValidationError(_("The package has no structured remaining quantity."))
    quantity = Decimal(quantity)
    if quantity <= 0 or quantity > package.current_quantity:
        raise ValidationError(
            _("The quantity must be positive and cannot exceed the remaining quantity.")
        )
    before = package.current_quantity
    package.current_quantity -= quantity
    if package.current_quantity == 0:
        package.status = Package.Status.WRITTEN_OFF
    elif (
        package.initial_quantity
        and package.current_quantity <= package.initial_quantity * Decimal("0.2")
    ):
        package.status = Package.Status.LOW_STOCK
    package.save(update_fields=["current_quantity", "status", "updated_at"])
    return StockMovement.objects.create(
        package=package,
        movement_type=StockMovement.Type.USE,
        quantity_before=before,
        quantity_delta=-quantity,
        quantity_after=package.current_quantity,
        from_location=package.location,
        to_location=package.location,
        performed_by=user,
        reason=reason,
    )


@transaction.atomic
def move_package(*, package, location, user=None, reason=""):
    package = Package.objects.select_for_update().get(pk=package.pk)
    previous = package.location
    package.location = location
    package.save(update_fields=["location", "updated_at"])
    return StockMovement.objects.create(
        package=package,
        movement_type=StockMovement.Type.MOVE,
        quantity_before=package.current_quantity,
        quantity_after=package.current_quantity,
        from_location=previous,
        to_location=location,
        performed_by=user,
        reason=reason,
    )


@transaction.atomic
def write_off_package(*, package, user=None, reason=""):
    package = Package.objects.select_for_update().get(pk=package.pk)
    before = package.current_quantity
    package.status = Package.Status.WRITTEN_OFF
    package.current_quantity = Decimal("0") if package.current_quantity is not None else None
    package.save(update_fields=["status", "current_quantity", "updated_at"])
    return StockMovement.objects.create(
        package=package,
        movement_type=StockMovement.Type.WRITE_OFF,
        quantity_before=before,
        quantity_delta=-before if before is not None else None,
        quantity_after=package.current_quantity,
        from_location=package.location,
        to_location=package.location,
        performed_by=user,
        reason=reason,
    )
