from datetime import timedelta
from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from .exports import build_inventory_export, export_filename
from .forms import MovePackageForm, PackageForm, ReagentForm, UsePackageForm, WriteOffForm
from .models import Location, Package, Reagent
from .search import search_reagents
from .services import move_package, use_package, write_off_package


def _location_parameter(request):
    value = next(
        (request.GET.get(key, "") for key in ("location", "cabinet", "lab") if request.GET.get(key)),
        "",
    )
    if value:
        try:
            UUID(value)
        except ValueError as exc:
            raise Http404("Invalid location identifier") from exc
    return value


def _filtered_reagents(request):
    q = request.GET.get("q", "").strip()
    qs = search_reagents(q)
    status = request.GET.get("status", "")
    location = _location_parameter(request)
    sheet = request.GET.get("sheet", "").strip()[:100]
    matching_packages = Package.objects.all()
    if status:
        matching_packages = matching_packages.filter(status=status)
    if location:
        selected_location = get_object_or_404(Location, pk=location)
        matching_packages = matching_packages.filter(
            location_id__in=selected_location.inventory_location_ids
        )
    if sheet:
        matching_packages = matching_packages.filter(source_key__contains=f":{sheet}:")
    if status or location or sheet:
        qs = qs.filter(packages__in=matching_packages).distinct()
        qs = qs.prefetch_related(None).prefetch_related(
            Prefetch(
                "packages",
                queryset=matching_packages.select_related("location__parent__parent__parent"),
            )
        )
    ordering = request.GET.get("ordering", "name")
    if ordering not in {"name", "-name", "cas_number", "-updated_at"}:
        ordering = "name"
    return qs.order_by(ordering), q, status, location, ordering, sheet


def reagent_list(request):
    qs, q, status, location, ordering, sheet = _filtered_reagents(request)
    try:
        per_page = int(request.GET.get("per_page", 20))
    except ValueError:
        per_page = 20
    paginator = Paginator(qs, min(max(per_page, 10), 100))
    page = paginator.get_page(request.GET.get("page"))
    selected = (
        Location.objects.select_related("parent__parent").filter(pk=location).first()
        if location else None
    )
    selected_lab = selected
    while selected_lab and selected_lab.location_type != Location.Type.LABORATORY:
        selected_lab = selected_lab.parent
    sheet_options = set()
    for source_key, lab_id in Package.objects.exclude(source_key__isnull=True).exclude(
        source_key=""
    ).values_list("source_key", "location__parent__parent_id"):
        if not lab_id or ":" not in source_key:
            continue
        source_sheet, separator, row = source_key.partition(":")[2].rpartition(":")
        if separator and row.isdigit():
            sheet_options.add((lab_id, source_sheet))
    context = {
        "page_obj": page,
        "q": q,
        "selected_status": status,
        "selected_location": location,
        "selected_sheet": sheet,
        "ordering": ordering,
        "labs": Location.objects.filter(
            is_active=True, location_type=Location.Type.LABORATORY
        ).order_by("code"),
        "sheet_options": [
            {"lab_id": lab_id, "name": name}
            for lab_id, name in sorted(sheet_options, key=lambda item: item[1].casefold())
        ],
        "selected_lab": selected_lab,
        "status_choices": Package.Status.choices,
        "last_updated": timezone.now(),
    }
    return render(request, "inventory/reagent_list.html", context)


