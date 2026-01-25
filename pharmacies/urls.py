from rest_framework.routers import DefaultRouter
from . import views

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
urlpatterns = router.urls
