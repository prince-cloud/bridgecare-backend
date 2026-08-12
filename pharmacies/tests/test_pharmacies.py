from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from accounts.models import CustomUser
from .models import (
    PharmacyProfile,
    PaymentMethod,
    DrugCategory,
    Drug,
    DrugUnit,
    Order,
    OrderItem,
    PharmacyOrder,
    Payment,
    Settlement,
    SettlementPayout,
)
from . import payout_service
from . import payment_service
from .settlement_service import sync_settlements_for_pharmacy


def make_pharmacy(email, license_no):
    # No `platform` set → the profile-creation signal is skipped, so we build
    # a fully-populated PharmacyProfile ourselves.
    user = CustomUser.objects.create(username=email, email=email)
    return PharmacyProfile.objects.create(
        user=user,
        pharmacy_name=f"Pharm {license_no}",
        pharmacy_license=license_no,
        address="123 Street",
        phone_number="+233200000000",
        is_verified=True,
    )


def make_paid_order(user, drug, quantity, status):
    order = Order.objects.create(
        user=user,
        subtotal=drug.unit_price * quantity,
        total_amount=drug.unit_price * quantity,
        payment_status=Order.PaymentStatus.PAID,
    )
    OrderItem.objects.create(
        order=order,
        drug=drug,
        quantity=quantity,
        unit_price=drug.unit_price,
        total_price=drug.unit_price * quantity,
    )
    PharmacyOrder.objects.create(pharmacy=drug.pharmacy, order=order, status=status)
    return order


class SettlementEligibilityTests(TestCase):
    def setUp(self):
        self.pharmacy = make_pharmacy("elig@x.com", "LIC-ELIG")
        category = DrugCategory.objects.create(pharmacy=self.pharmacy, name="Cat")
        self.drug = Drug.objects.create(
            pharmacy=self.pharmacy,
            name="Paracetamol",
            category=category,
            base_unit=DrugUnit.TABLET,
            unit_price=Decimal("10.00"),
        )

    def test_unfulfilled_order_is_not_settled(self):
        make_paid_order(self.pharmacy.user, self.drug, 3, PharmacyOrder.Status.PENDING)
        sync_settlements_for_pharmacy(self.pharmacy)
        self.assertEqual(Settlement.objects.filter(pharmacy=self.pharmacy).count(), 0)

    def test_delivered_order_is_settled(self):
        make_paid_order(self.pharmacy.user, self.drug, 3, PharmacyOrder.Status.DELIVERED)
        sync_settlements_for_pharmacy(self.pharmacy)
        settlement = Settlement.objects.get(pharmacy=self.pharmacy)
        self.assertEqual(settlement.total_amount, Decimal("30.00"))
        self.assertEqual(settlement.status, Settlement.Status.PENDING)


