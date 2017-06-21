import logging

from course_discovery.apps.course_metadata.models import CourseRun as CourseRunMetaData
from course_discovery.apps.publisher.models import CourseRun

logger = logging.getLogger(__name__)


def get_and_update_course_runs(start_id, end_id):
    """ Execute query according to the range."""

    for course_run in CourseRun.objects.filter(id__range=(start_id, end_id)):
        update_course_run(course_run)


def update_course_run(publisher_course_run):
    """ Update the publisher course."""
    try:
        if publisher_course_run.lms_course_id:
            course_run_metadata = CourseRunMetaData.objects.filter(key=publisher_course_run.lms_course_id).first()
            if (
                course_run_metadata and
                (
                    course_run_metadata.short_description_override or course_run_metadata.full_description_override or
                    course_run_metadata.title_override
                )
            ):
                publisher_course_run.short_description_override = course_run_metadata.short_description_override
                publisher_course_run.full_description_override = course_run_metadata.full_description_override
                publisher_course_run.title_override = course_run_metadata.title_override

                publisher_course_run.save()
                logger.info(
                    'Update course-run import with id [%s], lms_course_id [%s].',
                    publisher_course_run.id, publisher_course_run.lms_course_id
                )

    except:  # pylint: disable=bare-except
        logger.error('Exception appear in updating course-run-id [%s].', publisher_course_run.pk)
