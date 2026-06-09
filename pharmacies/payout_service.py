"""
Settlement payout (disbursement) service.

Pharmacies accrue PENDING settlements from their fulfilled, paid drug sales.
This module turns the available balance into an on-demand Paystack single
transfer to the pharmacy's collection account, and reconciles the result via
webhook (primary) or the verify-transfer API (fallback).
"""

import hashlib
import hmac
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from loguru import logger

from api.paystack import PayStack
from helpers import exceptions
from .models import PaymentMethod, Settlement, SettlementPayout

# Paystack transfer statuses that are not yet terminal — we wait for a webhook.
_PENDING_TRANSFER_STATUSES = {
    "pending",
    "processing",
    "queued",
    "received",
    "otp",
}
_CENT = Decimal("0.01")


def _quantize(amount: Decimal) -> Decimal:
    return (amount or Decimal("0.00")).quantize(_CENT, rounding=ROUND_HALF_UP)


def compute_commission(gross: Decimal):
    """Return (commission_amount, net_amount) for a gross settlement total."""
    pct = Decimal(str(getattr(settings, "SETTLEMENT_COMMISSION_PERCENT", 0) or 0))
    commission = _quantize(gross * pct / Decimal("100"))
    net = _quantize(gross - commission)
    return commission, net


def available_settlements_qs(pharmacy):
    """PENDING settlements not already locked into a payout."""
    return Settlement.objects.filter(
        pharmacy=pharmacy,
        status=Settlement.Status.PENDING,
        payout__isnull=True,
    )


def _payout_methods_qs(pharmacy):
    return (
        PaymentMethod.objects.filter(user=pharmacy.user)
        .exclude(paystack_recipient_code__isnull=True)
        .exclude(paystack_recipient_code="")
        .order_by("-date_created")
    )


def get_available_balance(pharmacy) -> dict:
    """Summary of what the pharmacy can currently withdraw."""
    from django.db.models import Sum, Count

    agg = available_settlements_qs(pharmacy).aggregate(
        total=Sum("total_amount"), count=Count("id")
    )
    gross = agg["total"] or Decimal("0.00")
    commission, net = compute_commission(gross)
    method = _payout_methods_qs(pharmacy).first()

    return {
        "available_amount": net,
        "gross_amount": _quantize(gross),
        "commission_amount": commission,
        "commission_percent": float(
            getattr(settings, "SETTLEMENT_COMMISSION_PERCENT", 0) or 0
        ),
        "settlement_count": agg["count"] or 0,
        "currency": "GHS",
        "has_payout_method": method is not None,
        "payment_method_id": str(method.uuid) if method and method.uuid else None,
    }


def resolve_payment_method(pharmacy, payment_method_id=None):
    """Pick the collection account to disburse to (validates ownership + Paystack link)."""
    qs = _payout_methods_qs(pharmacy)
    if payment_method_id:
        method = qs.filter(uuid=payment_method_id).first()
        if not method:
            raise exceptions.GeneralException(
                detail="Selected collection account was not found or is not linked to Paystack."
            )
        return method

    method = qs.first()
    if not method:
        raise exceptions.GeneralException(
            detail="Add a collection account (bank or mobile money) before requesting a payout."
        )
    return method


def _generate_reference() -> str:
    reference = f"PSO-{uuid.uuid4().hex[:24]}"
    while SettlementPayout.objects.filter(reference=reference).exists():
        reference = f"PSO-{uuid.uuid4().hex[:24]}"
    return reference


@transaction.atomic
def create_payout(pharmacy, payment_method) -> SettlementPayout:
    """
    Lock all currently-available settlements into a new payout. Uses
    select_for_update so two concurrent requests can't disburse the same funds.
    """
    settlements = list(
        Settlement.objects.select_for_update()
        .filter(
            pharmacy=pharmacy,
            status=Settlement.Status.PENDING,
            payout__isnull=True,
        )
    )
    if not settlements:
        raise exceptions.GeneralException(detail="You have no funds available for payout.")

    gross = sum((s.total_amount for s in settlements), Decimal("0.00"))
    commission, net = compute_commission(gross)
    if net <= 0:
        raise exceptions.GeneralException(detail="Available payout amount is zero.")

    payout = SettlementPayout.objects.create(
        pharmacy=pharmacy,
        payment_method=payment_method,
        gross_amount=_quantize(gross),
        commission_amount=commission,
        amount=net,
        reference=_generate_reference(),
        reason=f"BridgeCare settlement payout - {pharmacy.pharmacy_name}"[:255],
        status=SettlementPayout.Status.PENDING,
    )
    Settlement.objects.filter(id__in=[s.id for s in settlements]).update(payout=payout)
    logger.info(
        f"Payout created: id={payout.id} pharmacy={pharmacy.pharmacy_name!r} "
        f"net={net} gross={gross} settlements={len(settlements)} "
        f"reference={payout.reference}"
    )
    return payout


def _merge_metadata(payout: SettlementPayout, key: str, payload):
    data = dict(payout.metadata or {})
    data[key] = payload if isinstance(payload, (dict, list)) else str(payload)
    payout.metadata = data


