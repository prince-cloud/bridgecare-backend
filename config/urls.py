from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from django.conf.urls.static import static
from communities.views import (
    CertificateVerifyView,
    PublicCertificateDownloadView,
    AcceptStaffInviteView,
)


urlpatterns = [
    path("crt/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("pages.urls")),
    path("auth/", include("accounts.urls")),
    path("communities/<uuid:organization_id>/", include("communities.urls")),
    # NOTE: the frontend reaches the backend through a proxy that strips the
    # leading /api (vite rewrite + nginx `location /api/`), so backend routes
    # live at the root. These must NOT carry an `api/` prefix or the proxied
    # request (/verify/certificate/...) never matches → "Invalid Certificate".
    path(
        "verify/certificate/<str:verification_code>/",
        CertificateVerifyView.as_view(),
        name="certificate-verify",
    ),
    path(
        "verify/certificate/<str:verification_code>/download/",
        PublicCertificateDownloadView.as_view(),
        name="certificate-download",
    ),
    path(
        "accept-staff-invite/",
        AcceptStaffInviteView.as_view(),
        name="accept-staff-invite",
    ),
    path("facilities/", include("facilities.urls")),
    path("professionals/", include("professionals.urls")),
    path("partners/", include("partners.urls")),
    path("pharmacies/", include("pharmacies.urls")),
    path("patients/", include("patients.urls")),
    path("chat/", include("chat.urls")),
    path("appapi/v1/", include("public_api.urls")),
    path("admin-api/", include("admin_api.urls")),
    path("crt-schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "crt-docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "crt-redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

urlpatterns = (
    urlpatterns
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
)


if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
