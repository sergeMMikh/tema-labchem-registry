"""Two-step, user-scoped confirmation for saving a photographed reagent."""

import re
import secrets

from django.core.cache import cache
from django.db import transaction

from .models import Location, Package, Reagent, StockMovement, Supplier
from .photo_lookup import inventory_match

PENDING_SECONDS = 3600
PAGE_SIZE = 8


def save_name(fields):
    if fields["name"]:
        return fields["name"][:300]
    if re.fullmatch(r"\d{2,7}-\d{2}-\d", fields["cas"]):
        return f"CAS {fields['cas']}"
    if fields["catalog_number"]:
        return f"Catalog {fields['catalog_number'][:120]}"
    return ""


def start_save(channel, user, fields, source_url=""):
    key = secrets.token_hex(6)
    cache.set(
        f"photo-save:{channel}:{user}:{key}",
        {"fields": fields, "source_url": source_url[:500]},
        timeout=PENDING_SECONDS,
    )
    return key


def pending_save(channel, user, key):
    if not re.fullmatch(r"[0-9a-f]{12}", key):
        return None
    return cache.get(f"photo-save:{channel}:{user}:{key}")


def cancel_save(channel, user, key):
    if pending_save(channel, user, key) is None:
        return False
    cache.delete(f"photo-save:{channel}:{user}:{key}")
    return True


def storage_locations():
    """Offer active leaf locations, including a cabinet with no shelves."""
    locations = Location.objects.filter(is_active=True).exclude(children__is_active=True).distinct()
    return sorted(locations, key=lambda location: location.full_path.casefold())


@transaction.atomic
def save_photo_reagent(channel, user, key, location_id):
    pending = pending_save(channel, user, key)
    if pending is None:
        return None
    location = next((item for item in storage_locations() if str(item.pk) == location_id), None)
    if location is None:
        return None
    lock = f"photo-save-lock:{channel}:{user}:{key}"
    if not cache.add(lock, True, timeout=30):
        return None
    try:
        fields = pending["fields"]
        existing = inventory_match(fields)
        if existing:
            cache.delete(f"photo-save:{channel}:{user}:{key}")
            return existing, False
        name = save_name(fields)
        if not name:
            return None
        manufacturer = fields["manufacturer"][:160]
        supplier = None
        if manufacturer:
            supplier = Supplier.objects.filter(name__iexact=manufacturer).first()
            if supplier is None:
                supplier = Supplier.objects.create(name=manufacturer)
        cas = fields["cas"] if re.fullmatch(r"\d{2,7}-\d{2}-\d", fields["cas"]) else ""
        source = pending["source_url"]
        reagent = Reagent.objects.create(
            name=name[:300], cas_number=cas, catalog_number=fields["catalog_number"][:120],
            supplier=supplier,
            description="Identified from a bottle-label photo; pending laboratory review."
            + (f" Sigma-Aldrich source: {source}" if source else ""),
        )
        package = Package.objects.create(
            reagent=reagent, location=location, status=Package.Status.PENDING,
            notes="Added from a bot label photo. Quantity, lot and label need review.",
        )
        StockMovement.objects.create(
            package=package, movement_type=StockMovement.Type.ADD, to_location=location,
            reason=f"Photo save confirmed in {channel} by {user}; quantity unknown",
        )
        cache.delete(f"photo-save:{channel}:{user}:{key}")
        return reagent, True
    finally:
        cache.delete(lock)
