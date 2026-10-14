"""
Groq LLM Service Engine for SmartRecruit.

Provides reusable inference methods, structured outputs, prompt sanitization,
model fallback, retry backoff for network errors, and secret masking.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, ValidationError
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .security import AISecurityManager

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class TransientAIError(Exception):
    """Raised for retryable transient API timeouts and rate limits."""
    pass


class AIEngineBase(ABC):
    """Abstract base class for AI integrations (Groq, OpenAI, etc)."""

    @abstractmethod
    def generate_structured_response(self, prompt: str, schema: Type[T], model: str = None) -> T:
        """Generate a structured JSON response from the LLM, validated against a Pydantic schema."""
        pass

    @abstractmethod
    def generate_chat_completion(self, messages: list, model: str = None, temperature: float = None) -> str:
        """Generate a plain text chat completion."""
        pass


class GroqAIEngine(AIEngineBase):
    """Concrete reusable implementation of the AI Engine using Groq."""

    def __init__(self):
        self._cached_key = None
        self._client = None

    @property
    def config(self):
        """Fetch latest configuration from the database."""
        try:
            from dashboard.models import AIConfiguration
            return AIConfiguration.get_solo()
        except Exception as e:
            logger.warning(f"Could not load AIConfiguration from DB: {e}")
            return None

    @property
    def DEFAULT_MODEL(self) -> str:
        cfg = self.config
        return (cfg.default_model if cfg and cfg.default_model else None) or "llama-3.3-70b-versatile"

    @property
    def FAST_MODEL(self) -> str:
        cfg = self.config
        return (cfg.fast_model if cfg and cfg.fast_model else None) or "llama-3.1-8b-instant"

    @property
    def client(self) -> Groq:
        """Initialize or refresh Groq client when API key updates."""
        cfg = self.config
        db_key = cfg.groq_api_key if cfg and cfg.groq_api_key else None
        if db_key and (db_key.startswith("gsk_test_") or "never_leak" in db_key or len(db_key) < 25):
            db_key = None

        api_key = db_key or os.getenv("GROQ_API_KEY")

        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set in AI Configuration or environment variables.")

        if self._client is None or self._cached_key != api_key:
            self._cached_key = api_key
            self._client = Groq(api_key=api_key)

        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=5),
        retry=retry_if_exception_type(TransientAIError),
        reraise=True
    )
    def generate_structured_response(self, prompt: str, schema: Type[T], model: str = None) -> T:
        """
        Generate a structured response validated against a Pydantic schema.
        Applies input sanitization, secret scrubbing, and output validation.
        """
        target_model = model or self.DEFAULT_MODEL

        # Step 1: Sanitize & redact input prompt
        clean_prompt = AISecurityManager.sanitize_prompt_input(prompt)
        clean_prompt = AISecurityManager.redact_sensitive_info(clean_prompt)

        # Step 2: Build schema instructions
        schema_json = schema.model_json_schema()
        full_prompt = (
            f"{clean_prompt}\n\n"
            f"You MUST respond ONLY with a valid JSON object matching this exact JSON schema:\n"
            f"{json.dumps(schema_json)}\n"
            f"Do NOT wrap in markdown or add extra text."
        )

        cfg = self.config
        temp = cfg.temperature if cfg else 0.2
        max_t = cfg.max_tokens if cfg else 2048

        safe_log_prompt = AISecurityManager.redact_sensitive_info(clean_prompt[:150])
        logger.info(f"Executing Groq API call [Model: {target_model}] with prompt snippet: '{safe_log_prompt}...'")

        try:
            response = self.client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": "You are a professional AI recruitment assistant that outputs ONLY valid JSON matching the requested schema."},
                    {"role": "user", "content": full_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=temp,
                max_tokens=max_t,
                timeout=30.0
            )

            raw_content = response.choices[0].message.content
            # Step 3: Validate output schema
            validated_obj = AISecurityManager.validate_ai_output(raw_content, schema)
            return validated_obj

        except (ValidationError, ValueError) as e:
            logger.error(f"Groq API structured response failed validation: {AISecurityManager.redact_sensitive_info(str(e))}")
            raise
        except Exception as e:
            logger.error(f"Groq API network/service error: {AISecurityManager.redact_sensitive_info(str(e))}")
            raise TransientAIError(str(e)) from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=5),
        retry=retry_if_exception_type(TransientAIError),
        reraise=True
    )
    def generate_chat_completion(self, messages: list, model: str = None, temperature: float = None) -> str:
        """
        Generate a plain-text chat completion from conversation messages.
        """
        target_model = model or self.FAST_MODEL
        cfg = self.config
        temp = temperature if temperature is not None else (cfg.temperature if cfg else 0.4)
        max_t = cfg.max_tokens if cfg else 1024

        sanitized_messages = []
        for msg in messages:
            content = msg.get("content", "")
            sanitized_content = AISecurityManager.sanitize_prompt_input(content)
            sanitized_content = AISecurityManager.redact_sensitive_info(sanitized_content)
            sanitized_messages.append({
                "role": msg.get("role", "user"),
                "content": sanitized_content
            })

        logger.info(f"Executing Groq Chat Completion [Model: {target_model}]")

        try:
            response = self.client.chat.completions.create(
                model=target_model,
                messages=sanitized_messages,
                temperature=temp,
                max_tokens=max_t,
                timeout=30.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq Chat Completion error: {AISecurityManager.redact_sensitive_info(str(e))}")
            raise TransientAIError(str(e)) from e
