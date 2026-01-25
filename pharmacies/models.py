from django.db import models
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid


class PharmacyProfile(models.Model):
    """
    Specific profile for Pharmacy platform users
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="pharmacy_profile",
    )

    # Pharmacy details
    pharmacy_name = models.CharField(max_length=200)
    pharmacy_license = models.CharField(max_length=100, unique=True)

    # Location
    address = models.TextField()
    district = models.CharField(max_length=100, null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
    )

    # Contact information
    phone_number = PhoneNumberField()
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)

    # Services and capabilities
    delivery_available = models.BooleanField(default=False)
    delivery_radius = models.IntegerField(default=0)

    # Staff information
    pharmacist_license = models.CharField(max_length=100, blank=True, null=True)
    license_expiry_date = models.DateField(blank=True, null=True)

    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pharmacy_profiles"
        verbose_name = "Pharmacy Profile"
        verbose_name_plural = "Pharmacy Profiles"

    def __str__(self):
        return f"{self.user.email} - {self.pharmacy_name}"


class DrugCategory(models.Model):
    pharmacy = models.ForeignKey(
        PharmacyProfile,
        on_delete=models.CASCADE,
        related_name="drug_categories",
    )
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "drug_categories"
        verbose_name = "Drug Category"
        verbose_name_plural = "Drug Categories"

    def __str__(self):
        return self.name


class DrugUnit(models.TextChoices):
    TABLET = "tablet", "Tablet"
    CAPSULE = "capsule", "Capsule"
    BLISTER = "blister", "Blister pack"
    BOX = "box", "Box"
    BOTTLE = "bottle", "Bottle"
    VIAL = "vial", "Vial"
    AMPOULE = "ampoule", "Ampoule"
    TUBE = "tube", "Tube"
    SACHET = "sachet", "Sachet"
    INHALER = "inhaler", "Inhaler"
    SYRINGE = "syringe", "Prefilled syringe"
    PEN = "pen", "Injection pen"


class Drug(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ImageField(upload_to="drugs/", blank=True, null=True)

    pharmacy = models.ForeignKey(
        PharmacyProfile,
        on_delete=models.CASCADE,
        related_name="drugs",
    )

    name = models.CharField(max_length=100)
    category = models.ForeignKey(
        DrugCategory,
        on_delete=models.PROTECT,
        related_name="drugs",
    )

    base_unit = models.CharField(
        max_length=20,
        choices=DrugUnit.choices,
        help_text="Smallest measurable unit (e.g. tablet, ml)",
    )

    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Price per base unit"
    )

    low_stock_threshold = models.IntegerField(default=10)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "drugs"
        unique_together = ("pharmacy", "name")
        indexes = [
            models.Index(fields=["pharmacy", "name"]),
        ]

    def __str__(self):
        return self.name


class DrugSupplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pharmacy = models.ForeignKey(
        PharmacyProfile,
        on_delete=models.CASCADE,
        related_name="suppliers",
    )
    name = models.CharField(max_length=100)
    phone_number = PhoneNumberField()
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "drug_suppliers"
        verbose_name = "Drug Supplier"
        verbose_name_plural = "Drug Suppliers"


class DrugBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pharmacy = models.ForeignKey(
        PharmacyProfile,
        on_delete=models.CASCADE,
        related_name="batches",
    )
    drug = models.ForeignKey(
        Drug,
        on_delete=models.CASCADE,
        related_name="batches",
    )

    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()
    supplier = models.ForeignKey(
        DrugSupplier,
        on_delete=models.PROTECT,
        related_name="batches",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "drug_batches"
        unique_together = ("drug", "batch_number")
        indexes = [
            models.Index(fields=["expiry_date"]),
        ]

    def __str__(self):
        return f"{self.drug.name} - {self.batch_number}"


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        RESTOCK = "restock", "Restock"
        SALE = "sale", "Sale"
        RETURN = "return", "Return"
        ADJUSTMENT = "adjustment", "Adjustment"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pharmacy = models.ForeignKey(
        PharmacyProfile,
        on_delete=models.CASCADE,
        related_name="movements",
    )

    drug = models.ForeignKey(
        Drug,
        on_delete=models.CASCADE,
        related_name="movements",
    )

    batch = models.ForeignKey(
        DrugBatch,
        on_delete=models.PROTECT,
        related_name="movements",
    )

    quantity = models.IntegerField(
        help_text="Positive for stock-in, negative for stock-out"
    )

    reason = models.CharField(
        max_length=20,
        choices=Reason.choices,
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stock_movements"
        indexes = [
            models.Index(fields=["drug", "created_at"]),
            models.Index(fields=["batch"]),
        ]

        constraints = [
            models.CheckConstraint(
                check=~models.Q(quantity=0),
                name="quantity_not_zero",
            ),
        ]


# class DrugStock(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     drug = models.ForeignKey(
#         Drug,
#         on_delete=models.CASCADE,
#         related_name="stocks",
#     )
#     quantity = models.IntegerField(default=0)
#     batch_number = models.CharField(max_length=100)
#     batch_expiry_date = models.DateField()

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = "drug_stocks"
#         verbose_name = "Drug Stock"
#         verbose_name_plural = "Drug Stocks"

#     def __str__(self):
#         return f"{self.drug.name} - {self.quantity} {self.unit}"
