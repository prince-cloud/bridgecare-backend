# Generated manually for comprehensive authentication system

import django.db.models.deletion
import django.utils.timezone
import phonenumber_field.modelfields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        # Create Facility model first (no dependencies)
        migrations.CreateModel(
            name='Facility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('facility_code', models.CharField(max_length=50, unique=True)),
                ('facility_type', models.CharField(max_length=100)),
                ('address', models.TextField()),
                ('district', models.CharField(max_length=100)),
                ('region', models.CharField(max_length=100)),
                ('phone_number', phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region=None)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Facility',
                'verbose_name_plural': 'Facilities',
                'db_table': 'facilities',
            },
        ),

        # Add new fields to CustomUser
        migrations.AddField(
            model_name='customuser',
            name='phone_number',
            field=phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region=None),
        ),
        migrations.AddField(
            model_name='customuser',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='profile_picture',
            field=models.ImageField(blank=True, null=True, upload_to='profiles/'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='platform',
            field=models.CharField(choices=[('communities', 'Communities'), ('facilities', 'Health Facilities'), ('professionals', 'Individual Professionals'), ('partners', 'Partners'), ('pharmacies', 'Pharmacies'), ('patients', 'Patients/Users')], default='patients', max_length=20),
        ),
        migrations.AddField(
            model_name='customuser',
            name='primary_role',
            field=models.CharField(choices=[('doctor', 'Doctor'), ('nurse', 'Nurse'), ('midwife', 'Midwife'), ('pharmacist', 'Pharmacist'), ('community_health_worker', 'Community Health Worker'), ('medical_assistant', 'Medical Assistant'), ('lab_technician', 'Lab Technician'), ('radiologist', 'Radiologist'), ('other', 'Other')], default='other', max_length=50),
        ),
        migrations.AddField(
            model_name='customuser',
            name='is_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='customuser',
            name='verification_level',
            field=models.CharField(choices=[('basic', 'Basic'), ('verified', 'Verified'), ('professional', 'Professional'), ('admin', 'Administrator')], default='basic', max_length=20),
        ),
        migrations.AddField(
            model_name='customuser',
            name='license_number',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='license_expiry',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='specializations',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='customuser',
            name='mfa_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='customuser',
            name='mfa_method',
            field=models.CharField(choices=[('sms', 'SMS'), ('email', 'Email'), ('totp', 'TOTP'), ('disabled', 'Disabled')], default='disabled', max_length=20),
        ),
        migrations.AddField(
            model_name='customuser',
            name='last_login_ip',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='login_attempts',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='customuser',
            name='account_locked_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='customuser',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='last_activity',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='otp',
            field=models.CharField(blank=True, max_length=6, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='otp_expiry',
            field=models.DateTimeField(blank=True, null=True),
        ),

        # Update CustomUser Meta options
        migrations.AlterModelOptions(
            name='customuser',
            options={'verbose_name': 'User', 'verbose_name_plural': 'Users'},
        ),

        # Create Role model
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('platform', models.CharField(choices=[('communities', 'Communities'), ('facilities', 'Health Facilities'), ('professionals', 'Individual Professionals'), ('partners', 'Partners'), ('pharmacies', 'Pharmacies'), ('patients', 'Patients/Users')], max_length=20)),
                ('description', models.TextField(blank=True, null=True)),
                ('permissions', models.JSONField(blank=True, default=list)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Role',
                'verbose_name_plural': 'Roles',
                'db_table': 'roles',
            },
        ),

        # Create UserProfile model
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(choices=[('communities', 'Communities'), ('facilities', 'Health Facilities'), ('professionals', 'Individual Professionals'), ('partners', 'Partners'), ('pharmacies', 'Pharmacies'), ('patients', 'Patients/Users')], max_length=20)),
                ('bio', models.TextField(blank=True, null=True)),
                ('location', models.CharField(blank=True, max_length=200, null=True)),
                ('preferred_language', models.CharField(default='en', max_length=10)),
                ('profile_data', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User Profile',
                'verbose_name_plural': 'User Profiles',
                'db_table': 'user_profiles',
            },
        ),

        # Create UserRole model
        migrations.CreateModel(
            name='UserRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_roles', to=settings.AUTH_USER_MODEL)),
                ('facility', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='role_assignments', to='accounts.facility')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_assignments', to='accounts.role')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_roles', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User Role',
                'verbose_name_plural': 'User Roles',
                'db_table': 'user_roles',
            },
        ),

        # Create MFADevice model
        migrations.CreateModel(
            name='MFADevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_type', models.CharField(choices=[('sms', 'SMS'), ('email', 'Email'), ('totp', 'TOTP'), ('backup_codes', 'Backup Codes')], max_length=20)),
                ('device_id', models.CharField(max_length=100)),
                ('device_name', models.CharField(blank=True, max_length=100, null=True)),
                ('is_verified', models.BooleanField(default=False)),
                ('is_primary', models.BooleanField(default=False)),
                ('last_used', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mfa_devices', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'MFA Device',
                'verbose_name_plural': 'MFA Devices',
                'db_table': 'mfa_devices',
            },
        ),

        # Create LoginSession model
        migrations.CreateModel(
            name='LoginSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_token', models.CharField(max_length=255, unique=True)),
                ('refresh_token', models.CharField(blank=True, max_length=255, null=True)),
                ('device_info', models.JSONField(blank=True, default=dict)),
                ('ip_address', models.GenericIPAddressField()),
                ('location', models.JSONField(blank=True, default=dict)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('last_activity', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='login_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Login Session',
                'verbose_name_plural': 'Login Sessions',
                'db_table': 'login_sessions',
            },
        ),

        # Create SecurityEvent model
        migrations.CreateModel(
            name='SecurityEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('login_success', 'Successful Login'), ('login_failed', 'Failed Login'), ('mfa_challenge', 'MFA Challenge'), ('mfa_success', 'MFA Success'), ('mfa_failed', 'MFA Failed'), ('password_change', 'Password Change'), ('account_locked', 'Account Locked'), ('account_unlocked', 'Account Unlocked'), ('suspicious_activity', 'Suspicious Activity'), ('permission_denied', 'Permission Denied'), ('data_access', 'Data Access'), ('api_access', 'API Access')], max_length=50)),
                ('severity', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], default='medium', max_length=20)),
                ('ip_address', models.GenericIPAddressField()),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('platform', models.CharField(blank=True, choices=[('communities', 'Communities'), ('facilities', 'Health Facilities'), ('professionals', 'Individual Professionals'), ('partners', 'Partners'), ('pharmacies', 'Pharmacies'), ('patients', 'Patients/Users')], max_length=20, null=True)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('is_resolved', models.BooleanField(default=False)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_events', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='security_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Security Event',
                'verbose_name_plural': 'Security Events',
                'db_table': 'security_events',
                'ordering': ['-timestamp'],
            },
        ),

        # Create AuthenticationAudit model
        migrations.CreateModel(
            name='AuthenticationAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('login', 'Login'), ('logout', 'Logout'), ('register', 'Registration'), ('password_reset', 'Password Reset'), ('email_verification', 'Email Verification'), ('mfa_setup', 'MFA Setup'), ('mfa_challenge', 'MFA Challenge'), ('account_locked', 'Account Locked'), ('account_unlocked', 'Account Unlocked'), ('profile_update', 'Profile Update'), ('role_assignment', 'Role Assignment'), ('permission_granted', 'Permission Granted'), ('permission_denied', 'Permission Denied'), ('data_access', 'Data Access'), ('data_modification', 'Data Modification')], max_length=50)),
                ('platform', models.CharField(blank=True, choices=[('communities', 'Communities'), ('facilities', 'Health Facilities'), ('professionals', 'Individual Professionals'), ('partners', 'Partners'), ('pharmacies', 'Pharmacies'), ('patients', 'Patients/Users')], max_length=20, null=True)),
                ('ip_address', models.GenericIPAddressField()),
                ('user_agent', models.TextField()),
                ('success', models.BooleanField()),
                ('details', models.JSONField(blank=True, default=dict)),
                ('resource_accessed', models.CharField(blank=True, max_length=200, null=True)),
                ('method', models.CharField(blank=True, max_length=10, null=True)),
                ('endpoint', models.CharField(blank=True, max_length=500, null=True)),
                ('response_code', models.IntegerField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='auth_audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Authentication Audit',
                'verbose_name_plural': 'Authentication Audits',
                'db_table': 'authentication_audit',
                'ordering': ['-timestamp'],
            },
        ),

        # Create DataAccessLog model
        migrations.CreateModel(
            name='DataAccessLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_type', models.CharField(choices=[('patient_data', 'Patient Data'), ('medical_records', 'Medical Records'), ('prescription_data', 'Prescription Data'), ('financial_data', 'Financial Data'), ('personal_info', 'Personal Information'), ('system_data', 'System Data')], max_length=50)),
                ('access_type', models.CharField(choices=[('view', 'View'), ('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('export', 'Export'), ('print', 'Print')], max_length=20)),
                ('resource_id', models.CharField(blank=True, max_length=100, null=True)),
                ('resource_name', models.CharField(blank=True, max_length=200, null=True)),
                ('platform', models.CharField(choices=[('communities', 'Communities'), ('facilities', 'Health Facilities'), ('professionals', 'Individual Professionals'), ('partners', 'Partners'), ('pharmacies', 'Pharmacies'), ('patients', 'Patients/Users')], max_length=20)),
                ('ip_address', models.GenericIPAddressField()),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('access_reason', models.CharField(blank=True, max_length=200, null=True)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='data_access_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Data Access Log',
                'verbose_name_plural': 'Data Access Logs',
                'db_table': 'data_access_logs',
                'ordering': ['-timestamp'],
            },
        ),

        # Create platform-specific profile models
        migrations.CreateModel(
            name='CommunityProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('organization_name', models.CharField(blank=True, max_length=200, null=True)),
                ('organization_type', models.CharField(blank=True, max_length=100, null=True)),
                ('volunteer_status', models.BooleanField(default=False)),
                ('coordinator_level', models.CharField(blank=True, max_length=50, null=True)),
                ('areas_of_focus', models.JSONField(blank=True, default=list)),
                ('organization_phone', phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region=None)),
                ('organization_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('organization_address', models.TextField(blank=True, null=True)),
                ('active_programs', models.JSONField(blank=True, default=list)),
                ('certifications', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='community_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Community Profile',
                'verbose_name_plural': 'Community Profiles',
                'db_table': 'community_profiles',
            },
        ),

        migrations.CreateModel(
            name='ProfessionalProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('practice_type', models.CharField(max_length=100)),
                ('years_of_experience', models.IntegerField(default=0)),
                ('education_background', models.JSONField(blank=True, default=list)),
                ('license_number', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('license_issuing_body', models.CharField(blank=True, max_length=100, null=True)),
                ('license_expiry_date', models.DateField(blank=True, null=True)),
                ('certifications', models.JSONField(blank=True, default=list)),
                ('availability_schedule', models.JSONField(blank=True, default=dict)),
                ('preferred_working_hours', models.JSONField(blank=True, default=dict)),
                ('travel_radius', models.IntegerField(default=0)),
                ('hourly_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('currency', models.CharField(default='GHS', max_length=3)),
                ('specializations', models.JSONField(blank=True, default=list)),
                ('languages_spoken', models.JSONField(blank=True, default=list)),
                ('emergency_contact', models.CharField(blank=True, max_length=200, null=True)),
                ('emergency_phone', phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region=None)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='professional_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Professional Profile',
                'verbose_name_plural': 'Professional Profiles',
                'db_table': 'professional_profiles',
            },
        ),

        migrations.CreateModel(
            name='FacilityProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('employee_id', models.CharField(blank=True, max_length=50, null=True)),
                ('department', models.CharField(blank=True, max_length=100, null=True)),
                ('position', models.CharField(blank=True, max_length=100, null=True)),
                ('employment_type', models.CharField(blank=True, max_length=50, null=True)),
                ('hire_date', models.DateField(blank=True, null=True)),
                ('shift_schedule', models.JSONField(blank=True, default=dict)),
                ('working_hours', models.JSONField(blank=True, default=dict)),
                ('can_prescribe', models.BooleanField(default=False)),
                ('can_access_patient_data', models.BooleanField(default=True)),
                ('can_manage_inventory', models.BooleanField(default=False)),
                ('can_schedule_appointments', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('facility', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='staff', to='accounts.facility')),
                ('supervisor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subordinates', to=settings.AUTH_USER_MODEL)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='facility_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Facility Profile',
                'verbose_name_plural': 'Facility Profiles',
                'db_table': 'facility_profiles',
            },
        ),

        migrations.CreateModel(
            name='PartnerProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('organization_name', models.CharField(max_length=200)),
                ('organization_type', models.CharField(max_length=100)),
                ('organization_size', models.CharField(blank=True, max_length=50, null=True)),
                ('organization_phone', phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region=None)),
                ('organization_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('organization_address', models.TextField(blank=True, null=True)),
                ('website', models.URLField(blank=True, null=True)),
                ('partnership_type', models.CharField(max_length=100)),
                ('partnership_status', models.CharField(default='active', max_length=50)),
                ('partnership_start_date', models.DateField(blank=True, null=True)),
                ('partnership_end_date', models.DateField(blank=True, null=True)),
                ('api_access_level', models.CharField(default='basic', max_length=50)),
                ('can_access_analytics', models.BooleanField(default=False)),
                ('can_manage_subsidies', models.BooleanField(default=False)),
                ('can_view_patient_data', models.BooleanField(default=False)),
                ('contact_person_name', models.CharField(blank=True, max_length=200, null=True)),
                ('contact_person_title', models.CharField(blank=True, max_length=100, null=True)),
                ('contact_person_phone', phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region=None)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='partner_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Partner Profile',
                'verbose_name_plural': 'Partner Profiles',
                'db_table': 'partner_profiles',
            },
        ),

        migrations.CreateModel(
            name='PharmacyProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pharmacy_name', models.CharField(max_length=200)),
                ('pharmacy_license', models.CharField(max_length=100, unique=True)),
                ('pharmacy_type', models.CharField(max_length=100)),
                ('address', models.TextField()),
                ('district', models.CharField(max_length=100)),
                ('region', models.CharField(max_length=100)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('phone_number', phonenumber_field.modelfields.PhoneNumberField(max_length=128, region=None)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('website', models.URLField(blank=True, null=True)),
                ('services_offered', models.JSONField(blank=True, default=list)),
                ('delivery_available', models.BooleanField(default=False)),
                ('delivery_radius', models.IntegerField(default=0)),
                ('operating_hours', models.JSONField(blank=True, default=dict)),
                ('pharmacist_license', models.CharField(blank=True, max_length=100, null=True)),
                ('staff_count', models.IntegerField(default=1)),
                ('payment_methods', models.JSONField(blank=True, default=list)),
                ('insurance_accepted', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pharmacy_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Pharmacy Profile',
                'verbose_name_plural': 'Pharmacy Profiles',
                'db_table': 'pharmacy_profiles',
            },
        ),

        migrations.CreateModel(
            name='PatientProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('blood_type', models.CharField(blank=True, max_length=5, null=True)),
                ('height', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('weight', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('emergency_contact_name', models.CharField(blank=True, max_length=200, null=True)),
                ('emergency_contact_phone', phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region=None)),
                ('emergency_contact_relationship', models.CharField(blank=True, max_length=100, null=True)),
                ('insurance_provider', models.CharField(blank=True, max_length=100, null=True)),
                ('insurance_number', models.CharField(blank=True, max_length=100, null=True)),
                ('preferred_payment_method', models.CharField(default='mobile_money', max_length=50)),
                ('preferred_language', models.CharField(default='en', max_length=10)),
                ('preferred_consultation_type', models.CharField(default='in_person', max_length=50)),
                ('notification_preferences', models.JSONField(blank=True, default=dict)),
                ('medical_history', models.JSONField(blank=True, default=list)),
                ('allergies', models.JSONField(blank=True, default=list)),
                ('current_medications', models.JSONField(blank=True, default=list)),
                ('home_address', models.TextField(blank=True, null=True)),
                ('work_address', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('preferred_pharmacy', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='accounts.pharmacyprofile')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='patient_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Patient Profile',
                'verbose_name_plural': 'Patient Profiles',
                'db_table': 'patient_profiles',
            },
        ),

        # Add indexes for performance
        migrations.AddIndex(
            model_name='authenticationaudit',
            index=models.Index(fields=['user', 'timestamp'], name='auth_audit_user_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='authenticationaudit',
            index=models.Index(fields=['action', 'timestamp'], name='auth_audit_action_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='authenticationaudit',
            index=models.Index(fields=['platform', 'timestamp'], name='auth_audit_platform_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='authenticationaudit',
            index=models.Index(fields=['ip_address', 'timestamp'], name='auth_audit_ip_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='dataaccesslog',
            index=models.Index(fields=['user', 'timestamp'], name='data_access_user_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='dataaccesslog',
            index=models.Index(fields=['data_type', 'timestamp'], name='data_access_type_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='dataaccesslog',
            index=models.Index(fields=['platform', 'timestamp'], name='data_access_platform_timestamp_idx'),
        ),

        # Add unique constraints
        migrations.AddConstraint(
            model_name='role',
            constraint=models.UniqueConstraint(fields=['name', 'platform'], name='unique_role_per_platform'),
        ),
        migrations.AddConstraint(
            model_name='userrole',
            constraint=models.UniqueConstraint(fields=['user', 'role', 'facility'], name='unique_user_role_facility'),
        ),
        migrations.AddConstraint(
            model_name='mfadevice',
            constraint=models.UniqueConstraint(fields=['user', 'device_id'], name='unique_user_device'),
        ),
    ]