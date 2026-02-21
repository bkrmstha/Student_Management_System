from django.db.models.signals import pre_delete, post_delete
from django.dispatch import receiver
from .models import StudentProfile, GuardianStudentRelationship, User


@receiver(pre_delete, sender=StudentProfile)
def delete_orphaned_guardians_on_studentprofile_delete(sender, instance, **kwargs):
    """
    When a StudentProfile is deleted, remove guardian users who are only linked
    to that student. This runs before the StudentProfile deletion so we can
    inspect relationships.
    """
    student_user = instance.user

    # Collect guardians linked to this student
    relationships = GuardianStudentRelationship.objects.filter(student=student_user)
    guardians_to_check = [rel.guardian for rel in relationships]

    for guardian in guardians_to_check:
        remaining = GuardianStudentRelationship.objects.filter(guardian=guardian).exclude(student=student_user).count()
        if remaining == 0:
            # Delete guardian user which will cascade to guardian_profile and relationships
            try:
                guardian.delete()
            except Exception:
                # Be defensive: ignore failures here to avoid blocking student deletion
                pass


@receiver(pre_delete, sender=User)
def delete_orphaned_guardians_on_user_delete(sender, instance, **kwargs):
    """
    If a student User is deleted directly (instead of StudentProfile), ensure
    guardians who were only linked to that student are removed as well.
    """
    # Only act for student users
    if not getattr(instance, 'role', None) == 'student':
        return

    student_user = instance
    relationships = GuardianStudentRelationship.objects.filter(student=student_user)
    guardians_to_check = [rel.guardian for rel in relationships]

    for guardian in guardians_to_check:
        remaining = GuardianStudentRelationship.objects.filter(guardian=guardian).exclude(student=student_user).count()
        if remaining == 0:
            try:
                guardian.delete()
            except Exception:
                pass


@receiver(post_delete, sender=GuardianStudentRelationship)
def delete_guardian_when_last_relationship_removed(sender, instance, **kwargs):
    """
    When a GuardianStudentRelationship is removed (for whatever reason), check
    if the guardian still has any student relationships. If none remain and the
    guardian user still exists, delete the guardian user.
    """
    guardian = instance.guardian

    # Ensure guardian still exists in DB
    if not User.objects.filter(pk=guardian.pk, role='guardian').exists():
        return

    remaining = GuardianStudentRelationship.objects.filter(guardian=guardian).count()
    if remaining == 0:
        try:
            User.objects.filter(pk=guardian.pk).delete()
        except Exception:
            pass
