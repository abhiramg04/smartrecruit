"""
assistant/services.py — RecruiterAssistantService (Phase 10).

Full pipeline:
  sanitize → security check → classify intent → dispatch tool
  → build context → call Groq → validate output → return

SECURITY: AI never directly executes DB queries or application actions.
"""
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Concise system prompt that enforces the assistant's role and limitations
SYSTEM_PROMPT = """You are SmartRecruit AI — a professional AI Recruitment Assistant for recruiters.

Your role:
- Help recruiters find and evaluate candidates for their company's open positions
- Summarize candidate profiles and explain AI rankings
- Generate job descriptions and interview questions
- Provide hiring guidance and recommendations
- Draft professional candidate communications for recruiter review

Strict limitations:
- You CANNOT and will NOT reject, select, delete, or take any action on candidates
- You CANNOT modify system settings, user roles, or security configurations
- All candidate actions must be performed by the recruiter through the SmartRecruit portal
- You only have access to data from the recruiter's authorized company

Response style:
- Be concise, professional, and structured
- Use markdown formatting (bullet points, bold, headers) for readability
- Always clarify that final decisions must be made by the recruiter
- If asked to perform an unauthorized action, politely explain your limitations"""


class RecruiterAssistantService:
    """
    Intent-driven, permission-scoped AI Recruitment Assistant.
    Implements: sanitize → classify → tool dispatch → context → Groq → validate
    """

    def __init__(self):
        from core.ai.service import GroqAIEngine
        from core.ai.security import AISecurityManager
        self.engine = GroqAIEngine()
        self.ai_security = AISecurityManager()

    def generate_response(
        self,
        chat_history: List[Dict[str, str]],
        user_message: str,
        recruiter_user=None
    ) -> Dict[str, Any]:
        """
        Main entry point.
        Returns: {'response': str, 'intent': str, 'tool_log': list}
        """
        from .security_guard import AssistantSecurityGuard
        from .intent import IntentClassifier, Intent

        tool_log = []

        # ── Step 1: Input sanitization (base layer) ──────────────────────────
        sanitized = self.ai_security.sanitize_prompt_input(user_message)
        sanitized = self.ai_security.redact_sensitive_info(sanitized)

        # ── Step 2: Security guard (assistant-specific patterns) ─────────────
        is_safe, reason = AssistantSecurityGuard.check_input(sanitized)
        if not is_safe:
            refusal = AssistantSecurityGuard.get_refusal_message(reason)
            return {'response': refusal, 'intent': 'BLOCKED', 'tool_log': [reason]}

        # ── Step 3: Intent classification ────────────────────────────────────
        classified = IntentClassifier.classify(sanitized)

        if classified.name == Intent.UNAUTHORIZED_ACTION:
            refusal = AssistantSecurityGuard.get_refusal_message('unauthorized_action')
            return {'response': refusal, 'intent': Intent.UNAUTHORIZED_ACTION, 'tool_log': ['unauthorized_action_blocked']}

        # ── Step 4: Tool dispatch (permission-scoped DB retrieval) ───────────
        context_data = {}
        if recruiter_user and classified.name != Intent.GENERAL_CHAT:
            context_data, tool_log = self._dispatch_tool(classified, recruiter_user)

        # ── Step 5: Build context-enriched prompt ────────────────────────────
        enriched_message = self._build_context_prompt(sanitized, classified.name, context_data)

        # ── Step 6: Groq chat completion ─────────────────────────────────────
        messages = self._build_messages(chat_history, enriched_message)
        try:
            raw_response = self.engine.generate_chat_completion(messages, temperature=0.65)
        except Exception as e:
            logger.error(f"[RecruiterAssistant] Groq error: {e}")
            return {
                'response': "I'm having trouble connecting to the AI service right now. Please try again in a moment.",
                'intent': classified.name,
                'tool_log': tool_log
            }

        # ── Step 7: Output security validation ───────────────────────────────
        _, safe_response = AssistantSecurityGuard.check_output(raw_response)

        return {
            'response': safe_response,
            'intent': classified.name,
            'tool_log': tool_log,
        }

    def _dispatch_tool(self, classified, recruiter_user) -> tuple:
        """Dispatch the appropriate backend tool based on classified intent."""
        from .intent import Intent
        from .tools import (
            tool_find_candidates, tool_explain_ranking, tool_summarize_candidate,
            tool_find_missing_skills, tool_generate_job_description, tool_generate_questions,
            tool_summarize_interviews, tool_hiring_guidance, tool_draft_email,
            ToolPermissionError
        )

        entities = classified.entities
        tool_log = []

        try:
            if classified.name == Intent.FIND_CANDIDATES:
                data = tool_find_candidates(
                    recruiter_user,
                    job_title_query=entities.get('job_hint', ''),
                    limit=6
                )
                tool_log.append({'tool': 'find_candidates', 'job_hint': entities.get('job_hint', '')})

            elif classified.name == Intent.EXPLAIN_RANKING:
                name_hint = entities.get('candidate_name_hint', classified.raw_message[:40])
                data = tool_explain_ranking(recruiter_user, name_a=name_hint)
                tool_log.append({'tool': 'explain_ranking', 'name_hint': name_hint})

            elif classified.name == Intent.SUMMARIZE_CANDIDATE:
                name_hint = entities.get('candidate_name_hint', '')
                if not name_hint:
                    # Extract from raw message
                    import re
                    words = classified.raw_message.split()
                    name_hint = ' '.join(w for w in words if w[0].isupper() and len(w) > 2)[:40]
                data = tool_summarize_candidate(recruiter_user, name_hint=name_hint)
                tool_log.append({'tool': 'summarize_candidate', 'name_hint': name_hint})

            elif classified.name == Intent.MISSING_SKILLS:
                data = tool_find_missing_skills(
                    recruiter_user,
                    skill=entities.get('skill_hint', ''),
                    job_title=entities.get('job_hint', '')
                )
                tool_log.append({'tool': 'find_missing_skills', 'skill': entities.get('skill_hint', '')})

            elif classified.name == Intent.GENERATE_JD:
                data = tool_generate_job_description(
                    title=entities.get('job_hint', ''),
                    requirements=classified.raw_message
                )
                tool_log.append({'tool': 'generate_jd'})

            elif classified.name == Intent.GENERATE_QUESTIONS:
                name_hint = entities.get('candidate_name_hint', '')
                data = tool_generate_questions(
                    recruiter_user,
                    name_hint=name_hint,
                    job_hint=entities.get('job_hint', '')
                )
                tool_log.append({'tool': 'generate_questions', 'name_hint': name_hint})

            elif classified.name == Intent.SUMMARIZE_INTERVIEWS:
                date_filter = 'today'
                if 'week' in classified.raw_message.lower():
                    date_filter = 'week'
                data = tool_summarize_interviews(recruiter_user, date_filter=date_filter)
                tool_log.append({'tool': 'summarize_interviews', 'filter': date_filter})

            elif classified.name == Intent.HIRING_GUIDANCE:
                data = tool_hiring_guidance(recruiter_user, job_hint=entities.get('job_hint', ''))
                tool_log.append({'tool': 'hiring_guidance'})

            elif classified.name == Intent.DRAFT_COMMUNICATION:
                name_hint = entities.get('candidate_name_hint', '')
                email_type = 'general'
                msg_lower = classified.raw_message.lower()
                if 'reject' in msg_lower or 'regret' in msg_lower:
                    email_type = 'rejection'
                elif 'offer' in msg_lower:
                    email_type = 'offer'
                elif 'interview' in msg_lower:
                    email_type = 'interview_invite'
                data = tool_draft_email(recruiter_user, name_hint=name_hint, email_type=email_type)
                tool_log.append({'tool': 'draft_email', 'type': email_type})

            else:
                data = {}

            return data, tool_log

        except ToolPermissionError as e:
            logger.warning(f"[ToolDispatcher] Permission error: {e}")
            return {'error': str(e)}, [{'error': str(e)}]
        except Exception as e:
            logger.error(f"[ToolDispatcher] Unexpected error: {e}", exc_info=True)
            return {}, [{'error': f'tool_error: {str(e)[:100]}'}]

    def _build_context_prompt(self, user_message: str, intent: str, context_data: dict) -> str:
        """Build a context-enriched prompt including retrieved data."""
        if not context_data or context_data.get('error'):
            return user_message

        context_json = json.dumps(context_data, indent=2, default=str)
        # Limit context size
        if len(context_json) > 3000:
            context_json = context_json[:3000] + '\n... [truncated for token efficiency]'

        return (
            f"{user_message}\n\n"
            f"--- AUTHORIZED CONTEXT DATA (from SmartRecruit database, filtered to your company) ---\n"
            f"```json\n{context_json}\n```\n"
            f"--- END CONTEXT ---\n\n"
            f"Please use the above data to answer the recruiter's question accurately. "
            f"Do not invent candidate names or scores not present in the data."
        )

    def _build_messages(self, chat_history: List[Dict], enriched_message: str) -> List[Dict]:
        """Assemble the messages list for the Groq API call."""
        # Keep last 8 exchanges (16 messages) to avoid token limits
        recent_history = chat_history[-16:] if len(chat_history) > 16 else chat_history

        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]

        # Sanitize history
        for msg in recent_history:
            from core.ai.security import AISecurityManager
            safe_content = AISecurityManager.sanitize_prompt_input(msg.get('content', ''))
            messages.append({'role': msg.get('role', 'user'), 'content': safe_content})

        messages.append({'role': 'user', 'content': enriched_message})
        return messages
