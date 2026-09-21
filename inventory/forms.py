from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Location, Package, Reagent


class ReagentForm(forms.ModelForm):
    class Meta:
        model = Reagent
        fields = [
            "name",
            "formula",
            "cas_number",
            "supplier",
            "catalog_number",
            "category",
            "physical_state",
            "default_unit",
            "sds_url",
            "description",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class PackageForm(forms.ModelForm):
    class Meta:
        model = Package
        fields = [
            "lot_number",
            "initial_quantity",
            "current_quantity",
            "unit",
            "concentration",
            "expires_at",
            "location",
            "responsible_user",
            "status",
            "label_photo",
            "notes",
        ]
        widgets = {
            "expires_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        initial = cleaned.get("initial_quantity")
        current = cleaned.get("current_quantity")
        if initial is not None and current is not None and current > initial:
            self.add_error(
                "current_quantity", _("Current quantity cannot exceed initial quantity.")
            )
        return cleaned


class UsePackageForm(forms.Form):
    quantity = forms.DecimalField(
        min_value=Decimal("0.001"), max_digits=12, decimal_places=3, label=_("Quantity used")
    )
    reason = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), label=_("Reason")
    )


class MovePackageForm(forms.Form):
    location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True), label=_("New location")
    )
    reason = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), label=_("Reason")
    )


class WriteOffForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label=_("Reason"))