def initiate_payout_transfer(payout: SettlementPayout) -> SettlementPayout:
    """Kick off the Paystack transfer. Final status is confirmed by webhook."""
    amount_pesewas = int(
        (payout.amount * 100).to_integral_value(rounding=ROUND_HALF_UP)
    )
    body = {
        "source": "balance",
        "amount": amount_pesewas,
        "recipient": payout.payment_method.paystack_recipient_code,
        "reference": payout.reference,
        "reason": payout.reason or "Settlement payout",
    }

    logger.info(
        f"Initiating Paystack transfer: payout={payout.id} amount_pesewas={amount_pesewas} "
        f"recipient={body['recipient']!r} reference={payout.reference}"
    )
    success, data = PayStack().initiate_transfer(body)
    _merge_metadata(payout, "initiate", data)
    logger.info(
        f"Paystack transfer response: payout={payout.id} success={success} data={data!r}"
    )

    if not success:
        # `data` is Paystack's error message (e.g. insufficient Paystack balance).
        logger.warning(
            f"Paystack transfer rejected: payout={payout.id} reason={data!r}"
        )
        return mark_payout_failed(payout, reason=str(data))

    transfer_status = str((data or {}).get("status") or "").lower()
    payout.transfer_code = (data or {}).get("transfer_code") or payout.transfer_code

    if transfer_status == "success":
        return mark_payout_success(payout, payload=data)
    if transfer_status in ("failed", "abandoned"):
        return mark_payout_failed(payout, reason=f"Transfer {transfer_status}", payload=data)
    if transfer_status == "reversed":
        return mark_payout_failed(
            payout, reason="Transfer reversed", payload=data, reversed_=True
        )

    # pending / processing / queued / otp → await webhook confirmation
    payout.status = SettlementPayout.Status.PROCESSING
    payout.save(update_fields=["status", "transfer_code", "metadata", "updated_at"])
    logger.info(
        f"Payout awaiting confirmation: payout={payout.id} transfer_status={transfer_status!r} "
        f"transfer_code={payout.transfer_code!r}"
    )
    return payout


def mark_payout_success(payout: SettlementPayout, payload=None) -> SettlementPayout:
    if payout.status == SettlementPayout.Status.SUCCESS:
        return payout
    now = timezone.now()
    with transaction.atomic():
        locked = SettlementPayout.objects.select_for_update().get(pk=payout.pk)
        if locked.status == SettlementPayout.Status.SUCCESS:
            return locked
        locked.status = SettlementPayout.Status.SUCCESS
        locked.completed_at = now
        locked.failure_reason = None
        if payload is not None:
            _merge_metadata(locked, "success", payload)
        locked.save()
        count = locked.settlements.update(status=Settlement.Status.PAID, paid_at=now)
    logger.info(
        f"Payout SUCCESS: payout={locked.id} amount={locked.amount} "
        f"settlements_paid={count} reference={locked.reference}"
    )
    return locked


def mark_payout_failed(
    payout: SettlementPayout, reason=None, payload=None, reversed_=False
) -> SettlementPayout:
    """
    Mark a payout failed (or reversed) and release its settlements back to the
    available balance so the pharmacy can retry.
    """
    now = timezone.now()
    with transaction.atomic():
        locked = SettlementPayout.objects.select_for_update().get(pk=payout.pk)
        # Already in a terminal failure state — nothing to do.
        if locked.status in (
            SettlementPayout.Status.FAILED,
            SettlementPayout.Status.REVERSED,
        ):
            return locked
        # A plain "failed" event arriving after success is ignored; only an
        # explicit reversal can undo a successful payout.
        if locked.status == SettlementPayout.Status.SUCCESS and not reversed_:
            return locked

        locked.status = (
            SettlementPayout.Status.REVERSED
            if reversed_
            else SettlementPayout.Status.FAILED
        )
        locked.failure_reason = reason
        locked.completed_at = now
        if payload is not None:
            _merge_metadata(locked, "failure", payload)
        locked.save()
        # Release settlements: un-pay (if reversed after success) and detach.
        released = locked.settlements.update(
            status=Settlement.Status.PENDING, paid_at=None, payout=None
        )
    logger.warning(
        f"Payout {locked.status.upper()}: payout={locked.id} reason={reason!r} "
        f"settlements_released={released} reference={locked.reference}"
    )
    return locked


def reconcile_payout(payout: SettlementPayout) -> SettlementPayout:
    """Fallback reconciliation via the verify-transfer API (e.g. missed webhook)."""
    if payout.status in (
        SettlementPayout.Status.SUCCESS,
        SettlementPayout.Status.FAILED,
        SettlementPayout.Status.REVERSED,
    ):
        return payout

    success, data = PayStack().verify_transfer(payout.reference)
    if not success:
        return payout

    transfer_status = str((data or {}).get("status") or "").lower()
    if transfer_status == "success":
        return mark_payout_success(payout, payload=data)
    if transfer_status in ("failed", "abandoned"):
        return mark_payout_failed(payout, reason=f"Transfer {transfer_status}", payload=data)
    if transfer_status == "reversed":
        return mark_payout_failed(
            payout, reason="Transfer reversed", payload=data, reversed_=True
        )
    return payout


def apply_transfer_event(event: str, data: dict):
    """Apply a Paystack transfer.* webhook event to the matching payout."""
    reference = (data or {}).get("reference")
    if not reference:
        return None
    payout = SettlementPayout.objects.filter(reference=reference).first()
    if not payout:
        return None

    if event == "transfer.success":
        return mark_payout_success(payout, payload=data)
    if event == "transfer.failed":
        return mark_payout_failed(payout, reason="Transfer failed", payload=data)
    if event == "transfer.reversed":
        return mark_payout_failed(
            payout, reason="Transfer reversed", payload=data, reversed_=True
        )
    return payout


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Paystack signs the raw body with HMAC-SHA512 using the secret key."""
    secret = (settings.PAYSTACK_PRIVATE_KEY or "").encode()
    if not secret or not signature:
        return False
    computed = hmac.new(secret, raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, signature)
