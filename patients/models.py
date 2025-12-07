from django.db import models
from accounts.models import CustomUser
from phonenumber_field.modelfields import PhoneNumberField
import uuid

from .utils import generate_patient_id


class PatientProfile(models.Model):
    """
    Specific profile for Patient/User platform users
    """

    class Gender(models.TextChoices):
        MALE = "M"
        FEMALE = "F"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient_id = models.CharField(max_length=100, blank=True, null=True)
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="patient_profile",
        blank=True,
        null=True,
    )
    # basic profile information
    first_name = models.CharField(max_length=100, blank=True, null=True)
    surname = models.CharField(max_length=100, blank=True, null=True)
    other_names = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone_number = PhoneNumberField(blank=True, null=True)
    date_of_birth = models.DateField(null=True)
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
        null=True,
    )
    address = models.TextField(blank=True, null=True)

    # media
    profile_picture = models.ImageField(
        upload_to="patients/profile_pictures/",
        blank=True,
        null=True,
    )

    # Basic health information
    blood_type = models.CharField(max_length=5, blank=True, null=True)
    height = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )  # in cm
    weight = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )  # in kg

    # Emergency contact
    emergency_contact_name = models.CharField(max_length=200, blank=True, null=True)
    emergency_contact_phone = PhoneNumberField(blank=True, null=True)
    emergency_contact_relationship = models.CharField(
        max_length=100, blank=True, null=True
    )

    # Insurance and payment
    insurance_provider = models.CharField(max_length=100, blank=True, null=True)
    insurance_number = models.CharField(max_length=100, blank=True, null=True)

    # important date
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "patient_profiles"
        verbose_name = "Patient Profile"
        verbose_name_plural = "Patient Profiles"

    def __str__(self):
        return f"{self.patient_id} : {self.user.first_name} {self.user.last_name}"

    @property
    def bmi(self):
        """Calculate BMI if height and weight are available"""
        if self.height and self.weight:
            height_m = float(self.height) / 100  # Convert cm to m
            weight_kg = float(self.weight)
            return round(weight_kg / (height_m**2), 2)
        return None

    # create a patient ID
    def save(self, *args, **kwargs):
        if not self.patient_id:
            patient_id = generate_patient_id()
            while PatientProfile.objects.filter(patient_id=patient_id).exists():
                patient_id = generate_patient_id()
            self.patient_id = patient_id
        super().save(*args, **kwargs)


class PatientAccess(models.Model):
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name="health_professional_access",
    )
    health_professional = models.ForeignKey(
        "professionals.ProfessionalProfile",
        on_delete=models.CASCADE,
        related_name="patient_access",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "patient_access"
        verbose_name = "Patient Access"
        verbose_name_plural = "Patient Access"

    def __str__(self):
        return f"{self.patient.user.email} - {self.health_professional.user.email}"


class Visitation(models.Model):
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name="visitations",
    )
    issued_by = models.ForeignKey(
        "professionals.ProfessionalProfile",
        on_delete=models.CASCADE,
        related_name="visitations",
    )
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "visitations"
        verbose_name = "Visitation"
        verbose_name_plural = "Visitations"
        ordering = ["-date_created"]

    def __str__(self):
        return f"{self.patient.patient_id} - {self.title}"


class Diagnosis(models.Model):
    visitation = models.OneToOneField(
        Visitation,
        on_delete=models.CASCADE,
        related_name="diagnoses",
    )
    diagnosis = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "diagnoses"
        verbose_name = "Diagnosis"
        verbose_name_plural = "Diagnoses"
        ordering = ["-date_created"]

    def __str__(self):
        return f"{self.patient.user.email} - {self.diagnosis}"


# Patient Vitasl
class Vitals(models.Model):
    visitation = models.OneToOneField(
        Visitation,
        on_delete=models.CASCADE,
        related_name="vitals",
    )

    blood_pressure = models.CharField(max_length=100, blank=True, null=True)
    heart_rate = models.CharField(max_length=100, blank=True, null=True)
    respiratory_rate = models.CharField(max_length=100, blank=True, null=True)
    temperature = models.CharField(max_length=100, blank=True, null=True)
    height = models.CharField(max_length=100, blank=True, null=True)
    weight = models.CharField(max_length=100, blank=True, null=True)
    bmi = models.CharField(max_length=100, blank=True, null=True)
    custom_vitals = models.JSONField(blank=True, null=True)

    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "vitals"
        verbose_name = "Vitals"
        verbose_name_plural = "Vitals"
        ordering = ["-date_created"]


class Prescription(models.Model):
    visitation = models.ForeignKey(
        Visitation,
        on_delete=models.CASCADE,
        related_name="prescriptions",
    )
    medication = models.TextField(blank=True, null=True)
    dosage = models.TextField(blank=True, null=True)
    frequency = models.TextField(blank=True, null=True)
    duration = models.TextField(blank=True, null=True)
    instructions = models.TextField(blank=True, null=True)

    # dates
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prescriptions"
        verbose_name = "Prescription"
        verbose_name_plural = "Prescriptions"
        ordering = ["-date_created"]


class Allergy(models.Model):

    class AllergySeverity(models.TextChoices):
        LOW = "LOW"
        MODERATE = "MODERATE"
        HIGH = "HIGH"
        VERY_HIGH = "VERY_HIGH"

    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name="allergies",
    )
    allergy = models.TextField(blank=True, null=True)
    allergy_severity = models.CharField(
        max_length=100,
        choices=AllergySeverity.choices,
        blank=True,
        null=True,
    )
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "allergies"
        verbose_name = "Allergy"
        ordering = ["-date_created"]


class Notes(models.Model):
    visitation = models.ForeignKey(
        Visitation,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    issued_by = models.ForeignKey(
        "professionals.ProfessionalProfile",
        on_delete=models.CASCADE,
        related_name="notes",
    )
    note = models.TextField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notes"

    def __str__(self):
        return f"{self.patient.patient_id}"


class MedicalHistory(models.Model):
    class HistoryType(models.TextChoices):
        MEDICAL = "MEDICAL"
        SURGICAL = "SURGICAL"
        FAMILY = "FAMILY"
        PERSONAL = "PERSONAL"
        PSYCHOLOGICAL = "PSYCHOLOGICAL"
        SOCIAL = "SOCIAL"
        ENVIRONMENTAL = "ENVIRONMENTAL"
        GENETIC = "GENETIC"
        ALLERGIC = "ALLERGIC"
        CHRONIC = "CHRONIC"
        OTHER = "OTHER"

    history_type = models.CharField(
        max_length=100,
        choices=HistoryType.choices,
    )

    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name="medical_history",
    )
    name = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "medical_history"
        verbose_name = "Medical History"
        verbose_name_plural = "Medical History"
        ordering = ["-date_created"]

    def __str__(self):
        return f"{self.patient.patient_id} - {self.history_type} - {self.name}"
