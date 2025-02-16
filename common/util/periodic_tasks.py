from typing import Optional

from django_celery_beat.models import PeriodicTask


def get_task_by_name(name: str) -> Optional[PeriodicTask]:
    try:
        return PeriodicTask.objects.get(name=name)
    except PeriodicTask.DoesNotExist:
        return None


def toggle_tasks(name, enabled):
    qs = PeriodicTask.objects.all()
    for task in qs:
        if task.name.startswith(name):
            task.enabled = enabled
            task.save()