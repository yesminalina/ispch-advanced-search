from .models import DataUpdate


def last_update(request):
    """Expone last_update (DateTimeField o None) a todas las plantillas."""
    obj = DataUpdate.objects.first()
    return {"last_update": obj.last_checked_at if obj else None}
