from django.urls import path

from . import views

app_name = "inventory"
urlpatterns = [
    path("", views.reagent_list, name="reagent-list"),
    path("overview/", views.overview, name="overview"),
    path("reagents/", views.reagent_list, name="reagent-list-alt"),
    path("reagents/add/", views.reagent_create, name="reagent-create"),
    path("reagents/<uuid:pk>/", views.reagent_detail, name="reagent-detail"),
    path("reagents/<uuid:pk>/quick/", views.reagent_quick_view, name="reagent-quick"),
    path("packages/<uuid:pk>/use/", views.package_use, name="package-use"),
    path("packages/<uuid:pk>/move/", views.package_move, name="package-move"),
    path("packages/<uuid:pk>/write-off/", views.package_write_off, name="package-write-off"),
    path("locations/", views.location_list, name="location-list"),
    path("attention/", views.attention_list, name="attention-list"),
    path("api/v1/reagents/", views.reagent_api_list, name="api-reagent-list"),
]
