import subprocess

from celery.task import task
from celery.utils.log import get_task_logger


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

    ## Removing this piece of code for monitoring index corruption issue.
    # if service == 'wordpress':
    #     update_index_cmd = "/edx/app/discovery/venvs/discovery/bin/python /edx/app/discovery/discovery/manage.py update_index --disable-change-limit"
    #     remove_unused_index_cmd = "/edx/app/discovery/venvs/discovery/bin/python /edx/app/discovery/discovery/manage.py remove_unused_indexes"
    #     LOGGER.info('Runing update_index command ...')
    #     with subprocess.Popen(update_index_cmd, stdout=subprocess.PIPE, shell=True) as proc:
    #         LOGGER.info(proc.stdout.read())

    #     LOGGER.info('Runing remove_unused indexes command ...')
    #     with subprocess.Popen(remove_unused_index_cmd, stdout=subprocess.PIPE, shell=True) as proc:
    #         LOGGER.info(proc.stdout.read())
