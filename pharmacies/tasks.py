from api.paystack import PayStack
from . import models
from .settlement_service import (
    sync_settlements_for_all_pharmacies,
    sync_settlements_for_pharmacy,
)
from config import celery_app
import uuid


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
def initiate_paystack_transfer(claim_id):
    claim = models.Claim.objects.get(id=claim_id)
    claim.status = models.Claim.Status.PROCESSING
    claim.save()

    transaction_reference = str(uuid.uuid4())
    while models.ClaimsPayment.objects.filter(reference=transaction_reference).exists():
        transaction_reference = str(uuid.uuid4())

    payment = models.ClaimsPayment.objects.create(
        claim=claim,
        amount=claim.amount_receivable,
        reference=transaction_reference,
    )

    # create claims payment
    body = {
        "source": "balance",
        "amount": str(payment.amount * 100),
        "recipient": str(claim.payment_method.paystack_recipient_code),
        "reference": str(payment.reference),
        "reason": str(claim.reason),
    }

    success, data = PayStack().initiate_transfer(data=body)

    if not success:
        payment.status = models.ClaimsPayment.Status.FAILED
        payment.metadata = data
        payment.save()
        claim.status = models.Claim.Status.FAILED
        claim.save()
        return

    else:
        payment.metadata = data
        payment.save()
        # verify transfer
        verify_paystack_transfer.delay(transaction_reference)


@celery_app.task
def verify_paystack_transfer(transaction_reference):
    print("==== verify transfer ====")
    pass


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
