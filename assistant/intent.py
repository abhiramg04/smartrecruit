"""
assistant/intent.py — Intent Classification for SmartRecruit AI Recruitment Assistant.

Architecture:
  1. Fast rule-based pattern matching (no LLM cost)
  2. If ambiguous → Groq fast classification (single API call)

SECURITY: UNAUTHORIZED_ACTION intents are detected here and blocked BEFORE any LLM call.
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent Constants
# ---------------------------------------------------------------------------

class Intent:
    FIND_CANDIDATES      = 'FIND_CANDIDATES'
    EXPLAIN_RANKING      = 'EXPLAIN_RANKING'
    SUMMARIZE_CANDIDATE  = 'SUMMARIZE_CANDIDATE'
    MISSING_SKILLS       = 'MISSING_SKILLS'
    GENERATE_JD          = 'GENERATE_JD'
    GENERATE_QUESTIONS   = 'GENERATE_QUESTIONS'
    SUMMARIZE_INTERVIEWS = 'SUMMARIZE_INTERVIEWS'
    HIRING_GUIDANCE      = 'HIRING_GUIDANCE'
    DRAFT_COMMUNICATION  = 'DRAFT_COMMUNICATION'
    GENERAL_CHAT         = 'GENERAL_CHAT'
    UNAUTHORIZED_ACTION  = 'UNAUTHORIZED_ACTION'


@dataclass
class ClassifiedIntent:
    name: str
    confidence: float = 1.0
    entities: dict = field(default_factory=dict)
    raw_message: str = ''


# ---------------------------------------------------------------------------
# Rule-based patterns (fast, no API cost)
# ---------------------------------------------------------------------------

# UNAUTHORIZED first — must be checked before any other pattern
UNAUTHORIZED_PATTERNS = [
    r'\b(reject|decline|deny)\s+candidate',
    r'\bselect\s+candidate',
    r'\bhire\s+candidate',
    r'\bdelete\s+(candidate|user|applicant)',
    r'\bremove\s+(candidate|user|applicant)',
    r'\bchange\s+(role|permission|config)',
    r'\bmodify\s+(setting|configuration|security)',
    r'\bdisqualif',
    r'\bfire\s+(candidate|employee)',
    r'\bblacklist',
]

INTENT_PATTERNS = {
    Intent.FIND_CANDIDATES: [
        r'\b(find|show|list|get|fetch|who are the)\b.*(candidate|applicant)',
        r'\bbest\s+(candidate|applicant)',
        r'\btop\s+(candidate|applicant)',
        r'\brank(ed)?\s+(candidate|applicant)',
        r'\bcandidate.*for\b.*\bjob\b',
        r'\bsuitable\s+(candidate|applicant)',
    ],
    Intent.EXPLAIN_RANKING: [
        r'\bwhy\b.*\branked?\b',
        r'\bexplain\b.*\branking?\b',
        r'\bwhy\b.*\brank(ed)?\b.*\b(above|below|higher|lower)\b',
        r'\brank(ing)?\s+explanation',
        r'\bcompare\b.*\bcandidate',
        r'\bcandidate.*vs\b',
    ],
    Intent.SUMMARIZE_CANDIDATE: [
        r'\b(summarize|summary|profile|overview|about)\b.*(candidate|applicant)',
        r'\btell me about\b.*(candidate|applicant)',
        r'\bwho is\b',
        r'\bcandidate\s+profile',
        r'\bapplicant\s+summary',
    ],
    Intent.MISSING_SKILLS: [
        r'\b(missing|lack(ing)?|without)\b.*\b(skill|technology|tool)',
        r'\bskill\s+gap',
        r'\bwho.*doesn.t have\b',
        r'\bskill\b.*\bmissing\b',
        r'\b(candidate|applicant).*lacking\b',
    ],
    Intent.GENERATE_JD: [
        r'\bgenerate\b.*\bjob\s*description\b',
        r'\bcreate\b.*\bjob\s*(posting|description|listing)\b',
        r'\bwrite\b.*\bjob\s*description\b',
        r'\bdraft\b.*\bjob\s*(posting|description)\b',
        r'\bjob\s*description\b.*\bfor\b',
    ],
    Intent.GENERATE_QUESTIONS: [
        r'\bgenerate\b.*\b(interview\s+)?question',
        r'\bcreate\b.*\b(interview\s+)?question',
        r'\binterview\s+question',
        r'\bquestion\b.*\bfor\s*(this\s+)?(candidate|applicant|position|job)',
        r'\bask\b.*(candidate|applicant)',
    ],
    Intent.SUMMARIZE_INTERVIEWS: [
        r'\b(summarize|summary|recap|overview)\b.*\binterview',
        r'\btoday.s\s+interview',
        r'\binterview\s+summary',
        r'\binterview\s+report',
        r'\brecent\s+interview',
    ],
    Intent.HIRING_GUIDANCE: [
        r'\b(who|which\s+(candidate|applicant))\s+(should|do)\s+(i|we)\s+(hire|select|choose|pick)\b',
        r'\bhiring\s+(decision|recommendation|advice|guidance)',
        r'\bwho.s\s+the\s+best\s+fit\b',
        r'\bshould\s+i\s+hire\b',
        r'\bmy\s+(recommendation|advice)\b',
        r'\bbest\s+(fit|match|choice)\b',
    ],
    Intent.DRAFT_COMMUNICATION: [
        r'\b(draft|write|compose|create)\b.*(email|message|letter|communication)',
        r'\bnotif(y|ication)\b.*\bcandidate\b',
        r'\bcandidate.*\b(email|message)\b',
        r'\b(offer|rejection|feedback)\b.*\bemail\b',
    ],
}


class IntentClassifier:
    """
    Classifies recruiter messages into structured intents using pattern matching
    (fast) with optional Groq fallback for ambiguous queries.
    """

    @staticmethod
    def classify(message: str) -> ClassifiedIntent:
        """Main entry point. Returns ClassifiedIntent with name, confidence, entities."""
        if not message or not message.strip():
            return ClassifiedIntent(name=Intent.GENERAL_CHAT, confidence=1.0, raw_message=message)

        msg_lower = message.lower().strip()

        # 1. UNAUTHORIZED check first (safety gate)
        for pattern in UNAUTHORIZED_PATTERNS:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                logger.warning(f"[IntentClassifier] Unauthorized action detected: '{pattern}' in message")
                return ClassifiedIntent(
                    name=Intent.UNAUTHORIZED_ACTION,
                    confidence=1.0,
                    entities={'blocked_pattern': pattern},
                    raw_message=message
                )

        # 2. Rule-based pattern matching
        for intent_name, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, msg_lower, re.IGNORECASE):
                    entities = IntentClassifier._extract_entities(message, intent_name)
                    logger.info(f"[IntentClassifier] Pattern matched intent: {intent_name}")
                    return ClassifiedIntent(
                        name=intent_name,
                        confidence=0.85,
                        entities=entities,
                        raw_message=message
                    )

        # 3. Fallback: GENERAL_CHAT
        logger.info(f"[IntentClassifier] No pattern matched, defaulting to GENERAL_CHAT")
        return ClassifiedIntent(name=Intent.GENERAL_CHAT, confidence=0.6, raw_message=message)

    @staticmethod
    def _extract_entities(message: str, intent_name: str) -> dict:
        """Extract lightweight entity hints from the message text."""
        entities = {}
        msg_lower = message.lower()

        # Job title extraction hint
        job_patterns = [
            r'for\s+(a\s+)?([a-zA-Z][a-zA-Z\s/+#.]{2,40}?)\s+(developer|engineer|designer|analyst|manager|lead|architect)',
            r'([a-zA-Z][a-zA-Z\s/+#.]{2,40}?)\s+position',
            r'([a-zA-Z][a-zA-Z\s/+#.]{2,40}?)\s+role',
        ]
        for pat in job_patterns:
            m = re.search(pat, message, re.IGNORECASE)
            if m:
                entities['job_hint'] = m.group(0).strip()
                break

        # Skill extraction hint
        skill_patterns = [r'(?:missing|lacking|without|need)\s+([a-zA-Z][a-zA-Z0-9\s+#._-]{1,30})']
        for pat in skill_patterns:
            m = re.search(pat, msg_lower)
            if m:
                entities['skill_hint'] = m.group(1).strip()
                break

        # Candidate name hints (capitalized words not at sentence start)
        if intent_name in (Intent.SUMMARIZE_CANDIDATE, Intent.EXPLAIN_RANKING, Intent.GENERATE_QUESTIONS, Intent.DRAFT_COMMUNICATION):
            # Look for quoted names or capitalized multi-word names
            name_m = re.search(r'"([^"]+)"', message) or re.search(r"'([^']+)'", message)
            if name_m:
                entities['candidate_name_hint'] = name_m.group(1)

        return entities
