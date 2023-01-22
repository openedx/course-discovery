"""
Utilities for models and model fields.
"""


def has_model_changed(field_tracker, external_keys=None, excluded_fields=None):
    """
    Returns True if the model has changed, False otherwise.

    Args:
        field_tracker (FieldTracker): FieldTracker instance
        external_keys (list): Names of the Foreign Keys to check

    Returns:
        Boolean indicating if model or associated keys have changed.
    """
    external_keys = external_keys if external_keys else []
    excluded_fields = excluded_fields if excluded_fields else []

    changed = field_tracker.changed()
    for field in excluded_fields:
        changed.pop(field, None)

    return len(changed) or any(
        item.has_changed for item in external_keys if hasattr(item, 'has_changed')
    )
