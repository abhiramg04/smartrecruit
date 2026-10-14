"""
AI Security & Prompt Injection Protection Module for SmartRecruit.

Protects against:
- Prompt injection & instruction override attacks
- Disclosure of sensitive API keys or system credentials
- Insecure AI output structures
"""

import re
import json
import logging
from typing import Type, TypeVar, Any
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

# Known prompt injection patterns
INJECTION_PATTERNS = [
    r'ignore\s+(all\s+)?previous\s+instructions',
    r'disregard\s+(all\s+)?prior\s+prompts',
    r'system\s*:\s*override',
    r'you\s+are\s+now\s+a\s+DAN',
    r'forget\s+everything\s+you\s+were\s+told',
    r'bypass\s+safety\s+filter',
    r'admin\s+mode\s+enabled',
]

# Sensitive pattern scrubbers (API keys, secrets, auth tokens)
SENSITIVE_PATTERNS = [
    r'gsk_[a-zA-Z0-9_-]{20,}',               # Groq API keys
    r'sk-[a-zA-Z0-9]{20,}',                  # OpenAI API keys
    r'bearer\s+[a-zA-Z0-9_\-\.]{20,}',       # Bearer tokens
    r'password\s*=\s*[\'"][^\'"]+[\'"]',      # Hardcoded passwords
]


class AISecurityManager:
    """Provides input sanitization, sensitive data redaction, and output schema validation."""

    @staticmethod
    def sanitize_prompt_input(text: str) -> str:
        """
        Sanitizes user input to prevent prompt injection and instruction overrides.
        """
        if not text:
            return ""

        sanitized = text
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                logger.warning(f"Potential prompt injection detected and neutralised: '{pattern}'")
                sanitized = re.sub(pattern, '[REDACTED_INSTRUCTION]', sanitized, flags=re.IGNORECASE)

        return sanitized.strip()

    @staticmethod
    def redact_sensitive_info(text: str) -> str:
        """
        Redacts API keys, secrets, and auth tokens before including text in LLM prompts.
        """
        if not text:
            return ""

        redacted = text
        for pattern in SENSITIVE_PATTERNS:
            redacted = re.sub(pattern, '[REDACTED_SECRET]', redacted, flags=re.IGNORECASE)

        return redacted

    @staticmethod
    def validate_ai_output(raw_content: str, schema: Type[T]) -> T:
        """
        Validates raw JSON string output from LLMs against a expected Pydantic schema.
        Strips markdown code blocks if present.
        """
        if not raw_content:
            raise ValueError("Empty LLM response received.")

        # Strip markdown formatting if present
        clean_text = re.sub(r'```(?:json)?', '', raw_content).strip().rstrip('`').strip()

        try:
            parsed_json = json.loads(clean_text)
            return schema.model_validate(parsed_json)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}\nRaw output: {raw_content[:200]}")
            raise ValueError(f"AI response was not valid JSON: {e}")
        except ValidationError as e:
            logger.error(f"LLM output violated schema contract: {e.json()}")
            raise
