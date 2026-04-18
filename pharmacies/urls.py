from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views
from .cart_views import CartView, CartClearView, CartPrescriptionView

app_name = "pharmacies"

router = DefaultRouter()
router.register("profiles", views.PharmacyProfileViewSet, basename="profile")
router.register("inventory", views.InventoryViewSet, basename="inventory")

router.register("categories", views.DrugCategoryViewSet, basename="category")
router.register("drugs", views.DrugViewSet, basename="drug")
router.register(
    "suppliers",
    views.SupplierViewSet,
    basename="supplier",
)
router.register(
    "batches",
    views.DrugBatchViewSet,
    basename="batch",
)
router.register(
    "stock-movements",
    views.StockMovementViewSet,
    basename="stock-movement",
)

router.register(
    "payments",
    views.PaymentViewset,
    basename="payment",
)
router.register(
    "orders",
    views.OrderViewSet,
    basename="order",
)
router.register(
    "settlements",
    views.SettlementViewSet,
    basename="settlement",
)
router.register(
    "payment-methods",
    views.PaymentMethodViewSet,
    basename="payment-method",
)

urlpatterns = [
    # Cart endpoints (Redis-based, items expire after 18 hours)
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/clear/", CartClearView.as_view(), name="cart-clear"),
    path(
        "dashboard-statistics/",
        views.DashboardStatisticsView.as_view(),
        name="dashboard-statistics",
    ),
    path(
        "cart/prescription/", CartPrescriptionView.as_view(), name="cart-prescription"
    ),
    path("orders-place-order/", views.PlaceOrderView.as_view(), name="place-order/"),
] + router.urls
