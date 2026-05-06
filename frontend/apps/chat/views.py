from django.shortcuts import render, redirect
from django.views import View
from apps.core.mixins import APIViewMixin
from apps.core.api_client import get_api_client, APIError
import logging

logger = logging.getLogger(__name__)

class ConversationListView(View, APIViewMixin):
    template_name = "chat/list.html"

    def get(self, request):
        try:
            with get_api_client(request) as api:
                # Corrected prefix: /chats/conversations/list
                resp = api.get("/chats/conversations/list")
                conversations = resp.get("data", [])
                
                # Normalize IDs for template
                for conv in conversations:
                    conv['id'] = conv.get('_id', conv.get('id'))
                
                context = {
                    "conversations": conversations,
                    "active_tab": "chat"
                }
                return render(request, self.template_name, context)
        except APIError as e:
            self.handle_api_error(request, None, e)
            return render(request, self.template_name, {"conversations": []})

class ChatRoomView(View, APIViewMixin):
    template_name = "chat/room.html"

    def get(self, request, booking_id):
        try:
            with get_api_client(request) as api:
                # 1. Get conversation details - Corrected prefix: /chats/{booking_id}
                conv_resp = api.get(f"/chats/{booking_id}")
                conv = conv_resp.get("data", {})
                
                # 2. History
                history_resp = api.get(f"/chats/{booking_id}/messages", params={"limit": 50})
                messages = history_resp.get("data", [])
                # Sort ascending (oldest first)
                messages.reverse()
                
                # 3. WS token from session
                ws_token = request.session.get('access_token', '')
                
                # Get current user ID safely
                user_obj = request.session.get('user', {})
                user_id = str(user_obj.get('id') or user_obj.get('_id', ''))
                
                context = {
                    "conversation": conv,
                    "messages": messages,
                    "booking_id": booking_id,
                    "ws_token": ws_token,
                    "active_tab": "chat",
                    "user_id": user_id
                }
                return render(request, self.template_name, context)
        except APIError as e:
            self.handle_api_error(request, None, e)
            return redirect("chat:list")
