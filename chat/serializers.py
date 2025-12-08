from rest_framework import serializers
from .models import Chat, Message
from patients.serializers import PatientChatDetailSerializer
from professionals.serializers import ProfessionalChatDetailSerializer


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message"""

    sender_type = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "chat",
            "patient",
            "provider",
            "content",
            "sender_type",
            "is_read",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "is_read")

    def get_sender_type(self, obj):
        """Determine if sender is patient or professional"""
        if obj.patient:
            return "patient"
        elif obj.provider:
            return "professional"
        return None

    def create(self, validated_data):
        """Create message"""
        return Message.objects.create(**validated_data)


class ChatSerializer(serializers.ModelSerializer):
    """Serializer for Chat"""

    patient_detail = PatientChatDetailSerializer(source="patient", read_only=True)
    professional_detail = ProfessionalChatDetailSerializer(
        source="professional", read_only=True
    )
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = (
            "id",
            "patient",
            "professional",
            "patient_detail",
            "professional_detail",
            "last_message",
            "unread_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_last_message(self, obj):
        """Get the last message in the chat"""
        last_msg = obj.messages.last()
        if last_msg:
            return {
                "id": str(last_msg.id),
                "content": last_msg.content,
                "sender_type": "patient" if last_msg.patient else "professional",
                "created_at": last_msg.created_at,
            }
        return None

    def get_unread_count(self, obj):
        """Get count of unread messages"""
        request = self.context.get("request")
        if not request or not request.user:
            return 0

        # Determine current user type
        if hasattr(request.user, "patient_profile"):
            # Patient checking unread messages from professional
            return obj.messages.filter(provider__isnull=False, is_read=False).count()
        elif hasattr(request.user, "professional_profile"):
            # Professional checking unread messages from patient
            return obj.messages.filter(patient__isnull=False, is_read=False).count()
        return 0


class MessageListSerializer(serializers.ModelSerializer):
    """Simplified serializer for message list"""

    content = serializers.SerializerMethodField()
    sender_type = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "content",
            "sender_type",
            "is_read",
            "created_at",
        )

    def get_content(self, obj):
        """Return message content"""
        return obj.content

    def get_sender_type(self, obj):
        """Determine if sender is patient or professional"""
        if obj.patient:
            return "patient"
        elif obj.provider:
            return "professional"
        return None
