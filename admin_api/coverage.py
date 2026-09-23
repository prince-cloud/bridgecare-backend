"""
Coverage map: every BridgeCare model → how the admin portal exposes it.

Modes:
  resource          standalone list/form in the portal (nav item)
  inline:<parent>   editable/read-only child rows on the parent's form
  lookup            hidden lookup feeding FK widgets
  None              intentionally not exposed (auto-managed junctions)

Phases: 0=done at launch, 1..9 = release phases of the coverage plan.
DONE marks models already visible in the portal today.
"""

DONE = {
    "users", "roles", "user-roles", "security-events",
    "addresses", "mfa-devices", "login-sessions", "auth-audit", "data-access-logs", "email-delivery-logs",
    "organizations", "organization-staff", "health-programs", "participants", "program-catalogs",
    "facilities", "facility-appointments", "facility-staff", "wards", "beds", "lab-tests", "staff-invitations", "locum-workers",
    "professionals", "professions", "specializations", "licence-authorities", "professional-appointments",
    "availabilities", "education-histories", "availability-blocks", "break-periods",
    "patients", "visitations", "patient-access-grants", "facility-patient-access", "diagnoses", "vitals", "prescriptions", "allergies", "clinical-notes", "medical-histories", "patient-access-grants", "facility-patient-access", "diagnoses", "vitals", "prescriptions", "allergies", "clinical-notes", "medical-histories",
    "pharmacies", "drugs", "orders", "order-items", "payments", "drug-categories", "suppliers", "drug-batches", "stock-movements", "payment-methods", "settlements", "settlement-orders", "settlement-payouts", "callback-data", "pharmacy-orders",
    "partners", "subsidies", "partnership-requests",
    "contact-enquiries", "organization-files", "locum-jobs", "locum-applications", "locum-job-roles", "program-partners", "program-locum-needs", "program-monitors", "certificate-templates", "issued-certificates", "intervention-types", "interventions", "program-invitations", "intervention-fields", "intervention-field-options", "intervention-responses", "intervention-response-values", "intervention-templates", "intervention-template-fields", "bulk-intervention-uploads", "survey-types", "surveys", "survey-questions", "survey-question-options", "survey-responses", "survey-response-answers", "bulk-survey-uploads", "chats", "chat-messages", "ai-sessions", "ai-messages", "ai-abuse-events",
}

