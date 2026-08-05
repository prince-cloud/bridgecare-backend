# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run server
python manage.py runserver

# Migrations
python manage.py makemigrations <app_name>
python manage.py migrate

# Run all tests
python manage.py test

# Run tests for a single app
python manage.py test accounts

# Celery worker + beat scheduler
celery -A config worker -l info
celery -A config beat -l info

# Django shell
python manage.py shell
```

Docker alternative:
```bash
docker-compose up -d --build
docker-compose exec web python manage.py migrate
```

Admin: `http://localhost:8000/crt/`  
API docs: `http://localhost:8000/crt-docs/`

## Architecture Overview

Django 6 REST API for a healthcare platform. Uses ASGI (Daphne) for WebSocket support. Celery + Redis for async tasks. PostgreSQL as primary DB.

### Apps and Responsibilities

| App | Purpose |
|-----|---------|
| `accounts` | CustomUser model, JWT auth, OTP, MFA, roles, audit logging |
| `communities` | Organizations (NGOs/CBOs), health programs, surveys, interventions, locum jobs |
| `facilities` | Health facility profiles, facility staff |
| `professionals` | Doctor/nurse profiles, specializations, licensing |
| `patients` | Patient profiles, visitations, prescriptions, diagnoses, vitals |
| `pharmacies` | Drug inventory, orders, suppliers, Paystack settlements |
| `chat` | Patient-professional messaging, AI chat sessions (LangChain/LangGraph) |
| `public_api` | Public-facing endpoints under `/appapi/v1/` |
| `helpers` | Shared utilities: custom exceptions, access control (`access_guardian.py`) |
| `api` | Paystack payment API wrapper |
| `admin_api` | Operator admin API (all admin CRUD/dashboards), `IsPlatformAdmin`-gated |
| `config` | Settings, Celery app, URL routing, custom exception handler, pagination |

### URL Structure

```
/crt/                              → Django admin (Unfold UI)
/auth/                             → Custom auth (users, roles, profiles)
/accounts/                         → django-allauth
/communities/<uuid:org_id>/        → Community features (org-scoped)
/facilities/                       → Facility management
/professionals/                    → Professional profiles
/patients/                         → Patient records
/pharmacies/                       → Pharmacy + inventory
/chat/                             → Messaging
/appapi/v1/                        → Public API
/admin-api/                        → Operator admin API (admin_api app)
/accept-staff-invite/              → Public staff-invite acceptance
/verify/certificate/<code>/        → Public certificate verify + /download/
```

### admin_api app

Self-contained admin backend for the `/control` frontend. Every endpoint is `IsPlatformAdmin` (is_staff OR is_superuser). It imports existing models/serializers internally but exposes its **own** endpoint surface — never reuse existing app URLs from here. Layout: `permissions.py`, `base.py` (`AdminModelViewSet` / `AdminReadOnlyViewSet`), `views.py` (`AdminMeView`), `dashboards.py`, and `resources/<app>.py` (one per source app). `urls.py` auto-loads each via its `RESOURCE_MODULES` list + the module's `register(router)`. To add a resource: add a viewset to the relevant `resources/<app>.py` and register it.

### Identity / staff / multi-profile

One human = one `CustomUser` (username=email; email/phone not unique columns but effectively unique via username + signup OTP checks). Org staff is a **membership** (`communities.Staff`, status pending/active/revoked), created via invite (`StaffViewSet` + public `AcceptStaffInviteView`); staff appear as community_profile "contexts" alongside their own profiles. A user adds more profiles via `/auth/add-profile/`, `/auth/attach-patient-profile/`, `/auth/attach-profile/` (signup wizards run in add-mode with `?add=1`). Org access: `communities/permissions.py` `OrganizationMemberRequired` / `user_org_relationship` (owner OR active staff). Password reset: `/auth/request-password-reset/` + `/auth/reset-password/` (Django `default_token_generator`, `PASSWORD_RESET_TIMEOUT`).

### Authentication

