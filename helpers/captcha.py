"""
Bot-resistance check for unauthenticated public forms.

Supports Cloudflare Turnstile, hCaptcha and Google reCAPTCHA v2/v3 — they all
expose the same "POST secret + response token, get back {success: bool}" shape.

Verification is a no-op until `CAPTCHA_SECRET_KEY` is set, so enabling it is a
deploy-time decision: set the provider + secret in the environment and every
guarded endpoint starts enforcing it without a code change.
"""

import hashlib

import requests
from django.conf import settings
from django.core.cache import cache
from loguru import logger

VERIFY_URLS = {
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    "hcaptcha": "https://hcaptcha.com/siteverify",
    # v2 (checkbox) and v3 (invisible, score-based) verify against the same
    # endpoint; they differ only in how the browser obtains the token, and in
    # that v3 responses carry a `score` which is checked below.
    "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
    "recaptcha_v3": "https://www.google.com/recaptcha/api/siteverify",
}

ATTEMPT_PREFIX = "challenge:attempts"


def captcha_enabled() -> bool:
    return bool((getattr(settings, "CAPTCHA_SECRET_KEY", "") or "").strip())


def verify_captcha(token: str, remote_ip: str = "") -> bool:
    """
    Validate a CAPTCHA token with the configured provider.

    Returns True when the check passes *or* when CAPTCHA is not configured, so
    the platform keeps working in environments that have not enabled it.
    """
    if not captcha_enabled():
        return True

    if not token:
        return False

    provider = (getattr(settings, "CAPTCHA_PROVIDER", "turnstile") or "turnstile").lower()
    verify_url = VERIFY_URLS.get(provider)
    if not verify_url:
        logger.error(f"CAPTCHA_PROVIDER '{provider}' is not supported; rejecting request")
        return False

    payload = {"secret": settings.CAPTCHA_SECRET_KEY, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = requests.post(verify_url, data=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        # Fail closed: a provider outage must not become a bypass.
        logger.error(f"CAPTCHA verification call failed ({provider}): {exc}")
        return False

    if not data.get("success"):
        logger.warning(f"CAPTCHA rejected ({provider}): {data.get('error-codes')}")
        return False

    # reCAPTCHA v3 returns a score; enforce a floor when one is present.
    score = data.get("score")
    if score is not None:
        threshold = float(getattr(settings, "CAPTCHA_MIN_SCORE", 0.5))
        if float(score) < threshold:
            logger.warning(f"CAPTCHA score {score} below threshold {threshold}")
            return False

    return True


# ---------------------------------------------------------------------------
# Adaptive challenge
#
# A CAPTCHA on every request punishes the ordinary user — someone who mistypes
# their email once should not have to solve a puzzle. So the challenge stays
# hidden until a client has made several attempts, at which point it becomes
# required. Legitimate users almost never see it; a script hits it immediately.
# ---------------------------------------------------------------------------


def _attempt_key(scope: str, identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:32]
    return f"{ATTEMPT_PREFIX}:{scope}:{digest}"


def _attempt_window() -> int:
    return int(getattr(settings, "CAPTCHA_ATTEMPT_WINDOW_MINUTES", 60)) * 60


def challenge_threshold() -> int:
    """Attempts allowed before a challenge is demanded."""
    return int(getattr(settings, "CAPTCHA_CHALLENGE_AFTER_ATTEMPTS", 3))


def attempt_count(scope: str, identifier: str) -> int:
    try:
        return int(cache.get(_attempt_key(scope, identifier), 0))
    except Exception as exc:  # pragma: no cover - cache outage
        logger.warning(f"Challenge attempt read failed: {exc}")
        return 0


def record_attempt(scope: str, identifier: str) -> int:
    """Count one attempt and return the running total."""
    key = _attempt_key(scope, identifier)
    try:
        if cache.add(key, 1, _attempt_window()):
            return 1
        try:
            return int(cache.incr(key))
        except ValueError:
            # Expired between add() and incr(); start the window again.
            cache.set(key, 1, _attempt_window())
            return 1
    except Exception as exc:  # pragma: no cover - cache outage
        logger.warning(f"Challenge attempt write failed: {exc}")
        return 0


def reset_attempts(scope: str, identifier: str) -> None:
    """Clear the counter — used once a client has proved it is human."""
    try:
        cache.delete(_attempt_key(scope, identifier))
    except Exception as exc:  # pragma: no cover - cache outage
        logger.warning(f"Challenge attempt reset failed: {exc}")


def challenge_required(scope: str, identifier: str) -> bool:
    """
    Should this client be asked to prove it is human?

    False when CAPTCHA is not configured, so an environment without keys keeps
    working exactly as before.
    """
    if not captcha_enabled():
        return False
    return attempt_count(scope, identifier) >= challenge_threshold()
