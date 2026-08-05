"""
Regression tests for audit findings 2.1 and 2.2, and specifically for the
interaction between them.

Finding 2.2 asked that the UI stop reporting success when nothing was sent.
The obvious implementation — return an error when *this* send fails — quietly
reopens finding 2.1: during a mail outage, an error would mean "that address is
registered" and a success would mean "it is not". These tests pin the response
to be identical either way.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

# The project cache is Redis, shared with any dev server running locally.
# Writing attempt counters into it from the test suite would leak into manual
# and end-to-end testing, so these tests use an isolated in-memory cache.
ISOLATED_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "password-reset-tests",
    }
}
from django.urls import reverse

from accounts.models import CustomUser


@override_settings(
    # Take rate limiting out of the picture; it is covered separately and would
    # otherwise mask the status codes under test.
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {},
        "EXCEPTION_HANDLER": "config.exceptions.custom_exception_handler",
    }
)
class PasswordResetEnumerationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("accounts:request_password_reset")
        self.registered = "registered@example.com"
        CustomUser.objects.create_user(
            username=self.registered,
            email=self.registered,
            password="a-real-password",
        )
        self.unregistered = "no-such-account@example.com"

    def _post(self, email):
        return self.client.post(self.url, {"email": email}, content_type="application/json")

    def test_healthy_provider_gives_identical_responses(self):
        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=True
        ):
            known = self._post(self.registered)
            unknown = self._post(self.unregistered)

        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.json(), unknown.json())

    def test_broken_provider_gives_identical_responses(self):
        """
        The regression this file exists for: with mail down, a registered
        address must not answer differently from an unregistered one.
        """
        with patch("accounts.views.mail_provider_ready", return_value=False):
            known = self._post(self.registered)
            unknown = self._post(self.unregistered)

        self.assertEqual(
            known.status_code,
            unknown.status_code,
            "Status code reveals whether the account exists during a mail outage",
        )
        self.assertEqual(
            known.json(),
            unknown.json(),
            "Response body reveals whether the account exists during a mail outage",
        )
        # And it must be an honest failure, not a false success (finding 2.2).
        self.assertEqual(known.status_code, 503)

    def test_no_email_is_attempted_when_the_provider_is_down(self):
        """Avoids burning a reset token on a send that cannot succeed."""
        with patch("accounts.views.mail_provider_ready", return_value=False), patch(
            "accounts.views.send_mail_now"
        ) as send:
            self._post(self.registered)

        send.assert_not_called()

    def test_successful_send_reports_success(self):
        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=True
        ):
            response = self._post(self.registered)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_failed_send_does_not_report_success(self):
        """Finding 2.2: the UI must not claim an email was sent when it was not."""
        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=False
        ):
            response = self._post(self.registered)

        self.assertEqual(response.status_code, 503)
        self.assertNotEqual(response.json().get("status"), "success")


@override_settings(
    CACHES=ISOLATED_CACHE,
    CAPTCHA_SECRET_KEY="test-secret",
    CAPTCHA_CHALLENGE_AFTER_ATTEMPTS=3,
)
class AdaptiveCaptchaTests(TestCase):
    """
    The challenge is hidden until a client has made 3 attempts, then required.

    A CAPTCHA on the first attempt punishes someone who simply mistyped their
    address; one that never appears protects nothing.
    """

    def setUp(self):
        cache.clear()
        self.url = reverse("accounts:request_password_reset")

        # Rate limiting is covered by its own tests and would otherwise return
        # 429 before the challenge logic is reached. It cannot be switched off
        # with override_settings: DRF binds THROTTLE_RATES as a class attribute
        # at import time, so a settings override never reaches it.
        throttles = patch(
            "rest_framework.throttling.SimpleRateThrottle.allow_request",
            return_value=True,
        )
        throttles.start()
        self.addCleanup(throttles.stop)

    def _post(self, email="someone@example.com", token=None):
        payload = {"email": email}
        if token is not None:
            payload["captcha_token"] = token
        return self.client.post(self.url, payload, content_type="application/json")

    def test_first_three_attempts_need_no_challenge(self):
        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=True
        ):
            for i in range(3):
                response = self._post()
                self.assertEqual(response.status_code, 200, f"attempt {i + 1}")

    def test_fourth_attempt_demands_the_challenge(self):
        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=True
        ):
            for _ in range(3):
                self._post()
            response = self._post()

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json()["captcha_required"])
        self.assertIn("robot", response.json()["message"].lower())

    def test_the_third_response_warns_the_next_one_needs_a_challenge(self):
        """So the form can render the challenge before the user is rejected."""
        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=True
        ):
            responses = [self._post() for _ in range(3)]

        self.assertFalse(responses[0].json()["captcha_required"])
        self.assertTrue(
            responses[2].json()["captcha_required"],
            "The third response should flag that a challenge is now due",
        )

    def test_a_solved_challenge_lets_the_request_through(self):
        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=True
        ), patch("accounts.views.verify_captcha", return_value=True):
            for _ in range(3):
                self._post()
            response = self._post(token="a-valid-token")

        self.assertEqual(response.status_code, 200)

    def test_a_failed_challenge_is_rejected(self):
        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=True
        ), patch("accounts.views.verify_captcha", return_value=False):
            for _ in range(3):
                self._post()
            response = self._post(token="a-bad-token")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json()["captcha_required"])

    def test_solving_the_challenge_restores_the_allowance(self):
        """Otherwise every subsequent attempt would demand a fresh puzzle."""
        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=True
        ), patch("accounts.views.verify_captcha", return_value=True):
            for _ in range(3):
                self._post()
            solved = self._post(token="a-valid-token")

        self.assertFalse(
            solved.json()["captcha_required"],
            "Counter should reset once the client has proved it is human",
        )

    def test_a_rejected_attempt_does_not_count_against_the_user(self):
        """
        Otherwise a user who cannot solve the puzzle would be pushed further
        from ever clearing it.
        """
        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=True
        ):
            for _ in range(3):
                self._post()

            from helpers.captcha import attempt_count

            before = attempt_count("password_reset", "127.0.0.1")
            self._post()  # rejected, no token
            after = attempt_count("password_reset", "127.0.0.1")

        self.assertEqual(before, after)

    def test_status_endpoint_reports_the_challenge_state(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["captcha_required"])
        self.assertEqual(body["challenge_after"], 3)

        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=True
        ):
            for _ in range(3):
                self._post()

        self.assertTrue(self.client.get(self.url).json()["captcha_required"])

    @override_settings(CAPTCHA_SECRET_KEY="")
    def test_no_challenge_when_captcha_is_not_configured(self):
        """An environment without keys must keep working exactly as before."""
        with patch("accounts.views.mail_provider_ready", return_value=True), patch(
            "accounts.views.send_mail_now", return_value=True
        ):
            for _ in range(6):
                response = self._post()
                self.assertEqual(response.status_code, 200)
