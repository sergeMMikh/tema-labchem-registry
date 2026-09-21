from django.db.models import Q
from django.utils import timezone

from .models import Package


def navigation_counts(request):
    today = timezone.localdate()
    attention = Package.objects.filter(
        Q(status__in=[Package.Status.LOW_STOCK, Package.Status.PENDING, Package.Status.NOT_FOUND])
        | Q(expires_at__lte=today)
    ).count()
    return {"attention_count": attention}
