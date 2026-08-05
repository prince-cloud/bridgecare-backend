"""
Platform-default intervention template definitions (13 July 2026 review, item h).

Kept model-independent — plain strings, no enum or model imports — so the data
migration that seeds a fresh deployment can use it with historical models,
while the management command uses it with the live ones. One definition, two
callers: the alternative was a copy in the migration that would drift the first
time these fields change.

`tests_review_items.py` asserts these strings still match the real
`InterventionField` choices, so a renamed choice fails loudly rather than
silently seeding invalid values.

NOTE FOR REVIEW: Gideon owes the definitive default field list per the meeting
minutes. These are clinically conventional starting points so organisers are
not left with an empty form; expect them to be revised once his list arrives.
"""

# Vitals shared by most screening interventions. Height and weight are tagged
# so BMI can be derived; BMI itself is computed, never typed.
CORE_VITALS = [
    {"name": "Height (cm)", "field_type": "NUMBER", "section": "VITALS", "field_key": "height"},
    {"name": "Weight (kg)", "field_type": "NUMBER", "section": "VITALS", "field_key": "weight"},
    {
        "name": "BMI",
        "field_type": "NUMBER",
        "section": "VITALS",
        "field_key": "bmi",
        "is_computed": True,
    },
    # Text so "120/80" can be entered exactly as measured.
    {
        "name": "Blood Pressure",
        "field_type": "TEXT",
        "section": "VITALS",
        "field_key": "blood_pressure",
    },
    {"name": "Temperature (°C)", "field_type": "NUMBER", "section": "VITALS", "field_key": "temperature"},
    {"name": "Pulse (bpm)", "field_type": "NUMBER", "section": "VITALS", "field_key": "pulse"},
]

