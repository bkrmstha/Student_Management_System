from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import Course

try:
    # Import here to avoid circular import at module load time
    from accounts.models import Batch, BatchCourse
except Exception:
    Batch = None
    BatchCourse = None


@receiver(post_save, sender=Course)
def add_course_to_active_batches(sender, instance, created, **kwargs):
    """When a new active Course is created, add it to all active Batches.

    This keeps batches in sync when courses are added via admin or API.
    """
    if not created:
        return

    if not getattr(instance, 'is_active', False):
        return

    if Batch is None or BatchCourse is None:
        # Unable to import batch models; skip gracefully
        return

    active_batches = Batch.objects.filter(is_active=True)
    for batch in active_batches:
        if not BatchCourse.objects.filter(batch=batch, course=instance).exists():
            try:
                BatchCourse.objects.create(batch=batch, course=instance, added_by=None, is_active=True)
            except Exception as e:
                # Avoid breaking save; log to console for developer
                print(f"Error adding course '{instance}' to batch '{batch}': {e}")
