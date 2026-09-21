from django.contrib import admin

from .models import Category, ImportBatch, Location, Package, Reagent, StockMovement, Supplier


class PackageInline(admin.TabularInline):
    model = Package
    extra = 0
    fields = (
        "barcode",
        "lot_number",
        "current_quantity",
        "unit",
        "location",
        "status",
        "expires_at",
    )
    readonly_fields = ("barcode",)


@admin.register(Reagent)
class ReagentAdmin(admin.ModelAdmin):
    list_display = ("name", "formula", "cas_number", "supplier", "physical_state", "updated_at")
    search_fields = ("name", "formula", "cas_number", "catalog_number", "supplier__name")
    list_filter = ("physical_state", "category", "supplier")
    readonly_fields = ("created_at", "updated_at", "source_sheet", "source_row")
    inlines = [PackageInline]


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("reagent", "barcode", "display_quantity", "location", "status", "expires_at")
    list_filter = ("status", "unit", "expires_at")
    search_fields = ("reagent__name", "reagent__cas_number", "barcode", "lot_number", "source_key")
    readonly_fields = ("created_at", "updated_at", "source_key", "raw_quantity")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "location_type", "parent", "is_active")
    list_filter = ("location_type", "is_active")
    search_fields = ("name", "code")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("movement_type", "package", "performed_by", "created_at")
    list_filter = ("movement_type", "created_at")
    search_fields = ("package__reagent__name", "reason")
    readonly_fields = [field.name for field in StockMovement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Supplier)
admin.site.register(Category)
admin.site.register(ImportBatch)
