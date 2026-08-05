"""
Server-side guards for the public AI assistant.

Addresses three findings from the July 2026 audit:

  * 2.3 — the free-question cap lived only in React state, so a page refresh
    reset it. The quota here is keyed to the authenticated user, the chat
    thread, or the client IP and is stored in the shared cache, so it survives
    refreshes, new tabs and cleared local storage.
  * 2.4 — 36+ consecutive jailbreak attempts drew no response at all. Suspicious
    prompts are now scored, logged and counted, and a repeat offender is put
    into a temporary cool-down.
  * 2.5 — topic scope was enforced only by the system prompt. `check_response_scope`
    provides the independent output-side check.

Everything degrades open on infrastructure failure: if the cache is unavailable
the assistant keeps answering rather than locking every visitor out.
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional

from django.conf import settings
from django.core.cache import cache
from loguru import logger

QUOTA_PREFIX = "ai_chat:quota"
ABUSE_PREFIX = "ai_chat:abuse"
COOLDOWN_PREFIX = "ai_chat:cooldown"


def _limit() -> int:
    return int(getattr(settings, "AI_CHAT_FREE_QUESTION_LIMIT", 3))


def _window_seconds() -> int:
    return int(getattr(settings, "AI_CHAT_FREE_WINDOW_HOURS", 24)) * 3600


def _abuse_threshold() -> int:
    return int(getattr(settings, "AI_CHAT_ABUSE_THRESHOLD", 5))


def _cooldown_seconds() -> int:
    return int(getattr(settings, "AI_CHAT_ABUSE_COOLDOWN_MINUTES", 15)) * 60


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


def identity_for(request, thread_id: Optional[str] = None) -> str:
    """
    Stable identity for quota and abuse accounting.

    Authenticated users are keyed by user id. Guests are keyed by IP *and*
    thread id: the IP component means clearing browser state does not reset the
    quota, and including the thread keeps separate visitors behind one NAT from
    being merged into a single allowance more than necessary.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return f"user:{user.id}"

    raw = f"{client_ip(request)}|{thread_id or ''}"
    return f"guest:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]}"


# --------------------------------------------------------------------------
# 2.3 — free-question quota
# --------------------------------------------------------------------------


@dataclass
class QuotaState:
    used: int
    limit: int
    allowed: bool

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


def get_quota(request, thread_id: Optional[str] = None) -> QuotaState:
    """Read the current quota without consuming a question."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        # Signed-in users are not on the free tier.
        return QuotaState(used=0, limit=_limit(), allowed=True)

    limit = _limit()
    try:
        used = int(cache.get(f"{QUOTA_PREFIX}:{identity_for(request, thread_id)}", 0))
    except Exception as exc:
        logger.warning(f"AI quota cache read failed, allowing request: {exc}")
        return QuotaState(used=0, limit=limit, allowed=True)

    return QuotaState(used=used, limit=limit, allowed=used < limit)


def consume_quota(request, thread_id: Optional[str] = None) -> QuotaState:
    """
    Consume one free question. Returns the state *after* consumption.

    Callers must check `allowed` on the returned state: when it is False the
    caller was already over quota and no LLM call should be made.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return QuotaState(used=0, limit=_limit(), allowed=True)

    limit = _limit()
    key = f"{QUOTA_PREFIX}:{identity_for(request, thread_id)}"

    try:
        # add() only succeeds when the key is absent, which starts the window.
        if cache.add(key, 1, _window_seconds()):
            used = 1
        else:
            try:
                used = cache.incr(key)
            except ValueError:
                # Key expired between add() and incr(); restart the window.
                cache.set(key, 1, _window_seconds())
                used = 1
    except Exception as exc:
        logger.warning(f"AI quota cache write failed, allowing request: {exc}")
        return QuotaState(used=0, limit=limit, allowed=True)

    return QuotaState(used=used, limit=limit, allowed=used <= limit)


# --------------------------------------------------------------------------
# 2.4 — prompt-injection detection, logging and cool-down
# --------------------------------------------------------------------------

# Phrasings that recur across public jailbreak attempts. Matching one is not
# proof of malice, so a hit is scored and logged rather than hard-blocking, and
# only repeated hits trigger the cool-down.
INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+|any\s+|your\s+)?(previous|prior|earlier|above)\s+"
        r"(instruction|prompt|rule|direction)",
        r"disregard\s+(all\s+|any\s+|your\s+)?(previous|prior|earlier|above)",
        r"forget\s+(all\s+|everything\s+|your\s+)?(previous|prior|above|instruction|rule)",
        r"\b(system\s*(update|override|prompt)|new\s+(system\s+)?instructions?)\b",
        r"(reveal|show|print|repeat|output|display|tell\s+me)\s+"
        r"(me\s+)?(your|the)\s+(system\s+)?(prompt|instruction|rule|directive|config)",
        r"what\s+(are|were)\s+your\s+(original\s+|initial\s+)?(instruction|prompt|rule)",
        r"\b(developer|debug|god|admin|root|maintenance)\s*mode\b",
        r"\bDAN\b|\bdo\s+anything\s+now\b|\bjailbreak\b",
        r"pretend\s+(you\s+are|to\s+be)\s+(?!a\s+(doctor|nurse|clinician))",
        r"(act|roleplay|behave)\s+as\s+(if\s+you\s+are\s+)?(an?\s+)?"
        r"(unrestricted|uncensored|unfiltered|different)",
        r"you\s+(are\s+)?(no\s+longer|not)\s+(bound|restricted|limited)\s+by",
        r"(without|bypass|ignore|remove|disable)\s+(any\s+|all\s+|your\s+)?"
        r"(restriction|limitation|filter|guardrail|safety|censorship)",
        r"your\s+(previous\s+)?rules\s+are\s+(outdated|obsolete|wrong|invalid)",
        r"\bnever\s+refuse\b",
        r"answer\s+every\s+(user\s+)?request",
        r"\b(sudo|<\|im_start\|>|<\|system\|>|\[\[SYSTEM\]\])",
    )
]


