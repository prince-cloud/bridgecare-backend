"""
Tests for the API error envelope (QA findings SET-01, PRO-01, XCUT-01).

Every DRF ValidationError used to reach the client with the same `errorMsg`:
"A field exception occured. Find the exact fields as part of this json
data." Clients showed that raw text to users. `errorMsg` must now carry the
first field error in plain words, and the per-field dict must stay in the
body.
"""

from django.test import SimpleTestCase
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from config.exceptions import custom_exception_handler, field_error_message


class FieldErrorMessageTests(SimpleTestCase):
    def test_flat_field_error_names_the_field(self):
        data = {"phone_number": ["Enter a valid phone number."]}
        self.assertEqual(
            field_error_message(data), "Phone number: Enter a valid phone number."
        )

    def test_nested_field_error_uses_the_innermost_field(self):
        data = {"user": {"phone_number": ["Enter a valid phone number."]}}
        self.assertEqual(
            field_error_message(data), "Phone number: Enter a valid phone number."
        )

    def test_list_item_error_skips_the_index(self):
        data = {"items": [{}, {"quantity": ["Must be at least 1."]}]}
        self.assertEqual(field_error_message(data), "Quantity: Must be at least 1.")

    def test_non_field_error_has_no_label(self):
        data = {"non_field_errors": ["Passwords do not match."]}
        self.assertEqual(field_error_message(data), "Passwords do not match.")

    def test_envelope_keys_are_skipped(self):
        data = {"errorCode": 400, "errorMsg": "old", "email": ["Required."]}
        self.assertEqual(field_error_message(data), "Email: Required.")

    def test_empty_payload_falls_back_to_generic_text(self):
        self.assertEqual(
            field_error_message({}),
            "Please check the highlighted fields and try again.",
        )
        self.assertEqual(
            field_error_message(None),
            "Please check the highlighted fields and try again.",
        )


class _Form(serializers.Serializer):
    email = serializers.EmailField()
    phone_number = serializers.CharField()


class CustomExceptionHandlerTests(SimpleTestCase):
    def _context(self):
        return {"request": APIRequestFactory().post("/x/")}

    def test_validation_error_keeps_fields_and_adds_readable_summary(self):
        form = _Form(data={"email": "not-an-email", "phone_number": ""})
        with self.assertRaises(ValidationError) as raised:
            form.is_valid(raise_exception=True)

        response = custom_exception_handler(raised.exception, self._context())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["errorCode"], 400)
        # Per-field messages are still there for the client to place inline.
        self.assertIn("email", response.data)
        self.assertIn("phone_number", response.data)
        # The summary is one field error in plain words, not the old text.
        self.assertTrue(response.data["errorMsg"].startswith("Email: "))
        self.assertNotIn("json", response.data["errorMsg"].lower())
        self.assertNotIn("exception", response.data["errorMsg"].lower())

    def test_other_api_exceptions_keep_their_own_sentence(self):
        # Throttling used to arrive as "Some unexpected exception occured".
        from rest_framework.exceptions import NotAuthenticated, Throttled

        throttled = custom_exception_handler(Throttled(wait=42), self._context())
        self.assertEqual(throttled.status_code, 429)
        self.assertEqual(throttled.data["errorCode"], 429)
        self.assertIn("throttled", throttled.data["errorMsg"].lower())
        self.assertNotIn("unexpected", throttled.data["errorMsg"].lower())

        unauth = custom_exception_handler(NotAuthenticated(), self._context())
        self.assertEqual(unauth.status_code, 401)
        self.assertEqual(unauth.data["errorMsg"], unauth.data["detail"])

    def test_validation_error_raised_with_a_list_is_wrapped(self):
        response = custom_exception_handler(
            ValidationError(["Start date must be before end date."]),
            self._context(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["non_field_errors"],
            ["Start date must be before end date."],
        )
        self.assertEqual(
            response.data["errorMsg"], "Start date must be before end date."
        )
