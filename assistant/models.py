from django.db import models
from accounts.models import CustomUser


class ChatSession(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=120, blank=True, default='New Chat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"ChatSession '{self.title}' ({self.user.username})"

    def auto_title_from_message(self, message: str):
        """Set title from first user message (truncated)."""
        if self.title == 'New Chat' and message:
            self.title = message[:80].strip()
            self.save(update_fields=['title'])


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    intent = models.CharField(max_length=40, blank=True, null=True, help_text="Classified intent for analytics")
    tool_calls_log = models.JSONField(default=list, blank=True, help_text="Audit log of tool calls made for this message")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role} [{self.intent or '-'}] at {self.created_at:%Y-%m-%d %H:%M}"
