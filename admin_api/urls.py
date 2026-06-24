from importlib import import_module

from rest_framework.routers import DefaultRouter
from django.urls import path

from . import views
from .dashboards import dashboard_urls

app_name = "admin_api"

router = DefaultRouter()

# Resource modules under admin_api/resources/. Each exposes register(router)
# and an optional EXTRA_URLS list. Add an app name here as its file is built.
RESOURCE_MODULES = [
    "accounts",
    "communities",
    "facilities",
    "professionals",
    "patients",
    "pharmacies",
    "partners",
    "chat",
]

_extra = []
for _name in RESOURCE_MODULES:
    _mod = import_module(f"admin_api.resources.{_name}")
    _mod.register(router)
    _extra += list(getattr(_mod, "EXTRA_URLS", []))

urlpatterns = [
    path("me/", views.AdminMeView.as_view(), name="admin_me"),
    *dashboard_urls,
    *_extra,
    *router.urls,
]
