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
```

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
