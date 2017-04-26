import waffle
from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from course_discovery.apps.api.cache import api_change_receiver
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.publishers import ProgramMarketingSitePublisher


@receiver(pre_delete, sender=Program)
def delete_program(sender, instance, **kwargs):  # pylint: disable=unused-argument
    is_publishable = (
        instance.partner.has_marketing_site and
        waffle.switch_is_active('publish_program_to_marketing_site')
    )

    if is_publishable:
        publisher = ProgramMarketingSitePublisher(instance.partner)
        publisher.delete_obj(instance)


# Invalidate API cache when any model in the course_metadata app is saved or
# deleted. Given how interconnected our data is and how infrequently our models
# change (data loading aside), this is a clean and simple way to ensure correctness
# of the API while providing closer-to-optimal cache TTLs.
for model in apps.get_app_config('course_metadata').get_models():
    for signal in (post_save, post_delete):
        signal.connect(api_change_receiver, sender=model)
