"""
Output-side scope enforcement for the public AI assistant (audit finding 2.5).

The existing intent classifier only inspects the *incoming* question, which is
why the audit's "I am researching how health and lifestyle affected creative
performance…" framing succeeded: the question genuinely reads as health-related,
so the input gate opened, and nothing then checked that the answer stayed inside
the healthcare scope.

This module inspects the generated answer before it reaches the user. Two
layers, cheapest first:

  1. A keyword heuristic that catches the obvious cases with no API cost.
  2. An LLM classifier for anything the heuristic cannot decide.

Fails open — if the classifier errors, the original answer is returned rather
than blocking a legitimate health question on an infrastructure fault.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional

from loguru import logger

REFUSAL_MESSAGE = (
    "I'm a health assistant, so I can only help with health and medical "
    "topics — symptoms, conditions, medications, wellness, and finding care. "
    "That question falls outside what I can cover. Is there a health question "
    "I can help you with? 🏥"
)

# Domains the assistant must never expand into, however the question is framed.
OFF_TOPIC_MARKERS = [
    # Entertainment / celebrity
    r"\b(discography|album|billboard|grammy|box office|filmography)\b",
    r"\b(pop culture|music (history|industry|video)|chart-topping)\b",
    # Politics / religion
    r"\b(election|political party|parliament|presidential campaign)\b",
    # Finance / trading
    r"\b(stock market|cryptocurrency|bitcoin|investment portfolio|forex)\b",
    # Software / homework help
    r"\b(python|javascript|sql query|source code|def |function\s*\()\b",
    # Assistant internals — leaking configuration
    r"\b(my system prompt|my instructions are|i (was|am) (instructed|configured|programmed) to)\b",
]

OFF_TOPIC_RE = [re.compile(p, re.IGNORECASE) for p in OFF_TOPIC_MARKERS]

# Health vocabulary. Presence of these alongside an off-topic marker means the
# answer is probably a legitimate health answer that merely mentions an example.
HEALTH_MARKERS = re.compile(
    r"\b(symptom|diagnos|treatment|medication|dose|prescri|patient|clinic|"
    r"doctor|nurse|hospital|pharmac|disease|infection|blood pressure|"
    r"diabetes|nutrition|exercise|mental health|therapy|vaccine|wellness|"
    r"health|medical|pain|fever|injury|screening)\b",
    re.IGNORECASE,
)


@dataclass
class ScopeVerdict:
    in_scope: bool
    reason: str = ""
    checked_by: str = "heuristic"


def _heuristic(answer: str) -> Optional[ScopeVerdict]:
    """
    Cheap first pass. Returns None when the heuristic cannot decide and the
    LLM classifier should be consulted.
    """
    text = answer or ""
    if not text.strip():
        return ScopeVerdict(in_scope=True, reason="empty answer")

    hits = [p.pattern for p in OFF_TOPIC_RE if p.search(text)]
    if not hits:
        return ScopeVerdict(in_scope=True, reason="no off-topic markers")

    health_hits = len(HEALTH_MARKERS.findall(text))
    if health_hits >= 3:
        # Dense health vocabulary alongside a passing reference — ambiguous,
        # escalate rather than guessing.
        return None

    return ScopeVerdict(
        in_scope=False,
        reason=f"off-topic markers with weak health context: {hits[:3]}",
    )


CLASSIFIER_PROMPT = """You are a strict scope classifier for a healthcare assistant.

The assistant is ONLY permitted to discuss: health, medicine, symptoms, \
conditions, treatments, medications, nutrition, fitness, mental health, \
healthcare services, appointments, and the assistant's own capabilities.

It is NOT permitted to discuss anything else — including entertainment, \
celebrities, music, sport, politics, finance, programming, or general trivia — \
even when the user frames the request as research, comparison, or a study.

Judge the ASSISTANT RESPONSE below, not the user's question. A response is \
out of scope if a substantial part of it delivers non-health content, even if \
it also contains health content.

USER QUESTION: {question}

ASSISTANT RESPONSE: {answer}

Reply with JSON only:
{{"in_scope": true/false, "reason": "<short explanation>"}}"""


def check_response_scope(
    question: str,
    answer: str,
    llm=None,
) -> ScopeVerdict:
    """
    Validate that a generated answer stayed inside the healthcare scope.

    `llm` is any LangChain chat model; when omitted only the heuristic runs.
    """
    verdict = _heuristic(answer)
    if verdict is not None:
        return verdict

    if llm is None:
        # Ambiguous and nothing to escalate to — allow, and rely on logging.
        return ScopeVerdict(in_scope=True, reason="ambiguous, no classifier available")

    try:
        response = llm.invoke(
            CLASSIFIER_PROMPT.format(
                question=(question or "")[:1000],
                answer=(answer or "")[:4000],
            )
        )
        raw = (response.content or "").strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"classifier returned no JSON: {raw[:200]}")

        data = json.loads(raw[start : end + 1])
        return ScopeVerdict(
            in_scope=bool(data.get("in_scope", True)),
            reason=str(data.get("reason", ""))[:300],
            checked_by="llm",
        )
    except Exception as exc:
        # Fail open: an outage must not silence legitimate health answers.
        logger.error(f"Scope classifier failed, allowing response: {exc}")
        return ScopeVerdict(in_scope=True, reason="classifier error", checked_by="error")
