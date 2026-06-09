"""
Incoming drug-payment reconciliation.

The Paystack `charge.success` webhook is the authoritative signal that a drug
order has been paid. This mirrors the validation in the verify-payment endpoint
(amount + currency + reference must match what we charged) so the order can't be
marked paid by a spoofed or mismatched event.
"""

from django.db import transaction

from .models import Order, Payment


def apply_charge_event(event: str, data: dict):
    """Handle a Paystack charge.* webhook event. Returns the Payment or None."""
    if event != "charge.success":
        return None

    reference = (data or {}).get("reference")
    if not reference:
        return None

    payment = Payment.objects.filter(reference=reference).first()
    if not payment:
        return None

    # Idempotent: never re-process an already-completed payment.
    if payment.status == Payment.Status.COMPLETED:
        return payment

    amount_matches = data.get("amount") == payment.amount_value()
    currency_matches = data.get("currency") == "GHS"
    reference_matches = data.get("reference") == payment.reference
    status_ok = str(data.get("status")) == "success"

    if status_ok and amount_matches and currency_matches and reference_matches:
        with transaction.atomic():
            payment.status = Payment.Status.COMPLETED
            payment.payment_response = data
            payment.save()
            payment.order.payment_status = Order.PaymentStatus.PAID
            payment.order.save()
        return payment

    # Verified but mismatched/unsuccessful — record for auditing, don't mark paid.
    payment.payment_response = data
    payment.save(update_fields=["payment_response"])
    return payment
