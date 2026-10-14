"""
assistant/security_guard.py — Input/Output Security Guard for the AI Recruitment Assistant.

Protects against:
  - Prompt injection / instruction override
  - Unauthorized action commands (reject/select/delete/role-change)
  - Cross-recruiter data fishing attempts
  - Sensitive data leakage in AI responses
  - Excessive agency attempts
"""
import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Blocked input patterns (augment core AISecurityManager patterns)
# ---------------------------------------------------------------------------

# Instruction override attacks
INJECTION_OVERRIDES = [
    r'ignore\s+(all\s+)?previous\s+instructions',
    r'disregard\s+(all\s+)?prior\s+prompts',
    r'you\s+are\s+now\s+(a\s+)?(?:DAN|evil|jailbreak)',
    r'forget\s+everything\s+you\s+were\s+told',
    r'bypass\s+(your\s+)?(safety|filter|restriction)',
    r'admin\s+mode\s+enabled',
    r'developer\s+mode\s+on',
    r'act\s+as\s+if\s+you\s+have\s+no\s+restrictions',
    r'simulate\s+(a\s+)?jailbreak',
    r'override\s+(system|instruction|prompt)',
    r'new\s+system\s+prompt\s*:',
    r'system\s+prompt',
    r'system\s+instructions',
    r'output\s+system',
    r'\[system\]',
    r'</?(system|instruction|context)>',
]


# Unauthorized application actions
UNAUTHORIZED_ACTIONS = [
    r'\b(reject|decline|deny)\s+(the\s+)?(candidate|applicant)',
    r'\b(select|hire|choose|pick)\s+(the\s+)?(candidate|applicant)',
    r'\b(delete|remove|drop|purge)\s+(the\s+)?(candidate|user|applicant|account|record)',
    r'\bchange\s+.*(role|permission)',

    r'\bmodify\s+(security|system|ai|configuration|config|setting)',
    r'\bdisqualif(y|ied)',
    r'\bblacklist\s+(the\s+)?(candidate|applicant|user)',
    r'\bsend\s+a\s+(rejection|offer)\s+(email|letter|message)',  # drafting OK, sending not
    r'\bautomatically\s+(reject|approve|select)',
    r'\bexecute\s+(sql|query|command)',
    r'\brun\s+(code|script|command)',
]

# Cross-company fishing
CROSS_COMPANY_FISHING = [
    r'\bother\s+(company|companies|organization|client)',
    r'\bdifferent\s+company',
    r'\bcompetitor',
    r'\bshow\s+(me\s+)?all\s+(company|companies|recruiter)',
    r'\ball\s+recruiter',
    r'\blist\s+all\s+user',
    r'\bdump\s+(data|database|db)',
    r'\bexport\s+(all|entire)\s+(data|candidate|database)',
]

# Patterns that should be stripped/blocked from AI OUTPUT
RESPONSE_LEAK_PATTERNS = [
    r'gsk_[a-zA-Z0-9_-]{20,}',        # Groq API keys
    r'sk-[a-zA-Z0-9]{20,}',           # OpenAI keys
    r'bearer\s+[a-zA-Z0-9_\-\.]{20,}', # Bearer tokens
    r'password\s*[:=]\s*\S+',          # Passwords
    r'secret\s*[:=]\s*\S+',            # Secrets
    r'\bDIRECT\s+DATABASE\s+ACCESS\b',
    r'\bSQL\s+QUERY\b',
]


class AssistantSecurityGuard:
    """
    Pre-LLM and post-LLM security validation for the AI Recruitment Assistant.
    All checks are deterministic (no LLM calls). Fast and cheap.
    """

    @classmethod
    def check_input(cls, message: str) -> Tuple[bool, str]:
        """
        Validates recruiter input BEFORE sending to LLM or tools.
        Returns (is_safe: bool, reason: str).
        Safe = True means the message can proceed.
        """
        if not message or not message.strip():
            return False, "Empty message."

        if len(message) > 4000:
            return False, "Message too long (max 4000 characters)."

        msg_lower = message.lower()

        # 1. Injection override check
        for pattern in INJECTION_OVERRIDES:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                logger.warning(f"[SecurityGuard] Prompt injection attempt blocked: '{pattern}'")
                return False, "prompt_injection"

        # 2. Unauthorized action check
        for pattern in UNAUTHORIZED_ACTIONS:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                logger.warning(f"[SecurityGuard] Unauthorized action attempt blocked: '{pattern}'")
                return False, "unauthorized_action"

        # 3. Cross-company fishing
        for pattern in CROSS_COMPANY_FISHING:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                logger.warning(f"[SecurityGuard] Cross-company fishing attempt blocked: '{pattern}'")
                return False, "cross_company_access"

        return True, "ok"

    @classmethod
    def check_output(cls, response: str) -> Tuple[bool, str]:
        """
        Validates AI response BEFORE returning to the user.
        Strips/blocks accidental leakage of secrets or system internals.
        Returns (is_safe: bool, cleaned_response: str).
        """
        if not response:
            return True, response

        cleaned = response
        for pattern in RESPONSE_LEAK_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                logger.error(f"[SecurityGuard] Sensitive data detected in AI response — redacting: '{pattern}'")
                cleaned = re.sub(pattern, '[REDACTED]', cleaned, flags=re.IGNORECASE)

        return True, cleaned

    @classmethod
    def get_refusal_message(cls, reason: str) -> str:
        """Returns a safe, helpful refusal message for blocked requests."""
        refusals = {
            "prompt_injection": (
                "⚠️ I noticed your message contains instructions that could override my guidelines. "
                "I'm designed to assist with recruitment tasks only. "
                "Please rephrase your question — I'm happy to help with candidate analysis, job descriptions, and more!"
            ),
            "unauthorized_action": (
                "🔒 I can help you **understand** and **prepare** actions, but I can't directly perform operations "
                "like rejecting, selecting, or deleting candidates. "
                "Those decisions require your explicit action through the SmartRecruit portal to ensure proper authorization.\n\n"
                "Here's what I **can** do:\n"
                "- Summarize a candidate's profile\n"
                "- Explain ranking and scoring\n"
                "- Draft a communication email for your review\n"
                "- Provide hiring guidance and recommendations"
            ),
            "cross_company_access": (
                "🔒 I can only access data within your authorized company's recruitment pipeline. "
                "I'm unable to access other organizations' data."
            ),
            "empty": "Please type a message and I'll be happy to help!",
        }
        return refusals.get(reason, "I'm unable to process that request. Please try rephrasing.")