def export_inventory(request):
    response = HttpResponse(
        build_inventory_export().getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{export_filename()}"'
    return response


def reagent_quick_view(request, pk):
    reagent = get_object_or_404(
        Reagent.objects.select_related("supplier").prefetch_related(
            "packages__location", "packages__movements"
        ),
        pk=pk,
    )
    return render(request, "inventory/_quick_view.html", {"reagent": reagent})


def reagent_detail(request, pk):
    reagent = get_object_or_404(
        Reagent.objects.select_related("supplier", "category").prefetch_related(
            "packages__location", "packages__movements"
        ),
        pk=pk,
    )
    return render(request, "inventory/reagent_detail.html", {"reagent": reagent})


@permission_required("inventory.add_reagent", raise_exception=True)
def reagent_create(request):
    reagent_form = ReagentForm(request.POST or None)
    package_form = PackageForm(request.POST or None, request.FILES or None, prefix="package")
    if request.method == "POST" and reagent_form.is_valid() and package_form.is_valid():
        reagent = reagent_form.save()
        package = package_form.save(commit=False)
        package.reagent = reagent
        package.save()
        messages.success(request, _("Reagent and package added successfully."))
        return redirect(reagent)
    return render(
        request,
        "inventory/reagent_form.html",
        {"reagent_form": reagent_form, "package_form": package_form},
    )


@permission_required("inventory.use_package", raise_exception=True)
def package_use(request, pk):
    package = get_object_or_404(Package, pk=pk)
    form = UsePackageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            use_package(package=package, user=request.user, **form.cleaned_data)
            messages.success(request, _("Quantity updated."))
            return redirect(package.reagent)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "inventory/action_form.html",
        {"form": form, "package": package, "title": _("Use reagent")},
    )


@permission_required("inventory.move_package", raise_exception=True)
def package_move(request, pk):
    package = get_object_or_404(Package, pk=pk)
    form = MovePackageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        move_package(package=package, user=request.user, **form.cleaned_data)
        messages.success(request, _("Package moved."))
        return redirect(package.reagent)
    return render(
        request,
        "inventory/action_form.html",
        {"form": form, "package": package, "title": _("Move package")},
    )


@permission_required("inventory.write_off_package", raise_exception=True)
def package_write_off(request, pk):
    package = get_object_or_404(Package, pk=pk)
    form = WriteOffForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        write_off_package(package=package, user=request.user, **form.cleaned_data)
        messages.success(request, _("Package written off."))
        return redirect(package.reagent)
    return render(
        request,
        "inventory/action_form.html",
        {"form": form, "package": package, "title": _("Write off package"), "danger": True},
    )


def location_list(request):
    roots = Location.objects.filter(parent__isnull=True).prefetch_related(
        "children__children__children"
    )
    selected = None
    if location := _location_parameter(request):
        selected = get_object_or_404(Location, pk=location)
    packages = (
        Package.objects.filter(location_id__in=selected.inventory_location_ids).select_related(
            "reagent"
        )
        if selected
        else Package.objects.none()
    )
    return render(
        request,
        "inventory/location_list.html",
        {"roots": roots, "selected": selected, "packages": packages},
    )


def attention_list(request):
    today = timezone.localdate()
    soon = today + timedelta(days=90)
    packages = (
        Package.objects.select_related("reagent", "location")
        .filter(
            Q(
                status__in=[
                    Package.Status.LOW_STOCK,
                    Package.Status.PENDING,
                    Package.Status.NOT_FOUND,
                ]
            )
            | Q(expires_at__lte=soon)
            | Q(location__isnull=True)
            | Q(reagent__sds_url="")
        )
        .distinct()
    )
    return render(
        request, "inventory/attention.html", {"packages": packages, "today": today, "soon": soon}
    )


def overview(request):
    counts = Package.objects.aggregate(
        total=Count("id"),
        available=Count("id", filter=Q(status=Package.Status.AVAILABLE)),
        written_off=Count("id", filter=Q(status=Package.Status.WRITTEN_OFF)),
    )
    return render(
        request,
        "inventory/overview.html",
        {"counts": counts, "recent": Reagent.objects.order_by("-updated_at")[:8]},
    )


def reagent_api_list(request):
    qs, *_ = _filtered_reagents(request)
    data = [
        {
            "id": str(r.id),
            "name": r.name,
            "formula": r.formula,
            "cas_number": r.cas_number,
            "supplier": r.supplier.name if r.supplier else None,
            "packages": [
                {
                    "id": str(p.id),
                    "status": p.status,
                    "quantity": str(p.current_quantity) if p.current_quantity is not None else None,
                    "unit": p.unit,
                    "location": p.location.full_path if p.location else None,
                }
                for p in r.packages.all()
            ],
        }
        for r in qs[:100]
    ]
    return JsonResponse({"count": qs.count(), "results": data})
