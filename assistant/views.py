import json
import logging
from django.http import JsonResponse
from django.views import View
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import ChatSession, ChatMessage
from .services import RecruiterAssistantService

logger = logging.getLogger(__name__)

ALLOWED_ROLES = ('RECRUITER', 'COMPANY', 'ADMIN')


def _role_check(user):
    return user.is_authenticated and user.role in ALLOWED_ROLES


# ---------------------------------------------------------------------------
# Chat UI
# ---------------------------------------------------------------------------

class ChatUIView(LoginRequiredMixin, View):
    """Renders the premium full-screen chat UI for recruiters."""
    def get(self, request):
        if not _role_check(request.user):
            from django.shortcuts import redirect
            return redirect('dashboard')
        sessions = ChatSession.objects.filter(user=request.user).order_by('-updated_at')[:20]
        return render(request, 'assistant/chat.html', {
            'sessions': sessions,
            'current_session': None,
        })


# ---------------------------------------------------------------------------
# Chat API — POST to send a message
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class ChatAPIView(LoginRequiredMixin, View):
    """AJAX endpoint: submit a user message and receive an AI response."""

    def post(self, request):
        if not _role_check(request.user):
            return JsonResponse({'error': 'Unauthorized. Only recruiters can access this assistant.'}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

        user_message = (data.get('message') or '').strip()
        session_id = data.get('session_id')

        if not user_message:
            return JsonResponse({'error': 'Message is required.'}, status=400)

        # Get or create session
        try:
            if session_id:
                session = ChatSession.objects.get(id=session_id, user=request.user)
            else:
                session = ChatSession.objects.create(user=request.user, title='New Chat')
        except ChatSession.DoesNotExist:
            return JsonResponse({'error': 'Session not found.'}, status=404)

        # Build history (last 20 messages to keep token usage bounded)
        past_messages = session.messages.filter(role__in=['user', 'assistant']).order_by('created_at')[:20]
        chat_history = [{'role': m.role, 'content': m.content} for m in past_messages]

        # Save user message
        ChatMessage.objects.create(session=session, role='user', content=user_message)

        # Auto-title the session from first message
        if session.title == 'New Chat':
            session.auto_title_from_message(user_message)

        # Run pipeline
        service = RecruiterAssistantService()
        result = service.generate_response(
            chat_history=chat_history,
            user_message=user_message,
            recruiter_user=request.user,
        )

        ai_response = result['response']
        intent = result.get('intent', '')
        tool_log = result.get('tool_log', [])

        # Save AI response with intent metadata
        ChatMessage.objects.create(
            session=session,
            role='assistant',
            content=ai_response,
            intent=intent,
            tool_calls_log=tool_log,
        )

        # Touch session updated_at
        session.save(update_fields=['updated_at'])

        return JsonResponse({
            'session_id': session.id,
            'session_title': session.title,
            'message': ai_response,
            'intent': intent,
        })


# ---------------------------------------------------------------------------
# Session Management APIs
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class SessionListView(LoginRequiredMixin, View):
    """GET list of recruiter's sessions."""

    def get(self, request):
        if not _role_check(request.user):
            return JsonResponse({'error': 'Unauthorized.'}, status=403)
        sessions = ChatSession.objects.filter(user=request.user).order_by('-updated_at')[:30]
        data = [{'id': s.id, 'title': s.title, 'updated_at': s.updated_at.isoformat()} for s in sessions]
        return JsonResponse({'sessions': data})


@method_decorator(csrf_exempt, name='dispatch')
class SessionDetailView(LoginRequiredMixin, View):
    """GET full message history for a session. DELETE to remove it. PATCH to rename."""

    def get(self, request, session_id):
        if not _role_check(request.user):
            return JsonResponse({'error': 'Unauthorized.'}, status=403)
        session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        messages = session.messages.order_by('created_at')
        data = {
            'session_id': session.id,
            'title': session.title,
            'messages': [
                {
                    'role': m.role,
                    'content': m.content,
                    'intent': m.intent,
                    'created_at': m.created_at.isoformat(),
                }
                for m in messages
            ]
        }
        return JsonResponse(data)

    def delete(self, request, session_id):
        if not _role_check(request.user):
            return JsonResponse({'error': 'Unauthorized.'}, status=403)
        session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        session.delete()
        return JsonResponse({'deleted': True, 'session_id': session_id})

    def patch(self, request, session_id):
        if not _role_check(request.user):
            return JsonResponse({'error': 'Unauthorized.'}, status=403)
        session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        try:
            data = json.loads(request.body)
            new_title = (data.get('title') or '').strip()[:120]
            if new_title:
                session.title = new_title
                session.save(update_fields=['title'])
            return JsonResponse({'session_id': session.id, 'title': session.title})
        except Exception:
            return JsonResponse({'error': 'Invalid request.'}, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class NewSessionView(LoginRequiredMixin, View):
    """POST to create a fresh chat session."""

    def post(self, request):
        if not _role_check(request.user):
            return JsonResponse({'error': 'Unauthorized.'}, status=403)
        session = ChatSession.objects.create(user=request.user, title='New Chat')
        return JsonResponse({'session_id': session.id, 'title': session.title})