Dual system: JWT (primary) + django-allauth sessions (secondary).
- Access token: 3 hours; Refresh token: 7 days
- Account locks after 5 failed login attempts (30 min)
- MFA via SMS, email, or TOTP
- Email-only login (no username)

### Key Model Patterns

- **UUID primary keys** on all models
- **`created_at` / `updated_at`** timestamps on all models
- **Platform-specific profiles** are OneToOne with `CustomUser` — created automatically via `post_save` signal in `accounts/models.py`; uses lazy imports to avoid circular dependencies
- **Slug fields** auto-generated on Organization, FacilityProfile, and LocumJob models
- **`JSONField`** used for flexible data: device_info, location, permissions, custom vitals, intervention fields
- **`PhoneNumberField`** (from `phonenumber_field`) for all phone numbers; defaults to Ghana region

### Outreach data entry (13 July 2026 client review)

Interventions are structured in three sections via `InterventionField.section`:
`PARTICIPANT` / `VITALS` / `INTERVENTION`. Standard participant details
(name, phone, gender, age or DOB, location) live on `Participant`.

**Nothing about a participant is required, including the phone number.**
Identity is carried by `participant_code` — the org prefix from
`Organization.participant_code_prefix` plus four random characters (e.g.
`SJ7K2M`), assigned on every save and unique platform-wide. The random tail is
deliberate: the code is the lookup handle and the lookup returns name, phone,
age and location, so sequential codes would let one slip enumerate everyone.
The alphabet excludes `O/0 I/1/L S/5 Z/2` because staff transcribe these by
hand off paper slips.

`sync.resolve_participant()` is the single find-or-create used by **both** the
live submission and the offline replay — matching on explicit id, then
`participant_code`, then phone number. Blank incoming values never overwrite
stored ones. Codes are searchable in intervention responses, and
`participants/lookup/?code=` resolves a code, a phone number, or an unambiguous
name.

`InterventionField.field_key` tags standard measurements (height, weight, bmi,
blood_pressure…). BMI is always `is_computed` and derived server-side in
`communities/vitals.py`; client-supplied values for computed fields are ignored.
Blood pressure is forced to TEXT so "120/80" is stored verbatim.

`ProgramIntervention.title` is the organiser's own name for an intervention;
`display_title` falls back to the type name when it is blank and is the single
place that rule lives. Use it — never `intervention_type.name` — wherever an
intervention is named, or two same-type interventions in one programme become
indistinguishable.

Note `ParticipantReadSerializer` (rendering saved records — carries `id` and
`participant_code`) vs `ParticipantSerializer` (input only). They previously
shared one name, so the second silently shadowed the first.

`InterventionTemplate` / `InterventionTemplateField` hold reusable field sets.
The platform defaults are seeded by migration `communities/0024`, so **any
deploy that runs `migrate` gets them** — deployment does not run the seeding
command. Re-seed or refresh manually with
`python manage.py seed_intervention_templates` (`--reset` replaces fields on
existing templates).

Definitions live in `communities/intervention_template_data.py` — plain
strings, no model or enum imports, so the migration can use historical models
and the command the live ones. **Edit them there, not in either caller.** A
test asserts those strings still match the real `InterventionField` choices,
so a renamed choice fails loudly instead of seeding values the app rejects.

Key endpoints under `/communities/<org_id>/`:
- `intervention-templates/` + `<id>/apply/` + `<id>/duplicate/`
- `participants/queue-slips/` — pre-allocate codes for printed paper slips
- `participants/lookup/?code=` — find a participant by slip code or phone
- `participants/<id>/history/` — read-only cross-intervention record + latest vitals
- `intervention-answers/sync/` — offline queue upload

These use `OrganizationDataEntryAllowed` (owner, active staff, **or** a
professional with an ACCEPTED invitation) rather than `OrganizationMemberRequired`.

### Offline sync

