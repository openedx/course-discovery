import logging

from django.core.management import BaseCommand

from course_discovery.apps.course_metadata.exceptions import MarketingSiteAPIClientException, PersonToMarketingException
from course_discovery.apps.course_metadata.models import CourseRun, DrupalPublishUuidConfig, Person
from course_discovery.apps.course_metadata.people import MarketingSitePeople
from course_discovery.apps.course_metadata.publishers import CourseRunMarketingSitePublisher

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Based on the configuration object, publishes out objects to the marketing site'

    def handle(self, *args, **options):
        config = DrupalPublishUuidConfig.get_solo()

        # Publish course runs
        if config.course_run_ids:
            course_run_ids = config.course_run_ids.split(',')
            course_runs = CourseRun.objects.filter(key__in=course_run_ids)
            for course_run in course_runs:
                publisher = CourseRunMarketingSitePublisher(course_run.course.partner)
                publisher.publish_obj(course_run, include_uuid=True)

        # Publish people
        if config.push_people:
            publisher = MarketingSitePeople()
            for person in Person.objects.all():
                logger.info('Updating person node %s [%s].', person.slug, person.uuid)
                try:
                    publisher.update_or_publish_person(person)
                except (PersonToMarketingException, MarketingSiteAPIClientException):
                    logger.exception(
                        'An error occurred while updating person %s on the marketing site.', person.full_name,
                    )