class PayoutFlowTests(TestCase):
    def setUp(self):
        self.pharmacy = make_pharmacy("payout@x.com", "LIC-PAY")
        self.method = PaymentMethod.objects.create(
            user=self.pharmacy.user,
            payment_method_type=PaymentMethod.PaymentMethodType.MOBILE_MONEY,
            account_number="0240000000",
            account_name="Pharm Pay",
            provider="MTN",
            paystack_recipient_code="RCP_test123",
        )
        # Two pending settlements totalling 80.00
        Settlement.objects.create(
            pharmacy=self.pharmacy,
            settlement_date="2026-06-01",
            total_amount=Decimal("50.00"),
            status=Settlement.Status.PENDING,
        )
        Settlement.objects.create(
            pharmacy=self.pharmacy,
            settlement_date="2026-06-02",
            total_amount=Decimal("30.00"),
            status=Settlement.Status.PENDING,
        )

    def test_available_balance(self):
        balance = payout_service.get_available_balance(self.pharmacy)
        self.assertEqual(balance["available_amount"], Decimal("80.00"))
        self.assertEqual(balance["settlement_count"], 2)
        self.assertTrue(balance["has_payout_method"])

    def test_create_payout_locks_settlements(self):
        payout = payout_service.create_payout(self.pharmacy, self.method)
        self.assertEqual(payout.amount, Decimal("80.00"))
        self.assertEqual(payout.settlements.count(), 2)
        # Balance is now empty (settlements locked).
        balance = payout_service.get_available_balance(self.pharmacy)
        self.assertEqual(balance["available_amount"], Decimal("0.00"))

    def test_successful_transfer_marks_settlements_paid(self):
        payout = payout_service.create_payout(self.pharmacy, self.method)
        with patch("pharmacies.payout_service.PayStack") as MockPaystack:
            MockPaystack.return_value.initiate_transfer.return_value = (
                True,
                {"status": "pending", "transfer_code": "TRF_1", "reference": payout.reference},
            )
            payout = payout_service.initiate_payout_transfer(payout)
        self.assertEqual(payout.status, SettlementPayout.Status.PROCESSING)

        # Webhook confirms success.
        payout_service.apply_transfer_event(
            "transfer.success", {"reference": payout.reference, "status": "success"}
        )
        payout.refresh_from_db()
        self.assertEqual(payout.status, SettlementPayout.Status.SUCCESS)
        self.assertTrue(
            all(s.status == Settlement.Status.PAID for s in payout.settlements.all())
        )

    def test_failed_transfer_releases_settlements(self):
        payout = payout_service.create_payout(self.pharmacy, self.method)
        with patch("pharmacies.payout_service.PayStack") as MockPaystack:
            MockPaystack.return_value.initiate_transfer.return_value = (
                True,
                {"status": "pending", "transfer_code": "TRF_2", "reference": payout.reference},
            )
            payout_service.initiate_payout_transfer(payout)

        payout_service.apply_transfer_event(
            "transfer.failed", {"reference": payout.reference, "status": "failed"}
        )
        payout.refresh_from_db()
        self.assertEqual(payout.status, SettlementPayout.Status.FAILED)
        # Settlements released back to the available balance.
        balance = payout_service.get_available_balance(self.pharmacy)
        self.assertEqual(balance["available_amount"], Decimal("80.00"))

    def test_payout_without_balance_is_rejected(self):
        Settlement.objects.filter(pharmacy=self.pharmacy).update(
            status=Settlement.Status.PAID
        )
        with self.assertRaises(Exception):
            payout_service.create_payout(self.pharmacy, self.method)

    def test_request_payout_endpoint(self):
        """End-to-end: empty body must validate and initiate a payout (200)."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.pharmacy.user)
        with patch("pharmacies.payout_service.PayStack") as MockPaystack:
            MockPaystack.return_value.initiate_transfer.return_value = (
                True,
                {"status": "pending", "transfer_code": "TRF_API", "reference": "x"},
            )
            response = client.post(
                "/pharmacies/settlements/request-payout/", {}, format="json"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["payout"]["status"], "processing")


class ChargeWebhookTests(TestCase):
    def setUp(self):
        self.pharmacy = make_pharmacy("charge@x.com", "LIC-CHG")
        self.order = Order.objects.create(
            user=self.pharmacy.user,
            subtotal=Decimal("30.00"),
            total_amount=Decimal("30.00"),
            payment_status=Order.PaymentStatus.PENDING,
        )
        self.payment = Payment.objects.create(
            user=self.pharmacy.user,
            order=self.order,
            amount=Decimal("30.00"),
        )

    def test_charge_success_marks_order_paid(self):
        payment_service.apply_charge_event(
            "charge.success",
            {
                "reference": self.payment.reference,
                "status": "success",
                "amount": self.payment.amount_value(),
                "currency": "GHS",
            },
        )
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.COMPLETED)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    def test_charge_amount_mismatch_does_not_pay(self):
        payment_service.apply_charge_event(
            "charge.success",
            {
                "reference": self.payment.reference,
                "status": "success",
                "amount": 1,  # wrong amount
                "currency": "GHS",
            },
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)
