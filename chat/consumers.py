import json
from channels.generic.websocket import (
    AsyncJsonWebsocketConsumer,
)  # AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Chat, Message
from helpers import exceptions

User = get_user_model()


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for chat messaging"""

    async def connect(self):
        print("Connecting to chat consumer ======")
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        self.chat_group_name = f"chat_{self.chat_id}"

        # Verify user has access to this chat
        chat = await self.get_chat(self.chat_id)
        if not chat:
            await self.close()
            return

        if not await self.has_chat_access(chat):
            await self.close()
            return

        # Join chat room group
        await self.channel_layer.group_add(self.chat_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave chat room group
        await self.channel_layer.group_discard(self.chat_group_name, self.channel_name)

    async def receive(self, text_data):
        """Receive message from WebSocket"""
        try:
            data = json.loads(text_data)
            message_content = data.get("content", "").strip()
            role = data.get("role", None)  # Optional: "patient" or "professional"

            if not message_content:
                await self.send(
                    text_data=json.dumps({"error": "Message content cannot be empty"})
                )
                return

            # Get chat
            chat = await self.get_chat(self.chat_id)
            if not chat:
                await self.send(text_data=json.dumps({"error": "Chat not found"}))
                return

            # Create and save message
            message = await self.create_message(chat, message_content, role=role)

            # Send message to chat group
            await self.channel_layer.group_send(
                self.chat_group_name,
                {
                    "type": "chat_message",
                    "message": {
                        "id": str(message.id),
                        "content": message.content,
                        "sender_type": "patient" if message.patient else "professional",
                        "created_at": message.created_at.isoformat(),
                    },
                },
            )
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid JSON"}))
        except Exception as e:
            await self.send(
                text_data=json.dumps({"error": f"Error sending message: {str(e)}"})
            )

    async def chat_message(self, event):
        """Receive message from chat group"""
        message = event["message"]
        # Send message to WebSocket
        await self.send(text_data=json.dumps({"message": message}))

    @database_sync_to_async
    def get_chat(self, chat_id):
        """Get chat by ID"""
        try:
            return Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            return None

    @database_sync_to_async
    def has_chat_access(self, chat):
        """Check if user has access to this chat"""
        # User can access if they are either the patient or the professional in this chat
        is_patient = chat.patient.user == self.user
        is_professional = chat.professional.user == self.user
        return is_patient or is_professional

    @database_sync_to_async
    def create_message(self, chat, content, role=None):
        """
        Create a new message with smart role detection.

        Role determination priority:
        1. Explicit role specified in message (if user has both profiles)
        2. Chat context (if user is patient in this chat, use patient profile)
        3. Default based on available profiles
        """
        message = Message(chat=chat)

        # Check what profiles the user has
        has_patient = hasattr(self.user, "patient_profile")
        has_professional = hasattr(self.user, "professional_profile")

        if not has_patient and not has_professional:
            raise exceptions.GeneralException(
                "User must have either a patient or professional profile"
            )

        # Smart role determination
        if has_patient and has_professional:
            # User has both profiles - need to determine which one to use
            if role:
                # Explicit role specified
                if role.lower() == "patient":
                    message.patient = self.user.patient_profile
                elif role.lower() in ["professional", "provider"]:
                    message.provider = self.user.professional_profile
                else:
                    raise exceptions.GeneralException(
                        f"Invalid role '{role}'. Must be 'patient' or 'professional'"
                    )
            else:
                # Determine from chat context
                # If user is the patient in this chat, they're acting as patient
                if chat.patient.user == self.user:
                    message.patient = self.user.patient_profile
                # If user is the professional in this chat, they're acting as professional
                elif chat.professional.user == self.user:
                    message.provider = self.user.professional_profile
                else:
                    # This shouldn't happen due to access control, but handle gracefully
                    raise exceptions.GeneralException(
                        "Cannot determine role. Please specify 'role' in message or ensure you're part of this chat"
                    )
        elif has_patient:
            # User only has patient profile
            message.patient = self.user.patient_profile
        elif has_professional:
            # User only has professional profile
            message.provider = self.user.professional_profile

        # Verify the selected role matches the chat
        # Prevent sending as wrong role (e.g., patient sending as professional in their own chat)
        if message.patient and chat.patient != message.patient:
            raise exceptions.GeneralException(
                "Cannot send message as patient: you are not the patient in this chat"
            )
        if message.provider and chat.professional != message.provider:
            raise exceptions.GeneralException(
                "Cannot send message as professional: you are not the professional in this chat"
            )

        # Set message content
        message.content = content
        message.save()

        # Update chat updated_at
        chat.save(update_fields=["updated_at"])

        return message
