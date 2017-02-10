import waffle
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.publishers import MarketingSitePublisher


@receiver(pre_delete, sender=Program)
def delete_program(sender, instance, **kwargs):  # pylint: disable=unused-argument
    if waffle.switch_is_active('publish_program_to_marketing_site') and \
            instance.partner.has_marketing_site:
        publisher = MarketingSitePublisher()
        publisher.delete_program(instance)
