import django_filters
from .models import Order


class OrderFilter(django_filters.FilterSet):
    """
    Class-based filter set for Order.
    Used by pharmacy users to filter their pharmacy's orders.
    """

    status = django_filters.ChoiceFilter(
        choices=Order.Status.choices,
        field_name="status",
    )
    payment_status = django_filters.ChoiceFilter(
        choices=Order.PaymentStatus.choices,
        field_name="payment_status",
    )
    delivery_method = django_filters.ChoiceFilter(
        choices=Order.DeliveryMethod.choices,
        field_name="delivery_method",
    )
    order_number = django_filters.CharFilter(
        field_name="order_number",
        lookup_expr="icontains",
    )
    pharmacy_status = django_filters.ChoiceFilter(
        choices=[
            ("pending", "Pending"),
            ("confirmed", "Confirmed"),
            ("processing", "Processing"),
            ("ready", "Ready for Pickup"),
            ("shipped", "Shipped"),
            ("delivered", "Delivered"),
            ("cancelled", "Cancelled"),
            ("refunded", "Refunded"),
        ],
        field_name="pharmacy_orders__status",
        label="Pharmacy fulfillment status",
    )
    created_after = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
    )

    class Meta:
        model = Order
        fields = [
            "status",
            "payment_status",
            "delivery_method",
            "order_number",
            "pharmacy_status",
            "created_after",
            "created_before",
        ]