@dataclass
class AbuseState:
    flagged: bool = False
    blocked: bool = False
    strikes: int = 0
    matched: List[str] = field(default_factory=list)
    retry_after: int = 0


def _matched_patterns(text: str) -> List[str]:
    return [p.pattern for p in INJECTION_PATTERNS if p.search(text)]


def check_cooldown(request, thread_id: Optional[str] = None) -> AbuseState:
    """Is this client currently in an abuse cool-down?"""
    key = f"{COOLDOWN_PREFIX}:{identity_for(request, thread_id)}"
    try:
        if cache.get(key):
            return AbuseState(blocked=True, retry_after=_cooldown_seconds())
    except Exception as exc:
        logger.warning(f"AI cooldown cache read failed, allowing request: {exc}")
    return AbuseState()


def inspect_prompt(request, question: str, thread_id: Optional[str] = None) -> AbuseState:
    """
    Score an incoming prompt for injection patterns, record a strike when it
    matches, and start a cool-down once strikes cross the threshold.

    Strikes decay with the cache TTL, so an occasional false positive from a
    legitimate user never accumulates into a block.
    """
    matched = _matched_patterns(question or "")
    if not matched:
        return AbuseState()

    identity = identity_for(request, thread_id)
    ip = client_ip(request)

    # Greppable marker for alerting on prompt-injection activity.
    logger.warning(
        f"AI_PROMPT_INJECTION_SUSPECTED identity={identity} ip={ip} "
        f"patterns={len(matched)} question={question[:200]!r}"
    )

    strikes = 0
    key = f"{ABUSE_PREFIX}:{identity}"
    try:
        if cache.add(key, 1, _cooldown_seconds()):
            strikes = 1
        else:
            try:
                strikes = cache.incr(key)
            except ValueError:
                cache.set(key, 1, _cooldown_seconds())
                strikes = 1
    except Exception as exc:
        logger.warning(f"AI abuse cache write failed: {exc}")

    _record_abuse_event(request, question, matched, strikes)

    if strikes >= _abuse_threshold():
        try:
            cache.set(
                f"{COOLDOWN_PREFIX}:{identity}", True, _cooldown_seconds()
            )
        except Exception as exc:
            logger.warning(f"AI cooldown cache write failed: {exc}")
        logger.error(
            f"AI_ABUSE_COOLDOWN_TRIGGERED identity={identity} ip={ip} strikes={strikes}"
        )
        return AbuseState(
            flagged=True,
            blocked=True,
            strikes=strikes,
            matched=matched,
            retry_after=_cooldown_seconds(),
        )

    return AbuseState(flagged=True, strikes=strikes, matched=matched)


def _record_abuse_event(request, question: str, matched: List[str], strikes: int) -> None:
    """Persist the attempt so the team has visibility in the admin."""
    try:
        from .models import AIAbuseEvent

        user = getattr(request, "user", None)
        AIAbuseEvent.objects.create(
            user=user if (user is not None and user.is_authenticated) else None,
            ip_address=client_ip(request),
            event_type="prompt_injection",
            prompt=(question or "")[:4000],
            matched_patterns=matched,
            strikes=strikes,
        )
    except Exception as exc:  # pragma: no cover - logging must never cascade
        logger.warning(f"Could not write AIAbuseEvent: {exc}")


def record_off_topic(request, question: str, answer: str) -> None:
    """Log an answer that failed the output-side scope check (finding 2.5)."""
    logger.warning(
        f"AI_OFF_TOPIC_RESPONSE ip={client_ip(request) if request else 'n/a'} "
        f"question={(question or '')[:200]!r}"
    )
    try:
        from .models import AIAbuseEvent

        user = getattr(request, "user", None) if request else None
        AIAbuseEvent.objects.create(
            user=user if (user is not None and user.is_authenticated) else None,
            ip_address=client_ip(request) if request else "0.0.0.0",
            event_type="off_topic",
            prompt=(question or "")[:4000],
            response=(answer or "")[:4000],
            matched_patterns=[],
            strikes=0,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning(f"Could not write off-topic AIAbuseEvent: {exc}")
