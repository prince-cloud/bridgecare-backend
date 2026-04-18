from django.db import models
from accounts.models import Address, CustomUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid
from api.paystack import PayStack
from helpers.functions import generate_reference


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
    contact_person = models.CharField(max_length=100)
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
                condition=~models.Q(quantity=0),
                name="quantity_not_zero",
            ),
        ]

    def __str__(self):
        return f"{self.drug.name} - {self.reason} ({self.quantity})"


class Order(models.Model):
    """
    Order model for completed drug purchases
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        DELIVERING = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    class DeliveryMethod(models.TextChoices):
        DELIVERY = "delivery", "Delivery"
        PICKUP = "pickup", "Pickup"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(
        max_length=50, unique=True, help_text="Unique order number"
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="orders",
    )

    # Order details
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    # Pricing
    subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Subtotal before delivery"
    )
    delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Delivery fee if applicable",
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Total amount including delivery"
    )

    # Delivery information
    delivery_method = models.CharField(
        max_length=20,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.PICKUP,
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.CASCADE,
        related_name="orders",
        null=True,
        blank=True,
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "orders"
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["order_number"]),
        ]

    def __str__(self):
        return f"Order {self.order_number} - {self.user.email}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            from helpers.functions import generate_reference_id

            self.order_number = f"ORD-{generate_reference_id(8).upper()}"
        super().save(*args, **kwargs)


class PharmacyOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready for Pickup"
        DELIVERING = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pharmacy = models.ForeignKey(
        PharmacyProfile,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="pharmacy_orders",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pharmacy_orders"
        verbose_name = "Pharmacy Order"
        verbose_name_plural = "Pharmacy Orders"


class OrderItem(models.Model):
    """
    Individual items in an order
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    drug = models.ForeignKey(
        Drug,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per unit at time of order",
    )
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Total price for this item"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_items"
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
        indexes = [
            models.Index(fields=["order"]),
        ]

    def __str__(self):
        return f"{self.drug.name} x{self.quantity} in Order {self.order.order_number}"

    def save(self, *args, **kwargs):
        # Auto-calculate total_price
        if not self.total_price:
            self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class Payment(models.Model):
    class Status(models.TextChoices):
        INITIATED = "INITIATED"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"

    user: CustomUser = models.ForeignKey(
        CustomUser,
        related_name="payments",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    order = models.OneToOneField(
        Order,
        related_name="payment",
        on_delete=models.CASCADE,
    )
    amount = models.DecimalField(decimal_places=2, max_digits=50)
    reference = models.CharField(max_length=200)

    # paystack details
    payment_response = models.TextField(blank=True, null=True)
    authorization_url = models.CharField(max_length=200, blank=True, null=True)

    status = models.CharField(
        choices=Status.choices,
        default=Status.INITIATED,
        max_length=30,
    )

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date_created",)

    def __str__(self) -> str:
        return f"{self.user} - {self.amount}"

    def save(self, *args, **kwargs):
        while not self.reference:
            ref = generate_reference(length=50)
            object_with_similar_ref = Payment.objects.filter(reference=ref).first()
            if not object_with_similar_ref:
                self.reference = ref
        super().save(*args, **kwargs)

    def amount_value(self):
        paystack_amount = float(float(1.9 / 100) * float(self.amount)) + float(
            self.amount
        )
        return int(paystack_amount * 100)
        # return int(self.total_amount * 100)

    def verify_payment(self):
        paystack = PayStack()
        status, result = paystack.verify_payment(self.reference, self.amount)
        if status:
            self.payment_response = result
            if result["amount"] / 100 == self.amount:
                self.status = Payment.Status.COMPLETED
                self.save()
                return True
            self.save()
            return False
        return False


class PaymentMethod(models.Model):
    class PaymentMethodType(models.TextChoices):
        BANK_TRANSFER = "Bank Transfer"
        MOBILE_MONEY = "Mobile Money"

    user = models.ForeignKey(
        CustomUser,
        related_name="payment_methods",
        on_delete=models.SET_NULL,
        null=True,
    )

    payment_method_type = models.CharField(
        choices=PaymentMethodType.choices, max_length=20
    )
    account_number = models.CharField(max_length=100)
    account_name = models.CharField(max_length=100)
    provider = models.CharField(
        max_length=100,
        help_text="Bank Name or Network Provider",
    )
    provider_code = models.CharField(max_length=100, null=True, blank=True)
    currency = models.CharField(max_length=100, null=True, blank=True, default="GHS")

    # paystack customer information details
    paystack_customer_type = models.CharField(max_length=100, null=True, blank=True)
    paystack_recipient_code = models.CharField(max_length=200, null=True, blank=True)
    paystack_customer_data = models.JSONField(default=dict, null=True, blank=True)

    # ther information
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    uuid = models.UUIDField(unique=True, blank=True, null=True, default=uuid.uuid4)

    def __str__(self):
        return "{} - {} : {}".format(
            self.payment_method_type,
            self.account_number,
            self.account_name,
        )

    class Meta:
        ordering = ["-date_created"]

    def save(self, *args, **kwargs):
        if self.payment_method_type == PaymentMethod.PaymentMethodType.BANK_TRANSFER:
            self.paystack_customer_type = "ghipss"
        else:
            self.paystack_customer_type = "mobile_money"
        super().save(*args, **kwargs)


class CallBackData(models.Model):
    class CallBackUrlType(models.TextChoices):
        MOOLRE = "moolre"
        PAYSTACK = "paystack"

    callback_type = models.CharField(
        choices=CallBackUrlType.choices,
        max_length=20,
        default=CallBackUrlType.MOOLRE,
    )
    uuid = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        default=uuid.uuid4,
    )
    data = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return str(self.uuid)


class Settlement(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pharmacy = models.ForeignKey(
        PharmacyProfile,
        on_delete=models.CASCADE,
        related_name="settlements",
    )
    settlement_date = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "settlements"
        verbose_name = "Settlement"
        verbose_name_plural = "Settlements"
        ordering = ["-settlement_date", "-created_at"]
        unique_together = ("pharmacy", "settlement_date")
        indexes = [
            models.Index(fields=["pharmacy", "status"]),
            models.Index(fields=["pharmacy", "settlement_date"]),
        ]

    def __str__(self):
        return f"{self.pharmacy.pharmacy_name} - {self.settlement_date} ({self.status})"


class SettlementOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    settlement = models.ForeignKey(
        Settlement,
        on_delete=models.CASCADE,
        related_name="settlement_orders",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="settlement_entries",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "settlement_orders"
        verbose_name = "Settlement Order"
        verbose_name_plural = "Settlement Orders"
        unique_together = ("settlement", "order")
        indexes = [
            models.Index(fields=["settlement"]),
            models.Index(fields=["order"]),
        ]

    def __str__(self):
        return f"{self.order.order_number} -> {self.settlement.settlement_date}"