TEMPLATES = [
    {
        "name": "General Health Screening",
        "description": "Standard vitals plus basic screening outcome.",
        "intervention_type": "General Health Screening",
        "fields": CORE_VITALS
        + [
            {"name": "Blood Sugar (mmol/L)", "field_type": "NUMBER", "section": "VITALS", "field_key": "blood_sugar"},
            {"name": "Presenting Complaint", "field_type": "TEXT", "section": "INTERVENTION"},
            {
                "name": "Screening Outcome",
                "field_type": "SELECTION",
                "section": "INTERVENTION",
                "options": ["Normal", "Abnormal — advised", "Referred"],
                "required": True,
            },
            {"name": "Referred To", "field_type": "TEXT", "section": "INTERVENTION"},
            {"name": "Notes", "field_type": "TEXT", "section": "INTERVENTION"},
        ],
    },
    {
        "name": "Eye Screening",
        "description": "Visual acuity and eye health assessment.",
        "intervention_type": "Eye Screening",
        "fields": [
            {"name": "Visual Acuity — Right Eye", "field_type": "TEXT", "section": "INTERVENTION"},
            {"name": "Visual Acuity — Left Eye", "field_type": "TEXT", "section": "INTERVENTION"},
            {"name": "Wears Glasses", "field_type": "BOOLEAN", "section": "INTERVENTION"},
            {
                "name": "Condition Observed",
                "field_type": "SELECTION",
                "section": "INTERVENTION",
                "options": [
                    "None",
                    "Refractive error",
                    "Cataract",
                    "Glaucoma suspect",
                    "Conjunctivitis",
                    "Other",
                ],
            },
            {
                "name": "Action Taken",
                "field_type": "SELECTION",
                "section": "INTERVENTION",
                "options": ["Advised", "Glasses issued", "Referred", "Treated"],
                "required": True,
            },
            {"name": "Notes", "field_type": "TEXT", "section": "INTERVENTION"},
        ],
    },
    {
        "name": "Blood Pressure Check",
        "description": "Focused hypertension screening.",
        "intervention_type": "Blood Pressure Screening",
        "fields": [
            {
                "name": "Blood Pressure",
                "field_type": "TEXT",
                "section": "VITALS",
                "field_key": "blood_pressure",
                "required": True,
            },
            {"name": "Pulse (bpm)", "field_type": "NUMBER", "section": "VITALS", "field_key": "pulse"},
            {"name": "Known Hypertensive", "field_type": "BOOLEAN", "section": "INTERVENTION"},
            {"name": "On Medication", "field_type": "BOOLEAN", "section": "INTERVENTION"},
            {
                "name": "Advice Given",
                "field_type": "SELECTION",
                "section": "INTERVENTION",
                "options": ["Lifestyle advice", "Continue medication", "Referred urgently"],
            },
        ],
    },
    {
        "name": "Blood Sugar / Diabetes Screening",
        "description": "Random or fasting blood glucose screening.",
        "intervention_type": "Diabetes Screening",
        "fields": [
            {
                "name": "Blood Sugar (mmol/L)",
                "field_type": "NUMBER",
                "section": "VITALS",
                "field_key": "blood_sugar",
                "required": True,
            },
            {
                "name": "Sample Type",
                "field_type": "SELECTION",
                "section": "INTERVENTION",
                "options": ["Random", "Fasting", "Post-prandial"],
                "required": True,
            },
            {"name": "Known Diabetic", "field_type": "BOOLEAN", "section": "INTERVENTION"},
            {
                "name": "Outcome",
                "field_type": "SELECTION",
                "section": "INTERVENTION",
                "options": ["Normal", "Elevated — advised", "Referred"],
            },
        ],
    },
    {
        "name": "Dental Screening",
        "description": "Basic oral health check.",
        "intervention_type": "Dental Screening",
        "fields": [
            {
                "name": "Oral Hygiene",
                "field_type": "SELECTION",
                "section": "INTERVENTION",
                "options": ["Good", "Fair", "Poor"],
            },
            {"name": "Decayed Teeth (count)", "field_type": "NUMBER", "section": "INTERVENTION"},
            {"name": "Gum Disease Present", "field_type": "BOOLEAN", "section": "INTERVENTION"},
            {
                "name": "Action Taken",
                "field_type": "SELECTION",
                "section": "INTERVENTION",
                "options": ["Advised", "Scaling done", "Extraction", "Referred"],
            },
            {"name": "Notes", "field_type": "TEXT", "section": "INTERVENTION"},
        ],
    },
    {
        "name": "Maternal & Child Health",
        "description": "Antenatal / child wellness check.",
        "intervention_type": "Maternal and Child Health",
        "fields": CORE_VITALS
        + [
            {"name": "Gestational Age (weeks)", "field_type": "NUMBER", "section": "INTERVENTION"},
            {"name": "Antenatal Visits So Far", "field_type": "NUMBER", "section": "INTERVENTION"},
            {"name": "Immunisations Up To Date", "field_type": "BOOLEAN", "section": "INTERVENTION"},
            {
                "name": "Outcome",
                "field_type": "SELECTION",
                "section": "INTERVENTION",
                "options": ["Normal", "Advised", "Referred"],
            },
        ],
    },
]


def seed_platform_templates(
    *, template_model, template_field_model, intervention_type_model, reset=False
):
    """
    Create or refresh the platform-default templates.

    Takes model classes rather than importing them, so a migration can pass its
    historical versions. Returns (created, updated).

    Existing templates keep their fields unless `reset` is passed: organisers
    copy these into live interventions, and silently rewriting them under an
    event that is already running would be worse than leaving them stale.
    """
    created_count = 0
    updated_count = 0

    for spec in TEMPLATES:
        intervention_type = None
        if spec.get("intervention_type"):
            intervention_type, _ = intervention_type_model.objects.get_or_create(
                name=spec["intervention_type"],
                defaults={"default": True},
            )

        template, created = template_model.objects.get_or_create(
            name=spec["name"],
            organization=None,
            defaults={
                "description": spec["description"],
                "intervention_type": intervention_type,
                "is_platform_default": True,
            },
        )

        if created:
            created_count += 1
        else:
            template.description = spec["description"]
            template.intervention_type = intervention_type
            template.is_platform_default = True
            template.is_active = True
            template.save()
            updated_count += 1
            if not reset:
                continue
            template.fields.all().delete()

        template_field_model.objects.bulk_create(
            [
                template_field_model(
                    template=template,
                    name=field["name"],
                    field_type=field.get("field_type", "TEXT"),
                    section=field.get("section", "INTERVENTION"),
                    field_key=field.get("field_key") or None,
                    is_computed=field.get("is_computed", False),
                    required=field.get("required", False),
                    order=index,
                    options=field.get("options", []),
                )
                for index, field in enumerate(spec["fields"])
            ]
        )

    return created_count, updated_count
