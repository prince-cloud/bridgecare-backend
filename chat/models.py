from django.db import models
from patients.models import PatientProfile
from professionals.models import ProfessionalProfile
import uuid
from accounts.models import CustomUser


class Chat(models.Model):
    """
    Chat room between a patient and a health professional (provider)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name="chats",
    )
    professional = models.ForeignKey(
        ProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="chats",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chats"
        verbose_name = "Chat"
        verbose_name_plural = "Chats"
        unique_together = [["patient", "professional"]]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Chat: {self.patient.patient_id} - {self.professional.user.email}"


class Message(models.Model):
    """
    Message in a chat between patient and provider
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        null=True,
        blank=True,
    )
    provider = models.ForeignKey(
        ProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        null=True,
        blank=True,
    )
    content = models.TextField(help_text="Message content")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"Message in {self.chat} at {self.created_at}"


class AIChatSession(models.Model):
    """Model to store chat sessions"""

    user = models.ForeignKey(
        CustomUser,
        related_name="chat_sessions",
        on_delete=models.CASCADE,
    )

    title = models.CharField(
        max_length=255, blank=True, help_text="Auto-generated or user-provided title"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether session is still active"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    uud = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Chat: {self.title or 'Untitled'} - {self.user.email}"

    def get_message_count(self):
        return self.messages.count()


class AIChatMessage(models.Model):
    """Model to store individual chat messages"""

    MESSAGE_TYPES = [
        ("user", "User Message"),
        ("assistant", "Assistant Response"),
        ("system", "System Message"),
    ]

    session = models.ForeignKey(
        AIChatSession,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    message_type = models.CharField(
        max_length=10, choices=MESSAGE_TYPES, default="user"
    )
    content = models.TextField()

    # For assistant messages, store context info
    sources = models.JSONField(
        default=list,
        blank=True,
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Confidence score of the response",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    tokens_used = models.IntegerField(
        null=True, blank=True, help_text="Number of tokens used in this message"
    )
    uud = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.message_type}: {self.content[:50]}..."
