import uuid

from django.db import models


class ContactEnquiry(models.Model):
    """
    A message submitted through the public "Let's Talk" contact form.

    Persisted before any email is attempted so an enquiry is never lost to a
    mail-provider outage — the audit found submissions were silently dropped
    with no record on either side.
    """

    STATUS_CHOICES = [
        ("new", "New"),
        ("in_progress", "In Progress"),
        ("responded", "Responded"),
        ("closed", "Closed"),
        ("spam", "Spam"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=150)
    company_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField()
    phone_number = models.CharField(max_length=32, blank=True)
    message = models.TextField(max_length=2000)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    notification_sent = models.BooleanField(
        default=False, help_text="Whether the internal notification email was delivered"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contact_enquiries"
        verbose_name = "Contact Enquiry"
        verbose_name_plural = "Contact Enquiries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["email", "created_at"]),
        ]

    def __str__(self):
        return f"{self.full_name} <{self.email}> — {self.get_status_display()}"
