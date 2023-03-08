from celery.task import task
from celery.utils.log import get_task_logger
from django.core import management


from course_discovery.apps.course_metadata.data_loaders.api import (
    CoursesApiDataLoader,
    EcommerceApiDataLoader,
    WordPressApiDataLoader,
)
from course_discovery.apps.core.models import Partner

LOGGER = get_task_logger(__name__)


@task()
def run_dataloader(partner, course_id, service):
    partner = Partner.objects.get(short_code=partner)

    pipeline = {
        'lms': (CoursesApiDataLoader, partner.courses_api_url),
        'ecommerce': (EcommerceApiDataLoader, partner.ecommerce_api_url),
        'wordpress': (WordPressApiDataLoader, partner.marketing_site_api_url),
    }

    dataloader, api_url = pipeline.get(service)
    LOGGER.info('Executing Loader [{}]'.format(api_url))

    dataloader(
        partner=partner,
        api_url=api_url,
        max_workers=1,
        course_id=course_id
    ).ingest()

    if service == 'wordpress':
        management.call_command('update_index', '--disable-change-limit')
        management.call_command('remove_unused_indexes')
