from django.apps import apps
from django.db.models.signals import post_delete, post_save

from course_discovery.apps.api.cache import api_change_receiver


# Invalidate API cache when any model in the course_metadata app is saved or
# deleted. Given how interconnected our data is and how infrequently our models
# change (data loading aside), this is a clean and simple way to ensure correctness
# of the API while providing closer-to-optimal cache TTLs.
for model in apps.get_app_config('course_metadata').get_models():
    for signal in (post_save, post_delete):
        signal.connect(api_change_receiver, sender=model)
