from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid


class Profession(models.Model):
    """
    Profession model
    """

    name = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "professions"
        verbose_name = "Profession"
        verbose_name_plural = "Professions"

    def __str__(self):
        return self.name


class Specialization(models.Model):
    """
    Specialization model
    """

    name = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "specializations"
        verbose_name = "Specialization"
        verbose_name_plural = "Specializations"

    def __str__(self):
        return self.name


class LicenceIssueAuthority(models.Model):
    """
    Licence issue authority model
    """

    name = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "licence_issue_authorities"
        verbose_name = "Licence Issue Authority"
        verbose_name_plural = "Licence Issue Authorities"

    def __str__(self):
        return self.name


class ProfessionalProfile(models.Model):
    """
    Specific profile for Individual Professionals
    """

    class EducationStatus(models.TextChoices):
        IN_SCHOOL = "IN_SCHOOL", "In School"
        COMPLETED = "COMPLETED", "Completed"
        NOT_IN_SCHOOL = "NOT_IN_SCHOOL", "Not in School"
        PRACTICING = "PRACTICING", "Practicing"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="professional_profile",
    )

    # education status
    education_status = models.CharField(
        max_length=100,
        choices=EducationStatus.choices,
        default=EducationStatus.NOT_IN_SCHOOL,
    )
    # profession details
    profession = models.ForeignKey(
        Profession,
        on_delete=models.SET_NULL,
        null=True,
        related_name="professional_profiles",
    )
    specialization = models.ForeignKey(
        Specialization,
        on_delete=models.SET_NULL,
        related_name="professional_profiles",
        blank=True,
        null=True,
    )
    facility_affiliation = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    # check weather the person is still in school, completed
    # not in school or practicing
    education_status = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        choices=EducationStatus.choices,
    )

    license_number = models.CharField(max_length=100, null=True, blank=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    license_issuing_authority = models.ForeignKey(
        LicenceIssueAuthority,
        on_delete=models.SET_NULL,
        related_name="professional_profiles",
        blank=True,
        null=True,
    )
    years_of_experience = models.IntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "professional_profiles"
        verbose_name = "Professional Profile"
        verbose_name_plural = "Professional Profiles"

    def __str__(self):
        return f"{self.user.email} - {self.user.primary_role}"

    def is_license_valid(self):
        """Check if professional license is valid"""
        if not self.license_expiry_date:
            return False
        return timezone.now().date() <= self.license_expiry_date


class EducationHistory(models.Model):
    """
    Education history model
    """

    class EducationLevel(models.TextChoices):
        DIPLOMA = "DIPLOMA", "Diploma"
        BACHELOR = "BACHELOR", "Bachelor"
        MASTER = "MASTER", "Master"
        DOCTORATE = "DOCTORATE", "Doctorate"
        PROFESSOR = "PROFESSOR", "Professor"
        OTHER = "OTHER", "Other"

    professional_profile = models.ForeignKey(
        ProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="education_histories",
    )
    education_level = models.CharField(
        max_length=100,
        choices=EducationLevel.choices,
        default=EducationLevel.OTHER,
    )
    education_institution = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    education_institution_address = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    is_current_education = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "education_histories"
        verbose_name = "Education History"
        verbose_name_plural = "Education Histories"

    def __str__(self):
        return f"{self.professional_profile.user.email} - {self.education_level}"