`communities/sync.py`. Records captured offline carry a client-generated
`client_uuid`; replaying one returns the original result instead of duplicating.
Submissions for the same (participant, intervention) **merge** into one record,
and field values resolve last-write-wins on `InterventionResponseValue.recorded_at`
(when the measurement was taken, not when it uploaded), so a stale queued reading
cannot overwrite a newer correction. Rejected values come back in `conflicts`.
`InterventionResponse.recorded_at` / `entry_mode` distinguish live capture from
paper transcription so reports use the collection date.

### Certificates

`communities/certificate_generator.py` renders one fixed BridgeCare design.
The top lock-up is "organisation logo │ BridgeCare mark", centred as a group;
with no organisation logo the BridgeCare mark is centred alone. Resolve logos
through `_logo_source()`, never `file.path` — the default storage raises
`NotImplementedError` for `path()`, which the renderer's catch-all swallowed,
so the organisation logo silently never appeared.

**The PDF is written once**, by `accounts.tasks.send_certificate_email` (a
Celery task), and then served from storage — the public download view only
generates when `certificate_file` is empty. A design change therefore does not
reach existing certificates. Re-render them with:

```bash
python manage.py regenerate_certificates --organization "St. Joana" --dry-run
python manage.py regenerate_certificates --code ABC123
python manage.py regenerate_certificates --all
```

Only the file changes; `verification_code` / `verification_hash` are untouched,
so certificates already issued still verify. Because generation happens in
Celery, **the worker must be restarted** to pick up generator changes — the
Django dev server auto-reloads, the worker does not.

### Transactional email

`accounts/tasks.py` — `deliver_email()` renders and sends, preferring the
`AWS_EMAIL_URL` relay and falling back to Django SMTP when it is unset (a blank
URL previously dropped mail silently). Use `generic_send_mail.delay(...)` for
fire-and-forget, or `send_mail_now(...)` when the caller must know the true
outcome (password reset). Every attempt is recorded in `accounts.EmailDeliveryLog`
and failures log `EMAIL_DELIVERY_FAILED` for alerting.

### AI assistant guards

`chat/guards.py` enforces the free-question quota server-side (Redis, keyed to
user or IP+thread, so a refresh cannot reset it), scores prompts for injection
patterns, and applies a cool-down after repeated hits. `chat/scope.py` runs an
output-side scope check — the input classifier alone let health-framed off-topic
requests through. Flagged activity is written to `chat.AIAbuseEvent`.

### Custom Exceptions

Define new exceptions in `helpers/exceptions.py`. The custom DRF exception handler is in `config/exceptions.py` and returns structured error responses with error codes.

### Async Tasks (Celery)

Tasks live in each app's `tasks.py`. Key tasks:
- `accounts/tasks.py`: `generic_send_mail()`, `generic_send_sms()` — email uses Jinja2 templates
- `pharmacies/tasks.py`: `create_paystack_recipient()`, `initiate_paystack_transfer()`
- Beat schedule: daily pharmacy settlement at 23:55 UTC (`config/celery.py`)

```python
from config import celery_app

@celery_app.task
def my_task(param):
    pass

my_task.delay(value)
```

### Settings & Environment

Single settings file: `config/settings.py`, fully env-driven via `.env`. Key variables:

```
DEBUG, SECRET_KEY, ALLOWED_HOSTS
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT
REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD, REDIS_USE_TLS
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME  # set USE_S3=true to enable
OPENAI_API_KEY, OPENAI_MODEL
PAYSTACK_PRIVATE_KEY, PAYSTACK_PUBLIC_KEY
MNOTIFY_SENDER_ID, MNOTIFY_API_KEY
CHAT_ENCRYPTION_KEY, FRONTEND_URL
```

Redis DB assignments: Cache=1, Channels=0, Celery broker=2, Celery result=3.

### Pagination

`config/pagination.py` — `DefaultPagination` with page size 64.

### Access Control

`helpers/access_guardian.py` handles patient access permissions. Two models gate access:
- `PatientAccess` — professional-to-patient
- `FacilityPatientAccess` — facility-to-patient
