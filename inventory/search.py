import re
import unicodedata

from django.db.models import Prefetch, Q

from .models import Package, Reagent

AVAILABLE_STATUSES = (Package.Status.AVAILABLE, Package.Status.LOW_STOCK)

# Explicit chemical equivalents, not automatic translation or substring expansion.
# Include names as well as CAS because imported records may have no CAS value.
CHEMICAL_SYNONYMS = (
    (
        "7697-37-2",
        ("nitric acid", "ácido nítrico", "ácido nitrico", "acido nítrico", "acido nitrico"),
    ),
    ("67-64-1", ("acetone", "acetona")),
)


def normalize_name(value):
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value.casefold())
        if not unicodedata.combining(char)
    )


def synonym_filter(query):
    """Resolve known complete names; leave unrelated partial searches unchanged."""
    normalized = normalize_name(query)
    for cas, aliases in CHEMICAL_SYNONYMS:
        for alias in sorted({normalize_name(a) for a in aliases}, key=len, reverse=True):
            match = re.search(
                r"(?<!\w)" + r"\s+".join(map(re.escape, alias.split())) + r"(?!\w)", normalized
            )
            if match:
                names = "|".join(r"\s+".join(map(re.escape, a.split())) for a in aliases)
                # Portable across SQLite and PostgreSQL, unlike backend-specific word boundaries.
                pattern = rf"(^|[^\w])({names})([^\w]|$)"
                condition = Q(name__iregex=pattern) | Q(cas_number=cas)
                remaining = normalized[: match.start()] + " " + normalized[match.end() :]
                return condition, remaining
    return Q(), query


def search_reagents(query, *, available_only=False):
    packages = Package.objects.select_related("location__parent__parent__parent")
    if available_only:
        packages = packages.filter(status__in=AVAILABLE_STATUSES)
    results = Reagent.objects.select_related("supplier", "category").prefetch_related(
        Prefetch("packages", queryset=packages)
    )
    if available_only:
        results = results.filter(packages__status__in=AVAILABLE_STATUSES)
    condition, remaining = synonym_filter(query)
    results = results.filter(condition)
    for term in remaining.strip().split():
        results = results.filter(
            Q(name__icontains=term)
            | Q(formula__icontains=term)
            | Q(cas_number__icontains=term)
            | Q(supplier__name__icontains=term)
            | Q(catalog_number__icontains=term)
            | Q(packages__barcode__icontains=term)
        )
    return results.distinct().order_by("name", "pk")
