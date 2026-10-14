from django.urls import path
from .views import (
    ChatAPIView,
    ChatUIView,
    SessionListView,
    SessionDetailView,
    NewSessionView,
)

urlpatterns = [
    path('chat/', ChatUIView.as_view(), name='assistant_chat'),
    path('api/chat/', ChatAPIView.as_view(), name='chat_api'),
    path('api/sessions/', SessionListView.as_view(), name='session_list_api'),
    path('api/sessions/new/', NewSessionView.as_view(), name='session_new_api'),
    path('api/sessions/<int:session_id>/', SessionDetailView.as_view(), name='session_detail_api'),
]

