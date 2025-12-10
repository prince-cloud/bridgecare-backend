from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from patients.models import PatientProfile
from .models import Chat, Message
from .serializers import ChatSerializer, MessageSerializer, MessageListSerializer
from helpers import exceptions


class ChatViewSet(viewsets.ModelViewSet):
    """ViewSet for managing chats"""

    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post"]

    def get_queryset(self):
        """Get chats for the current user where they are either the patient or professional"""
        user = self.request.user

        # Build query to filter chats where user is either patient or professional
        query = Q()

        if hasattr(user, "patient_profile"):
            # Include chats where user is the patient
            query |= Q(patient=user.patient_profile)

        if hasattr(user, "professional_profile"):
            # Include chats where user is the professional
            query |= Q(professional=user.professional_profile)

        if query:
            return Chat.objects.filter(query)
        else:
            # User has neither profile
            return Chat.objects.none()

    @extend_schema(
        request=ChatSerializer,
        responses={201: ChatSerializer},
    )
    def create(self, request):
        """Create or get existing chat

        Both 'patient' and 'professional' IDs are required in the request data.
        If a chat already exists for the provided patient and professional,
        it will be returned instead of creating a new one.
        """
        # Get both patient and professional IDs from request
        patient_id = request.data.get("patient")
        professional_id = request.data.get("professional")

        # Validate both IDs are provided
        if not patient_id:
            raise exceptions.GeneralException("patient field is required")

        if not professional_id:
            raise exceptions.GeneralException("professional field is required")

        # Validate patient exists
        try:
            patient = PatientProfile.objects.get(id=patient_id)
        except PatientProfile.DoesNotExist:
            raise exceptions.GeneralException(
                f"Patient with ID '{patient_id}' not found"
            )

        # Validate professional exists
        try:
            from professionals.models import ProfessionalProfile

            professional = ProfessionalProfile.objects.get(id=professional_id)
        except ProfessionalProfile.DoesNotExist:
            raise exceptions.GeneralException(
                f"Professional with ID '{professional_id}' not found"
            )

        # Get or create chat (returns existing if already exists)
        chat, created = Chat.objects.get_or_create(
            patient=patient, professional=professional
        )

        serializer = self.get_serializer(chat)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        responses={200: MessageListSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        """Get messages for a chat"""
        chat = self.get_object()
        messages = chat.messages.all().order_by("created_at")

        # Paginate if needed
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = MessageListSerializer(messages, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=MessageSerializer,
        responses={201: MessageSerializer},
    )
    @action(detail=True, methods=["post"])
    def send_message(self, request, pk=None):
        """Send a message in a chat (alternative to WebSocket)"""
        chat = self.get_object()
        content = request.data.get("content", "").strip()
        role = request.data.get("role", None)  # Optional: "patient" or "professional"

        if not content:
            raise exceptions.GeneralException("Message content cannot be empty")

        # Create message
        message = Message(chat=chat)

        # Smart role determination (same logic as WebSocket consumer)
        user = request.user
        has_patient = hasattr(user, "patient_profile")
        has_professional = hasattr(user, "professional_profile")

        if not has_patient and not has_professional:
            raise exceptions.GeneralException(
                "User must have either a patient or professional profile"
            )

        if has_patient and has_professional:
            # User has both profiles - determine which one to use
            if role:
                # Explicit role specified
                if role.lower() == "patient":
                    message.patient = user.patient_profile
                elif role.lower() in ["professional", "provider"]:
                    message.provider = user.professional_profile
                else:
                    raise exceptions.GeneralException(
                        f"Invalid role '{role}'. Must be 'patient' or 'professional'"
                    )
            else:
                # Determine from chat context
                if chat.patient.user == user:
                    message.patient = user.patient_profile
                elif chat.professional.user == user:
                    message.provider = user.professional_profile
                else:
                    raise exceptions.GeneralException(
                        "Cannot determine role. Please specify 'role' in request or ensure you're part of this chat"
                    )
        elif has_patient:
            message.patient = user.patient_profile
        elif has_professional:
            message.provider = user.professional_profile

        # Verify the selected role matches the chat
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

        # Update chat
        chat.save(update_fields=["updated_at"])

        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        responses={200: MessageSerializer},
    )
    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """Mark messages as read"""
        chat = self.get_object()
        user = request.user

        # Mark appropriate messages as read
        if hasattr(user, "patient_profile"):
            # Patient marks professional's messages as read
            chat.messages.filter(provider__isnull=False, is_read=False).update(
                is_read=True
            )
        elif hasattr(user, "professional_profile"):
            # Professional marks patient's messages as read
            chat.messages.filter(patient__isnull=False, is_read=False).update(
                is_read=True
            )

        return Response({"status": "Messages marked as read"})
