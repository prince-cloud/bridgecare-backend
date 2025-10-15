"""
Management command to set up initial authentication system roles and permissions
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Role, Facility


class Command(BaseCommand):
    help = 'Set up initial authentication system roles and permissions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset existing roles and recreate them',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Resetting existing roles...')
            Role.objects.all().delete()

        self.stdout.write('Setting up authentication system roles...')
        
        with transaction.atomic():
            # Define roles for each platform
            roles_data = [
                # Communities Platform Roles
                {
                    'name': 'Community Admin',
                    'platform': 'communities',
                    'description': 'Full administrative access to community platform',
                    'permissions': [
                        'communities.create_program',
                        'communities.edit_program',
                        'communities.delete_program',
                        'communities.view_all_programs',
                        'communities.manage_volunteers',
                        'communities.manage_organizations',
                        'communities.view_analytics',
                        'communities.export_data',
                    ]
                },
                {
                    'name': 'Program Coordinator',
                    'platform': 'communities',
                    'description': 'Can create and manage programs',
                    'permissions': [
                        'communities.create_program',
                        'communities.edit_program',
                        'communities.view_program',
                        'communities.manage_participants',
                        'communities.view_analytics',
                    ]
                },
                {
                    'name': 'Community Volunteer',
                    'platform': 'communities',
                    'description': 'Can participate in programs',
                    'permissions': [
                        'communities.view_program',
                        'communities.add_participant',
                        'communities.view_participants',
                    ]
                },

                # Health Facilities Platform Roles
                {
                    'name': 'Facility Admin',
                    'platform': 'facilities',
                    'description': 'Full administrative access to facility platform',
                    'permissions': [
                        'facilities.manage_staff',
                        'facilities.manage_patients',
                        'facilities.manage_appointments',
                        'facilities.manage_inventory',
                        'facilities.view_analytics',
                        'facilities.export_data',
                        'facilities.manage_settings',
                        'facilities.assign_roles',
                    ]
                },
                {
                    'name': 'Medical Director',
                    'platform': 'facilities',
                    'description': 'Medical oversight and patient care management',
                    'permissions': [
                        'facilities.view_patients',
                        'facilities.manage_patients',
                        'facilities.manage_appointments',
                        'facilities.prescribe_medications',
                        'facilities.view_analytics',
                        'facilities.manage_medical_records',
                    ]
                },
                {
                    'name': 'Doctor',
                    'platform': 'facilities',
                    'description': 'Patient care and medical services',
                    'permissions': [
                        'facilities.view_patients',
                        'facilities.manage_patients',
                        'facilities.manage_appointments',
                        'facilities.prescribe_medications',
                        'facilities.manage_medical_records',
                        'facilities.view_medical_history',
                    ]
                },
                {
                    'name': 'Nurse',
                    'platform': 'facilities',
                    'description': 'Nursing care and patient support',
                    'permissions': [
                        'facilities.view_patients',
                        'facilities.update_vitals',
                        'facilities.manage_appointments',
                        'facilities.view_medical_records',
                        'facilities.manage_patient_care',
                    ]
                },
                {
                    'name': 'Receptionist',
                    'platform': 'facilities',
                    'description': 'Appointment scheduling and patient registration',
                    'permissions': [
                        'facilities.view_patients',
                        'facilities.register_patients',
                        'facilities.manage_appointments',
                        'facilities.view_appointments',
                    ]
                },

                # Individual Professionals Platform Roles
                {
                    'name': 'Independent Doctor',
                    'platform': 'professionals',
                    'description': 'Independent medical practitioner',
                    'permissions': [
                        'professionals.manage_patients',
                        'professionals.schedule_consultations',
                        'professionals.prescribe_medications',
                        'professionals.apply_locum_shifts',
                        'professionals.view_earnings',
                        'professionals.manage_availability',
                        'professionals.participate_programs',
                    ]
                },
                {
                    'name': 'Independent Nurse',
                    'platform': 'professionals',
                    'description': 'Independent nursing practitioner',
                    'permissions': [
                        'professionals.manage_patients',
                        'professionals.schedule_consultations',
                        'professionals.apply_locum_shifts',
                        'professionals.view_earnings',
                        'professionals.manage_availability',
                        'professionals.participate_programs',
                    ]
                },
                {
                    'name': 'Locum Provider',
                    'platform': 'professionals',
                    'description': 'Temporary healthcare provider',
                    'permissions': [
                        'professionals.view_available_shifts',
                        'professionals.apply_locum_shifts',
                        'professionals.manage_availability',
                        'professionals.view_earnings',
                    ]
                },

                # Partners Platform Roles
                {
                    'name': 'Partner Admin',
                    'platform': 'partners',
                    'description': 'Full administrative access to partner platform',
                    'permissions': [
                        'partners.manage_organization',
                        'partners.manage_subsidies',
                        'partners.view_analytics',
                        'partners.manage_api_access',
                        'partners.export_data',
                        'partners.manage_integrations',
                    ]
                },
                {
                    'name': 'Program Manager',
                    'platform': 'partners',
                    'description': 'Manage funded programs and subsidies',
                    'permissions': [
                        'partners.view_programs',
                        'partners.manage_subsidies',
                        'partners.view_analytics',
                        'partners.export_program_data',
                    ]
                },
                {
                    'name': 'Analyst',
                    'platform': 'partners',
                    'description': 'View analytics and generate reports',
                    'permissions': [
                        'partners.view_analytics',
                        'partners.export_data',
                        'partners.view_programs',
                    ]
                },

                # Pharmacies Platform Roles
                {
                    'name': 'Pharmacy Owner',
                    'platform': 'pharmacies',
                    'description': 'Full administrative access to pharmacy platform',
                    'permissions': [
                        'pharmacies.manage_staff',
                        'pharmacies.manage_inventory',
                        'pharmacies.process_prescriptions',
                        'pharmacies.manage_deliveries',
                        'pharmacies.view_analytics',
                        'pharmacies.manage_settings',
                    ]
                },
                {
                    'name': 'Pharmacist',
                    'platform': 'pharmacies',
                    'description': 'Process prescriptions and manage medications',
                    'permissions': [
                        'pharmacies.process_prescriptions',
                        'pharmacies.manage_inventory',
                        'pharmacies.view_prescriptions',
                        'pharmacies.manage_deliveries',
                        'pharmacies.view_analytics',
                    ]
                },
                {
                    'name': 'Pharmacy Staff',
                    'platform': 'pharmacies',
                    'description': 'Support pharmacy operations',
                    'permissions': [
                        'pharmacies.view_prescriptions',
                        'pharmacies.manage_deliveries',
                        'pharmacies.update_inventory',
                    ]
                },

                # Patients/Users Platform Roles
                {
                    'name': 'Patient',
                    'platform': 'patients',
                    'description': 'Patient user with basic access',
                    'permissions': [
                        'patients.view_profile',
                        'patients.update_profile',
                        'patients.book_consultations',
                        'patients.order_medications',
                        'patients.view_medical_history',
                        'patients.request_emergency_services',
                    ]
                },
                {
                    'name': 'Caregiver',
                    'platform': 'patients',
                    'description': 'Caregiver with limited patient access',
                    'permissions': [
                        'patients.view_profile',
                        'patients.book_consultations',
                        'patients.order_medications',
                        'patients.view_medical_history',
                    ]
                },

                # System-wide Roles
                {
                    'name': 'System Admin',
                    'platform': 'patients',  # Default platform, but has cross-platform access
                    'description': 'System-wide administrative access',
                    'permissions': [
                        'system.manage_users',
                        'system.manage_roles',
                        'system.view_analytics',
                        'system.manage_security',
                        'system.export_all_data',
                        'system.manage_integrations',
                        'system.view_audit_logs',
                        'system.manage_facilities',
                    ]
                },
                {
                    'name': 'Support Agent',
                    'platform': 'patients',
                    'description': 'Customer support with limited access',
                    'permissions': [
                        'support.view_users',
                        'support.view_tickets',
                        'support.resolve_issues',
                        'support.view_basic_analytics',
                    ]
                },
            ]

            # Create roles
            created_count = 0
            for role_data in roles_data:
                role, created = Role.objects.get_or_create(
                    name=role_data['name'],
                    platform=role_data['platform'],
                    defaults={
                        'description': role_data['description'],
                        'permissions': role_data['permissions'],
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created role: {role.name} ({role.platform})')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Role already exists: {role.name} ({role.platform})')
                    )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully set up {created_count} new roles!')
        )
        
        # Create some sample facilities
        self.stdout.write('Creating sample facilities...')
        sample_facilities = [
            {
                'name': 'Tamale Teaching Hospital',
                'facility_code': 'TTH001',
                'facility_type': 'Teaching Hospital',
                'address': 'Tamale, Northern Region',
                'district': 'Tamale Metropolitan',
                'region': 'Northern Region',
                'phone_number': '+233372022000',
                'email': 'info@tth.gov.gh',
            },
            {
                'name': 'Korle-Bu Teaching Hospital',
                'facility_code': 'KBTH001',
                'facility_type': 'Teaching Hospital',
                'address': 'Korle-Bu, Greater Accra',
                'district': 'Korle-Klottey Municipal',
                'region': 'Greater Accra Region',
                'phone_number': '+233302665111',
                'email': 'info@kbth.gov.gh',
            },
            {
                'name': 'Komfo Anokye Teaching Hospital',
                'facility_code': 'KATH001',
                'facility_type': 'Teaching Hospital',
                'address': 'Kumasi, Ashanti Region',
                'district': 'Kumasi Metropolitan',
                'region': 'Ashanti Region',
                'phone_number': '+233322206040',
                'email': 'info@kath.gov.gh',
            },
            {
                'name': 'Ridge Hospital',
                'facility_code': 'RH001',
                'facility_type': 'Regional Hospital',
                'address': 'Ridge, Greater Accra',
                'district': 'Accra Metropolitan',
                'region': 'Greater Accra Region',
                'phone_number': '+233302664400',
                'email': 'info@ridge.gov.gh',
            },
            {
                'name': 'Tamale Central Hospital',
                'facility_code': 'TCH001',
                'facility_type': 'Regional Hospital',
                'address': 'Tamale, Northern Region',
                'district': 'Tamale Metropolitan',
                'region': 'Northern Region',
                'phone_number': '+233372022100',
                'email': 'info@tch.gov.gh',
            },
        ]

        facility_count = 0
        for facility_data in sample_facilities:
            facility, created = Facility.objects.get_or_create(
                facility_code=facility_data['facility_code'],
                defaults=facility_data
            )
            
            if created:
                facility_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created facility: {facility.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {facility_count} sample facilities!')
        )

        self.stdout.write(
            self.style.SUCCESS(
                '\nAuthentication system setup complete!\n'
                'You can now:\n'
                '1. Create users and assign them to appropriate roles\n'
                '2. Set up platform-specific profiles\n'
                '3. Configure MFA for enhanced security\n'
                '4. Monitor authentication events in the admin panel'
            )
        )

