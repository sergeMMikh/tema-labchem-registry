from django.db.models import Prefetch, Q

from .models import Package, Reagent

AVAILABLE_STATUSES = (Package.Status.AVAILABLE, Package.Status.LOW_STOCK)


def search_reagents(query, *, available_only=False):
    packages = Package.objects.select_related("location__parent__parent__parent")
    if available_only:
        packages = packages.filter(status__in=AVAILABLE_STATUSES)
    results = Reagent.objects.select_related("supplier", "category").prefetch_related(
        Prefetch("packages", queryset=packages)
    )
    if available_only:
        results = results.filter(packages__status__in=AVAILABLE_STATUSES)
    for term in query.strip().split():
        results = results.filter(
            Q(name__icontains=term)
            | Q(formula__icontains=term)
            | Q(cas_number__icontains=term)
            | Q(supplier__name__icontains=term)
            | Q(catalog_number__icontains=term)
            | Q(packages__barcode__icontains=term)
        )
    return results.distinct().order_by("name", "pk")
