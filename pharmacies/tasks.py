from api.paystack import PayStack
from . import models
from .settlement_service import (
    sync_settlements_for_all_pharmacies,
    sync_settlements_for_pharmacy,
)
from config import celery_app
from django.utils import timezone
from datetime import timedelta
from accounts.tasks import generic_send_mail
from loguru import logger


@celery_app.task
def create_paystack_recipient(payment_method_id):
    payment_method: models.PaymentMethod = models.PaymentMethod.objects.get(
        id=payment_method_id
    )

    data = {
        "type": payment_method.paystack_customer_type,
        "name": payment_method.account_name,
        "account_number": payment_method.account_number,
        "bank_code": payment_method.provider_code,
        "currency": payment_method.currency,
    }
    success, data = PayStack().create_recipient(data)

    if success:
        payment_method.paystack_recipient_code = data["recipient_code"]
        payment_method.paystack_customer_data = data
        payment_method.save()
    else:
        # TODO: put retry mechanism here
        pass


@celery_app.task
def initiate_settlement_payout(payout_id):
    """
    Async wrapper to start a Paystack transfer for an already-created payout.
    The request path normally initiates inline; this is for retries/scheduled use.
    """
    from .payout_service import initiate_payout_transfer

    payout = models.SettlementPayout.objects.filter(id=payout_id).first()
    if not payout or payout.status != models.SettlementPayout.Status.PENDING:
        return
    initiate_payout_transfer(payout)


@celery_app.task
def reconcile_pending_payouts():
    """
    Fallback reconciliation for payouts stuck in PROCESSING (e.g. a missed
    webhook): verify each against Paystack and finalize. Safe to run on a beat.
    """
    from .payout_service import reconcile_payout

    pending = models.SettlementPayout.objects.filter(
        status=models.SettlementPayout.Status.PROCESSING
    )
    for payout in pending.iterator():
        try:
            reconcile_payout(payout)
        except Exception as exc:
            logger.error(f"Failed to reconcile payout {payout.id}: {exc}")


@celery_app.task
def calculate_daily_settlements():
    """
    Recalculate settlements for all pharmacies.
    Intended to run once daily at 11:55 PM.
    """
    sync_settlements_for_all_pharmacies()


@celery_app.task
def calculate_pharmacy_settlements(pharmacy_id):
    """
    Recalculate settlements for a specific pharmacy.
    """
    pharmacy = models.PharmacyProfile.objects.filter(id=pharmacy_id).first()
    if not pharmacy:
        return
    sync_settlements_for_pharmacy(pharmacy)


@celery_app.task
def send_expiry_alerts():
    """
    Daily task: email pharmacies about drug batches expiring within 30 days.
    Runs at 08:00 UTC each day.
    """
    today = timezone.now().date()
    threshold = today + timedelta(days=30)

    pharmacies = models.PharmacyProfile.objects.filter(user__is_active=True).select_related("user")

    for pharmacy in pharmacies:
        expiring_batches = (
            models.DrugBatch.objects.filter(
                pharmacy=pharmacy,
                expiry_date__gte=today,
                expiry_date__lte=threshold,
            )
            .select_related("drug")
            .order_by("expiry_date")
        )

        if not expiring_batches.exists():
            continue

        items_html = "".join(
            f"<li><strong>{b.drug.name}</strong> — Batch {b.batch_number} expires on <strong>{b.expiry_date}</strong></li>"
            for b in expiring_batches
        )
        body = (
            f"<p>The following drug batches in your pharmacy are expiring within the next 30 days:</p>"
            f"<ul style='color:#333;line-height:1.8'>{items_html}</ul>"
            "<p>Please take the necessary steps to manage these items (return, discount, or dispose).</p>"
        )

        email = pharmacy.email or pharmacy.user.email
        if not email:
            continue

        try:
            generic_send_mail.delay(
                recipient=email,
                title="⚠️ Drug Expiry Alert — Action Required",
                payload={
                    "user_name": pharmacy.pharmacy_name,
                    "body": body,
                },
                email_type=None,
            )
            logger.info(f"Expiry alert sent to {pharmacy.pharmacy_name} ({email})")
        except Exception as exc:
            logger.error(f"Failed to send expiry alert to {email}: {exc}")
