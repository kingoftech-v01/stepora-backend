"""
Content moderation service for Stepora.

Three-tier moderation:
1. Jailbreak/role-play pattern detection (regex, instant, no API call)
2. Harmful dream content detection (regex, instant)
3. OpenAI Moderation API (multilingual catch-all)

All moderation events are logged via core.audit for admin review.
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")


@dataclass
class ModerationResult:
    """Result of a content moderation check."""

    is_flagged: bool = False
    categories: list = field(default_factory=list)
    severity: str = "none"  # none, low, medium, high
    user_message: str = ""
    raw_scores: dict = field(default_factory=dict)
    detection_source: str = (
        ""  # 'openai_api', 'jailbreak_pattern', 'dream_content', 'roleplay'
    )


# ---------------------------------------------------------------------------
# Friendly, non-aggressive rejection messages (English only per user request)
# ---------------------------------------------------------------------------
REJECTION_MESSAGES = {
    "harmful_content": (
        "I appreciate you sharing, but I can only help with positive, "
        "constructive goals that contribute to your personal growth. "
        "Could you tell me about a dream that focuses on a healthy, "
        "achievable objective?"
    ),
    "sexual_content": (
        "I'm here to help with personal development goals. This type of "
        "content falls outside what I can assist with. Let's focus on a "
        "dream that helps you grow as a person."
    ),
    "relationship_coercion": (
        "I understand relationships are important, but I can't help with "
        "goals that involve controlling or forcing another person's choices. "
        "I'd love to help you with goals like improving your social skills, "
        "building confidence, or developing healthy relationship habits."
    ),
    "self_harm": (
        "I care about your well-being. I'm not able to help with this type of request, "
        "but I strongly encourage you to reach out to a mental health professional "
        "or a trusted person in your life. You deserve support."
    ),
    "jailbreak_attempt": (
        "I'm Stepora, your personal goal-planning assistant. "
        "I can't take on other roles or personas. "
        "How can I help you with your dreams and goals today?"
    ),
    "roleplay_attempt": (
        "I appreciate the creativity, but I need to stay in my role as "
        "Stepora to best help you. Let's focus on turning your real "
        "dreams into actionable plans."
    ),
    "illegal_content": (
        "I can only assist with legal and ethical goals. "
        "Let's redirect toward something positive — what constructive "
        "dream would you like to work on?"
    ),
    "generic_violation": (
        "I wasn't able to process that request. Could you tell me about "
        "a personal goal or dream you'd like to work toward? I'm here to "
        "help with health, career, education, creative, and personal growth goals."
    ),
}


# ---------------------------------------------------------------------------
# Jailbreak detection patterns (compiled for performance)
# ---------------------------------------------------------------------------
JAILBREAK_PATTERNS = [
    # Direct instruction override (EN + FR)
    re.compile(
        r"ignore\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|rules?|prompts?|guidelines?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(disregard|forget|override)\s+(all\s+)?(your\s+)?(previous|prior|above)?\s*"
        r"(instructions?|rules?|prompts?|guidelines?|restrictions?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(ignore|oublie|ignorer)\s+(tes|vos|les)\s+(instructions?|r[eè]gles?|consignes?)",
        re.IGNORECASE,
    ),
    # DAN / persona injection
    re.compile(r"\bDAN\b.*\b(mode|jailbreak|prompt)\b", re.IGNORECASE),
    re.compile(
        r"you\s+are\s+now\s+(a\s+)?(?!stepora|my\s+coach|motivated|focused|disciplined)",
        re.IGNORECASE,
    ),
    re.compile(
        r"from\s+now\s+on\s+you\s+(are|will\s+be|must)\s+",
        re.IGNORECASE,
    ),
    re.compile(r"switch\s+to\s+.*\bmode\b", re.IGNORECASE),
    re.compile(r"enter\s+.*\bmode\b", re.IGNORECASE),
    re.compile(r"activate\s+.*\bmode\b", re.IGNORECASE),
    # System prompt extraction
    re.compile(
        r"(show|reveal|print|display|output|repeat|tell)\s+(me\s+)?(your\s+)?"
        r"(system\s+prompt|instructions|initial\s+prompt|rules)",
        re.IGNORECASE,
    ),
    re.compile(r"what\s+(are|were)\s+your\s+(system\s+)?instructions", re.IGNORECASE),
    # Encoding bypass attempts
    re.compile(r"respond\s+in\s+(base64|binary|hex|morse|rot13)", re.IGNORECASE),
    re.compile(
        r"(encode|translate)\s+(your\s+)?(response|answer|output)\s+(in|to)\s+(base64|hex|binary)",
        re.IGNORECASE,
    ),
    # Hypothetical framing for bypass
    re.compile(
        r"hypothetically.*\b(if|what\s+if)\b.*\b(no\s+rules|no\s+restrictions|no\s+limits|anything)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"in\s+a\s+(fictional|hypothetical|imaginary)\s+(world|scenario|universe).*\b(how|can|would)\b",
        re.IGNORECASE,
    ),
]


# ---------------------------------------------------------------------------
# Role-play detection patterns
# ---------------------------------------------------------------------------
ROLEPLAY_PATTERNS = [
    re.compile(
        r"(pretend|imagine|suppose|assume)\s+(you\s+are|you\'re|to\s+be)\s+",
        re.IGNORECASE,
    ),
    re.compile(
        r"(pr[eé]tends?|imagine)\s+(que\s+)?tu\s+(es|sois)\s+", re.IGNORECASE
    ),  # FR
    re.compile(r"role\s*-?\s*play\s+as\b", re.IGNORECASE),
    re.compile(
        r"act\s+as\s+(if\s+you\s+are|though\s+you|a)\s+(?!motivated|focused|disciplined)",
        re.IGNORECASE,
    ),
    re.compile(
        r"you\s+are\s+(my|a)\s+(girlfriend|boyfriend|therapist|doctor|lawyer|hacker|evil|villain)",
        re.IGNORECASE,
    ),
    re.compile(
        r"adopt\s+the\s+(role|persona|character|identity)\s+of\b", re.IGNORECASE
    ),
    re.compile(r"channel\s+(the\s+)?(spirit|energy|persona)\s+of\b", re.IGNORECASE),
    re.compile(
        r"be\s+my\s+(girlfriend|boyfriend|friend|lover|partner|therapist|doctor|slave)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(sois|deviens)\s+(mon|ma|un|une)\s+", re.IGNORECASE
    ),  # FR: "sois ma copine"
]


# ---------------------------------------------------------------------------
# Harmful dream content patterns
# ---------------------------------------------------------------------------
HARMFUL_DREAM_PATTERNS_VIOLENCE = [
    re.compile(
        r"\b(kill|murder|assassinate|harm|hurt|attack|stab|shoot|poison|kidnap|torture|beat\s+up|strangle)\b"
        r".*\b(someone|person|people|him|her|them|my|a\s+man|a\s+woman)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(tuer|assassiner|poignarder|empoisonner|torturer|kidnapper|frapper)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(revenge|vengeance|get\s+back\s+at|make\s+.*\s+pay|destroy\s+.*\s+life)\b",
        re.IGNORECASE,
    ),
]

HARMFUL_DREAM_PATTERNS_SEXUAL = [
    re.compile(
        r"\b(sex\s+with|sleep\s+with|seduce|have\s+sex|sexual\s+fantasy|erotic|pornograph|nude|naked)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(coucher\s+avec|s[eé]duire|fantasme\s+sexuel|[eé]rotique|pornograph|nu[es]?)\b",
        re.IGNORECASE,
    ),
]

HARMFUL_DREAM_PATTERNS_COERCION = [
    re.compile(
        r"\b(make|force|trick|manipulate|coerce)\s+.*\b(love\s+me|marry\s+me|date\s+me|be\s+with\s+me|like\s+me|want\s+me)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(forcer|obliger|manipuler)\s+.*\b(m\'aimer|me\s+marier|sortir\s+avec\s+moi)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bstalk(ing)?\b.*\b(someone|person|him|her|them|my\s+ex)\b", re.IGNORECASE
    ),
    re.compile(
        r"\b(marry|épouser)\b.*\b(without\s+(her|his)\s+consent|de\s+force|par\s+la\s+force)\b",
        re.IGNORECASE,
    ),
]

HARMFUL_DREAM_PATTERNS_SELF_HARM = [
    re.compile(
        r"\b(suicide|kill\s+myself|end\s+my\s+life|self[- ]?harm|cut\s+myself)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(me\s+suicider|mettre\s+fin\s+[àa]\s+m(a|es)\s+jour|me\s+faire\s+du\s+mal)\b",
        re.IGNORECASE,
    ),
]

HARMFUL_DREAM_PATTERNS_ILLEGAL = [
    re.compile(
        r"\b(steal|rob|hack\s+into|break\s+into|forge|counterfeit|drug\s+deal|sell\s+drugs|traffic)\b",
        re.IGNORECASE,
    ),
    # FR: "voler" means both "to fly" and "to steal" — require theft context
    # to avoid false positives on dreams about flying.
    re.compile(
        r"\b(cambrioler|pirater|falsifier|vendre\s+de\s+la\s+drogue|trafic\s+de\s+|trafiquant)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bvoler\s+(quelqu|qqch|de\s+l\'argent|dans\s+(un|une|le|la|les)\s)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(scam|fraud|con\s+someone|deceive|catfish|impersonate)\b", re.IGNORECASE
    ),
    re.compile(r"\b(arnaquer|frauder|escroquer|usurper|d[eé]rober)\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------


class ContentModerationService:
    """
    Central moderation service. Call moderate_text() or moderate_dream()
    at every input boundary.
    """

    def __init__(self):
        mod_settings = getattr(settings, "CONTENT_MODERATION", {})
        self._openai_enabled = mod_settings.get("OPENAI_MODERATION_ENABLED", True)
        self._patterns_enabled = mod_settings.get("CUSTOM_PATTERNS_ENABLED", True)
        self._cache_ttl = mod_settings.get("MODERATION_CACHE_TTL", 300)
        self._enabled = mod_settings.get("ENABLED", True)

    def moderate_text(self, text: str, context: str = "chat") -> ModerationResult:
        """
        Full moderation pipeline for any text input.

        Args:
            text: The user-provided text to check.
            context: 'chat', 'dream_title', 'dream_description', 'calibration_answer', 'ai_output'

        Returns:
            ModerationResult with flagged status and user-friendly message.
        """
        if not self._enabled or not text or not text.strip():
            return ModerationResult()

        text = text.strip()

        # Check cache
        cache_key = f"moderation:{hashlib.sha256(text.encode()).hexdigest()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = self._run_checks(text, context)

        # Cache the result
        cache.set(cache_key, result, timeout=self._cache_ttl)

        return result

    def moderate_dream(self, title: str, description: str) -> ModerationResult:
        """Specialized moderation for dream creation/update."""
        title_result = self.moderate_text(title, context="dream_title")
        if title_result.is_flagged:
            return title_result

        if description:
            desc_result = self.moderate_text(description, context="dream_description")
            if desc_result.is_flagged:
                return desc_result

        return ModerationResult()

    def _run_checks(self, text: str, context: str) -> ModerationResult:
        """Run all moderation tiers in order."""

        if self._patterns_enabled:
            # Tier A: Jailbreak patterns
            result = self._check_jailbreak_patterns(text)
            if result.is_flagged:
                self._log_event(text, result, context)
                return result

            # Tier A: Role-play patterns
            result = self._check_roleplay_patterns(text)
            if result.is_flagged:
                self._log_event(text, result, context)
                return result

            # Tier B: Harmful dream content (for all contexts except ai_output which uses simpler check)
            result = self._check_harmful_dream_patterns(text)
            if result.is_flagged:
                self._log_event(text, result, context)
                return result

        # Tier C: OpenAI Moderation API
        if self._openai_enabled:
            result = self._check_openai_moderation(text)
            if result.is_flagged:
                self._log_event(text, result, context)
                return result

        return ModerationResult()

    def _check_openai_moderation(self, text: str) -> ModerationResult:
        """Call OpenAI Moderation API (language-agnostic)."""
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.OPENAI_API_KEY or "sk-placeholder",
                organization=getattr(settings, "OPENAI_ORGANIZATION_ID", None),
            )

            response = client.moderations.create(
                input=text,
                model="omni-moderation-latest",
            )
            result = response.results[0]

            if result.flagged:
                categories = []
                scores = {}

                for cat_name in vars(result.categories):
                    if cat_name.startswith("_"):
                        continue
                    flagged = getattr(result.categories, cat_name, False)
                    score = getattr(result.category_scores, cat_name, 0)
                    if flagged:
                        categories.append(cat_name)
                    scores[cat_name] = score

                user_msg = self._get_rejection_message_for_categories(categories)

                return ModerationResult(
                    is_flagged=True,
                    categories=categories,
                    severity="high",
                    user_message=user_msg,
                    raw_scores=scores,
                    detection_source="openai_api",
                )

            return ModerationResult()

        except Exception as e:
            # Fail OPEN: pattern checks already caught obvious attacks
            logger.error("OpenAI Moderation API error: %s", e)
            return ModerationResult()

    def _check_jailbreak_patterns(self, text: str) -> ModerationResult:
        """Check for jailbreak/prompt injection patterns."""
        for pattern in JAILBREAK_PATTERNS:
            if pattern.search(text):
                return ModerationResult(
                    is_flagged=True,
                    categories=["jailbreak"],
                    severity="high",
                    user_message=REJECTION_MESSAGES["jailbreak_attempt"],
                    detection_source="jailbreak_pattern",
                )
        return ModerationResult()

    def _check_roleplay_patterns(self, text: str) -> ModerationResult:
        """Check for role-play attempt patterns."""
        for pattern in ROLEPLAY_PATTERNS:
            if pattern.search(text):
                return ModerationResult(
                    is_flagged=True,
                    categories=["roleplay"],
                    severity="medium",
                    user_message=REJECTION_MESSAGES["roleplay_attempt"],
                    detection_source="roleplay",
                )
        return ModerationResult()

    def _check_harmful_dream_patterns(self, text: str) -> ModerationResult:
        """Check for harmful dream content patterns."""
        # Self-harm (check first for appropriate response)
        for pattern in HARMFUL_DREAM_PATTERNS_SELF_HARM:
            if pattern.search(text):
                return ModerationResult(
                    is_flagged=True,
                    categories=["self_harm"],
                    severity="high",
                    user_message=REJECTION_MESSAGES["self_harm"],
                    detection_source="dream_content",
                )

        # Violence
        for pattern in HARMFUL_DREAM_PATTERNS_VIOLENCE:
            if pattern.search(text):
                return ModerationResult(
                    is_flagged=True,
                    categories=["violence"],
                    severity="high",
                    user_message=REJECTION_MESSAGES["harmful_content"],
                    detection_source="dream_content",
                )

        # Sexual content
        for pattern in HARMFUL_DREAM_PATTERNS_SEXUAL:
            if pattern.search(text):
                return ModerationResult(
                    is_flagged=True,
                    categories=["sexual"],
                    severity="high",
                    user_message=REJECTION_MESSAGES["sexual_content"],
                    detection_source="dream_content",
                )

        # Relationship coercion
        for pattern in HARMFUL_DREAM_PATTERNS_COERCION:
            if pattern.search(text):
                return ModerationResult(
                    is_flagged=True,
                    categories=["coercion"],
                    severity="high",
                    user_message=REJECTION_MESSAGES["relationship_coercion"],
                    detection_source="dream_content",
                )

        # Illegal activity
        for pattern in HARMFUL_DREAM_PATTERNS_ILLEGAL:
            if pattern.search(text):
                return ModerationResult(
                    is_flagged=True,
                    categories=["illegal"],
                    severity="high",
                    user_message=REJECTION_MESSAGES["illegal_content"],
                    detection_source="dream_content",
                )

        return ModerationResult()

    def _get_rejection_message_for_categories(self, categories: list) -> str:
        """Map OpenAI moderation categories to user-friendly rejection messages."""
        cat_set = set(categories)

        if cat_set & {"sexual", "sexual/minors"}:
            return REJECTION_MESSAGES["sexual_content"]
        if cat_set & {"violence", "violence/graphic"}:
            return REJECTION_MESSAGES["harmful_content"]
        if cat_set & {"self-harm", "self-harm/intent", "self-harm/instructions"}:
            return REJECTION_MESSAGES["self_harm"]
        if cat_set & {"harassment", "harassment/threatening"}:
            return REJECTION_MESSAGES["harmful_content"]
        if cat_set & {"illicit", "illicit/violent"}:
            return REJECTION_MESSAGES["illegal_content"]

        return REJECTION_MESSAGES["generic_violation"]

    def _log_event(self, text: str, result: ModerationResult, context: str):
        """Log moderation event for admin review."""
        truncated = text[:300]
        security_logger.warning(
            "CONTENT_MODERATION context=%s source=%s categories=%s severity=%s text=%.300s",
            context,
            result.detection_source,
            ",".join(result.categories),
            result.severity,
            truncated,
        )
