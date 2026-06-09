from datetime import date as dt_date
from decimal import Decimal
from django.db.models import Sum, Count

from .models import (
    PharmacyProfile,
    PharmacyOrder,
    OrderItem,
    Order,
    Settlement,
    SettlementOrder,
)


def sync_settlements_for_pharmacy(pharmacy: PharmacyProfile):
    # Only fulfilled orders are eligible: the pharmacy's portion (PharmacyOrder)
    # must be DELIVERED (delivered or picked up) AND the order must be paid.
    fulfilled_order_ids = PharmacyOrder.objects.filter(
        pharmacy=pharmacy,
        status=PharmacyOrder.Status.DELIVERED,
    ).values_list("order_id", flat=True)

    rows = (
        OrderItem.objects.filter(
            drug__pharmacy=pharmacy,
            order__payment_status=Order.PaymentStatus.PAID,
            order_id__in=fulfilled_order_ids,
        )
        .values("order_id", "order__created_at__date")
        .annotate(amount=Sum("total_price"))
        .order_by()
    )

    grouped_by_date = {}
    for row in rows:
        settlement_date = row["order__created_at__date"]
        grouped_by_date.setdefault(settlement_date, []).append(row)

    for settlement_date, date_rows in grouped_by_date.items():
        settlement, _ = Settlement.objects.get_or_create(
            pharmacy=pharmacy,
            settlement_date=settlement_date,
            defaults={"status": Settlement.Status.PENDING},
        )

        # Paid settlements are immutable snapshots; settlements locked into an
        # in-flight payout must not change mid-transfer.
        if settlement.status == Settlement.Status.PAID or settlement.payout_id:
            continue

        current_order_ids = set()
        for row in date_rows:
            current_order_ids.add(row["order_id"])
            SettlementOrder.objects.update_or_create(
                settlement=settlement,
                order_id=row["order_id"],
                defaults={"amount": row["amount"] or Decimal("0.00")},
            )

        settlement.settlement_orders.exclude(order_id__in=current_order_ids).delete()

        total_amount = settlement.settlement_orders.aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0.00")
        settlement.total_amount = total_amount
        settlement.save(update_fields=["total_amount", "updated_at"])

    # Remove empty pending settlements that aren't locked into a payout.
    (
        Settlement.objects.filter(
            pharmacy=pharmacy,
            status=Settlement.Status.PENDING,
            payout__isnull=True,
        )
        .annotate(order_count=Count("settlement_orders"))
        .filter(order_count=0)
        .delete()
    )


def sync_settlement_for_pharmacy_date(
    pharmacy: PharmacyProfile, settlement_date: dt_date
):
    fulfilled_order_ids = PharmacyOrder.objects.filter(
        pharmacy=pharmacy,
        status=PharmacyOrder.Status.DELIVERED,
    ).values_list("order_id", flat=True)

    rows = (
        OrderItem.objects.filter(
            drug__pharmacy=pharmacy,
            order__payment_status=Order.PaymentStatus.PAID,
            order__created_at__date=settlement_date,
            order_id__in=fulfilled_order_ids,
        )
        .values("order_id")
        .annotate(amount=Sum("total_price"))
        .order_by()
    )

    settlement, _ = Settlement.objects.get_or_create(
        pharmacy=pharmacy,
        settlement_date=settlement_date,
        defaults={"status": Settlement.Status.PENDING},
    )

    # Paid settlements are immutable; payout-locked settlements must not change.
    if settlement.status == Settlement.Status.PAID or settlement.payout_id:
        return settlement

    current_order_ids = set()
    for row in rows:
        current_order_ids.add(row["order_id"])
        SettlementOrder.objects.update_or_create(
            settlement=settlement,
            order_id=row["order_id"],
            defaults={"amount": row["amount"] or Decimal("0.00")},
        )

    settlement.settlement_orders.exclude(order_id__in=current_order_ids).delete()

    if not current_order_ids:
        settlement.delete()
        return None

    total_amount = settlement.settlement_orders.aggregate(total=Sum("amount"))[
        "total"
    ] or Decimal("0.00")
    settlement.total_amount = total_amount
    settlement.save(update_fields=["total_amount", "updated_at"])
    return settlement


def sync_settlements_for_all_pharmacies():
    for pharmacy in PharmacyProfile.objects.all().iterator():
        sync_settlements_for_pharmacy(pharmacy)
