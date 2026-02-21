from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User, GuardianStudentRelationship


class Command(BaseCommand):
    help = 'Delete guardian users who are not linked to any student (orphaned guardians)'

    def handle(self, *args, **options):
        self.stdout.write('Scanning for orphaned guardians...')
        # Find guardians with zero relationships
        guardians = User.objects.filter(role='guardian')
        count_deleted = 0

        for guardian in guardians:
            rel_count = GuardianStudentRelationship.objects.filter(guardian=guardian).count()
            if rel_count == 0:
                try:
                    with transaction.atomic():
                        self.stdout.write(f'Deleting guardian: {guardian.email} (id={guardian.pk})')
                        guardian.delete()
                        count_deleted += 1
                except Exception as e:
                    self.stderr.write(f'Failed to delete guardian {guardian.email}: {e}')

        self.stdout.write(self.style.SUCCESS(f'Done. Deleted {count_deleted} orphaned guardians.'))