# model (app_label.model_name, lowercase) → (mode, portal_key, phase)
COVERAGE = {
    # ── accounts ──
    "accounts.customuser": ("resource", "users", 0),
    "accounts.address": ("inline:users", "addresses", 1),
    "accounts.role": ("resource", "roles", 0),
    "accounts.userrole": ("resource", "user-roles", 0),
    "accounts.mfadevice": ("resource", "mfa-devices", 1),
    "accounts.loginsession": ("resource", "login-sessions", 1),
    "accounts.securityevent": ("resource", "security-events", 0),
    "accounts.authenticationaudit": ("resource", "auth-audit", 1),
    "accounts.dataaccesslog": ("resource", "data-access-logs", 1),
    "accounts.emaildeliverylog": ("resource", "email-delivery-logs", 1),
    # ── communities ──
    "communities.organization": ("resource", "organizations", 0),
    "communities.staff": ("resource", "organization-staff", 0),
    "communities.organizationfiles": ("inline:organizations", "organization-files", 5),
    "communities.locumjobrole": ("lookup", "locum-job-roles", 5),
    "communities.locumjob": ("resource", "locum-jobs", 5),
    "communities.locumjobapplication": ("resource", "locum-applications", 5),
    "communities.healthprogramtype": ("lookup", "program-catalogs", 0),
    "communities.healthprogrampartners": ("lookup", "program-partners", 5),
    "communities.healthprogram": ("resource", "health-programs", 0),
    "communities.healthprogramlocumneed": ("inline:locum-jobs", "program-locum-needs", 5),
    "communities.programinterventiontype": ("lookup", "intervention-types", 6),
    "communities.programintervention": ("resource", "interventions", 6),
    "communities.healthprograminvitation": ("resource", "program-invitations", 6),
    "communities.interventionfield": ("inline:program-interventions", "intervention-fields", 6),
    "communities.interventionfieldoption": ("inline:program-interventions", "intervention-field-options", 6),
    "communities.participant": ("resource", "participants", 0),
    "communities.interventionresponse": ("resource", "intervention-responses", 6),
    "communities.interventionresponsevalue": ("inline:intervention-responses", "intervention-response-values", 6),
    "communities.interventiontemplate": ("resource", "intervention-templates", 6),
    "communities.interventiontemplatefield": ("inline:intervention-templates", "intervention-template-fields", 6),
    "communities.bulkinterventionupload": ("resource", "bulk-intervention-uploads", 6),
    "communities.surveytype": ("lookup", "survey-types", 7),
    "communities.survey": ("resource", "surveys", 7),
    "communities.surveyquestion": ("inline:surveys", "survey-questions", 7),
    "communities.surveyquestionoption": ("inline:surveys", "survey-question-options", 7),
    "communities.surveyresponse": ("resource", "survey-responses", 7),
    "communities.surveyresponseanswers": ("inline:survey-responses", "survey-response-answers", 7),
    "communities.bulksurveyupload": ("resource", "bulk-survey-uploads", 7),
    "communities.certificatetemplate": ("resource", "certificate-templates", 5),
    "communities.issuedcertificate": ("resource", "issued-certificates", 5),
    # ── facilities ──
    "facilities.facilityprofile": ("resource", "facilities", 0),
    "facilities.locum": ("resource", "locum-workers", 2),
    "facilities.facilitystaff": ("resource", "facility-staff", 2),
    "facilities.ward": ("resource", "wards", 2),
    "facilities.bed": ("resource", "beds", 2),
    "facilities.facilityappointment": ("resource", "facility-appointments", 0),
    "facilities.labtest": ("resource", "lab-tests", 2),
    "facilities.staffinvitation": ("resource", "staff-invitations", 2),
    # ── professionals ──
    "professionals.profession": ("lookup", "professions", 0),
    "professionals.specialization": ("lookup", "specializations", 2),
    "professionals.licenceissueauthority": ("lookup", "licence-authorities", 2),
    "professionals.professionalprofile": ("resource", "professionals", 0),
    "professionals.availability": ("resource", "availabilities", 2),
    "professionals.educationhistory": ("resource", "education-histories", 2),
    "professionals.availabilityblock": ("resource", "availability-blocks", 2),
    "professionals.breakperiod": ("resource", "break-periods", 2),
    "professionals.appointment": ("resource", "professional-appointments", 2),
    # ── patients ──
    "patients.patientprofile": ("resource", "patients", 0),
    "patients.patientaccess": ("resource", "patient-access-grants", 3),
    "patients.facilitypatientaccess": ("resource", "facility-patient-access", 3),
    "patients.visitation": ("resource", "visitations", 0),
    "patients.diagnosis": ("inline:visitations", "diagnoses", 3),
    "patients.vitals": ("inline:visitations", "vitals", 3),
    "patients.prescription": ("inline:visitations", "prescriptions", 3),
    "patients.allergy": ("inline:visitations", "allergies", 3),
    "patients.notes": ("inline:visitations", "clinical-notes", 3),
    "patients.medicalhistory": ("inline:visitations", "medical-histories", 3),
    # ── pharmacies ──
    "pharmacies.pharmacyprofile": ("resource", "pharmacies", 0),
    "pharmacies.drugcategory": ("inline:pharmacies", "drug-categories", 4),
    "pharmacies.drug": ("resource", "drugs", 0),
    "pharmacies.drugsupplier": ("resource", "suppliers", 4),
    "pharmacies.drugbatch": ("resource", "drug-batches", 4),
    "pharmacies.stockmovement": ("resource", "stock-movements", 4),
    "pharmacies.order": ("resource", "orders", 0),
    "pharmacies.pharmacyorder": ("resource", "pharmacy-orders", 4),
    "pharmacies.orderitem": ("inline:orders", "order-items", 0),
    "pharmacies.payment": ("resource", "payments", 0),
    "pharmacies.paymentmethod": ("resource", "payment-methods", 4),
    "pharmacies.callbackdata": ("resource", "callback-data", 4),
    "pharmacies.settlement": ("resource", "settlements", 4),
    "pharmacies.settlementorder": ("inline:settlements", "settlement-orders", 4),
    "pharmacies.settlementpayout": ("resource", "settlement-payouts", 4),
    # ── partners ──
    "partners.partnerprofile": ("resource", "partners", 0),
    "partners.subsidy": ("resource", "subsidies", 0),
    "partners.programpartnershiprequest": ("resource", "partnership-requests", 0),
    "partners.programmonitor": ("resource", "program-monitors", 5),
    # ── chat ──
    "chat.chat": ("resource", "chats", 8),
    "chat.message": ("inline:chats", "chat-messages", 8),
    "chat.aichatsession": ("resource", "ai-sessions", 8),
    "chat.aichatmessage": ("inline:ai-sessions", "ai-messages", 8),
    "chat.aiabuseevent": ("resource", "ai-abuse-events", 8),
    # ── public_api ──
    "public_api.contactenquiry": ("resource", "contact-enquiries", 0),
}

# content-type model_name → portal resource key (for audit-log links)
MODEL_TO_RESOURCE = {
    "customuser": "users", "role": "roles", "userrole": "user-roles",
    "organization": "organizations", "staff": "organization-staff",
    "healthprogram": "health-programs", "participant": "participants",
    "facilityprofile": "facilities", "facilityappointment": "facility-appointments",
    "professionalprofile": "professionals", "patientprofile": "patients",
    "visitation": "visitations", "pharmacyprofile": "pharmacies", "drug": "drugs",
    "order": "orders", "orderitem": "order-items", "payment": "payments",
    "partnerprofile": "partners", "subsidy": "subsidies",
    "programpartnershiprequest": "partnership-requests",
    "contactenquiry": "contact-enquiries", "securityevent": "security-events",
    "profession": "professions", "healthprogramtype": "program-catalogs",
}
