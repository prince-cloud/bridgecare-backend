"""Access-control helpers for patient records.

Patient records (profiles, visitations, diagnoses, vitals, prescriptions,
notes, allergies, medical history) hold PHI and must only be visible to:

- the patient themselves (their own ``patient_profile``),
- a health professional who has been granted ``PatientAccess``
  (created when an appointment is booked — see ``professionals/views.py``),
- a facility (admin or staff) that has been granted ``FacilityPatientAccess``
  (created when a patient is registered/linked — see ``facilities/views.py``),
- staff/superusers (unrestricted, for admin tooling).

These helpers centralise that gating so every ViewSet scopes identically.
``select_related``/``prefetch_related`` are intentionally left to callers.
"""

from django.db.models import Q


def is_unrestricted(user) -> bool:
    """Staff and superusers bypass per-patient scoping (admin tooling)."""
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def accessible_patient_ids(user):
    """Return the set of ``PatientProfile`` ids this user may access.

    Returns ``None`` to signal *no restriction* (staff/superuser).
    """
    if is_unrestricted(user):
        return None

    ids = set()
    if not (user and user.is_authenticated):
        return ids

    # The patient's own profile.
    if hasattr(user, "patient_profile"):
        ids.add(user.patient_profile.id)

    # Professional → patients they have been granted access to.
    if hasattr(user, "professional_profile"):
        ids.update(
            user.professional_profile.patient_access.filter(
                is_active=True,
            ).values_list("patient_id", flat=True)
        )

    # Facility (admin or staff) → patients linked to the facility.
    from facilities.views import get_facility_for_user  # lazy: avoid circular import

    facility = get_facility_for_user(user)
    if facility is not None:
        from .models import FacilityPatientAccess

        ids.update(
            FacilityPatientAccess.objects.filter(
                facility=facility, is_active=True
            ).values_list("patient_id", flat=True)
        )

    return ids


def filter_patient_queryset(queryset, user, patient_field="id"):
    """Scope a queryset whose ``patient_field`` points at ``PatientProfile.id``."""
    patient_ids = accessible_patient_ids(user)
    if patient_ids is None:  # unrestricted
        return queryset
    return queryset.filter(**{f"{patient_field}__in": patient_ids})


def _visitation_access_q(user, prefix):
    """Build a Q over a ``Visitation`` (optionally via ``prefix`` like
    ``"visitation"``) that matches records the user may access."""
    field = lambda name: f"{prefix}__{name}" if prefix else name  # noqa: E731

    patient_ids = accessible_patient_ids(user)
    q = Q(**{field("patient_id") + "__in": patient_ids})

    # Always include records a provider issued or that belong to their facility,
    # so freshly-created records remain visible even before an access row exists.
    if hasattr(user, "professional_profile"):
        q |= Q(**{field("issued_by"): user.professional_profile})

    from facilities.views import get_facility_for_user  # lazy: avoid circular import

    facility = get_facility_for_user(user)
    if facility is not None:
        q |= Q(**{field("facility"): facility})

    return q


def filter_visitation_queryset(queryset, user):
    """Scope a ``Visitation`` queryset to records the user may access."""
    if is_unrestricted(user):
        return queryset
    return queryset.filter(_visitation_access_q(user, prefix="")).distinct()


def filter_by_visitation(queryset, user, visitation_field="visitation"):
    """Scope a queryset of records that relate to a patient via a Visitation FK
    (Diagnosis, Vitals, Prescription, Notes)."""
    if is_unrestricted(user):
        return queryset
    return queryset.filter(
        _visitation_access_q(user, prefix=visitation_field)
    ).distinct()
