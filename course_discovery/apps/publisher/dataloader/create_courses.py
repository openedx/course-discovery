import io
import logging

import requests
from django.core.files import File

from course_discovery.apps.publisher.choices import CourseRunStateChoices, CourseStateChoices, PublisherUserRole
from course_discovery.apps.publisher.models import Course, CourseRun, CourseRunState, CourseState, Seat

logger = logging.getLogger(__name__)


def execute_query(start_id, end_id, create_run):
    """ Execute query according to the range."""

    from course_discovery.apps.course_metadata.models import Course as CourseMetaData

    for course in CourseMetaData.objects.select_related('canonical_course_run', 'level_type', 'video').filter(
            id__range=(start_id, end_id)):

        process_course(course, create_run)


def process_course(meta_data_course, create_run, course_run=None):
    """ Create or update the course."""

    # if course has more than 1 organization don't import that course. Just log the entry.
    # that course will import manually.
    organizations = meta_data_course.authoring_organizations.all()

    try:
        available_organization = organizations_requirements(organizations, meta_data_course)

        if not available_organization:
            return

        create_or_update_course(meta_data_course, available_organization, create_run, course_run=course_run)

    except Exception:  # pylint: disable=broad-except
        logger.exception('Exception appear for course-id [%s].', meta_data_course.uuid)


def create_or_update_course(meta_data_course, available_organization, create_run, course_run=None):

    primary_subject = None
    secondary_subject = None
    tertiary_subject = None

    for i, subject in enumerate(meta_data_course.subjects.all()):
        if i == 0:
            primary_subject = subject
        elif i == 1:
            secondary_subject = subject
        elif i == 2:
            tertiary_subject = subject

    defaults = {
        'title': meta_data_course.title, 'number': meta_data_course.number,
        'short_description': meta_data_course.short_description,
        'full_description': meta_data_course.full_description,
        'level_type': meta_data_course.level_type,
        'primary_subject': primary_subject, 'secondary_subject': secondary_subject,
        'tertiary_subject': tertiary_subject,
        'video_link': meta_data_course.video.src if meta_data_course.video else None,
        'expected_learnings': meta_data_course.outcome,
        'prerequisites': meta_data_course.prerequisites_raw,
        'syllabus': meta_data_course.syllabus_raw,
    }

    publisher_course, created = Course.objects.update_or_create(
        course_metadata_pk=meta_data_course.id,
        defaults=defaults
    )

    transfer_course_image(meta_data_course, publisher_course)

    if created:
        if available_organization:
            publisher_course.organizations.add(available_organization)

        # marked course as approved with related fields.
        state, created = CourseState.objects.get_or_create(course=publisher_course)
        if created:
            state.approved_by_role = PublisherUserRole.MarketingReviewer
            state.owner_role = PublisherUserRole.MarketingReviewer
            state.marketing_reviewed = True
            state.name = CourseStateChoices.Approved
            state.save()

        logger.info('Import course with id [%s], number [%s].', publisher_course.id, publisher_course.number)

    if create_run:
        # create canonical course-run against the course.
        create_course_runs(meta_data_course, publisher_course, course_run=course_run)


def transfer_course_image(meta_data_course, publisher_course):
    if meta_data_course.image:
        publisher_course.image.save(
            meta_data_course.image.name,
            meta_data_course.image.file
        )
    elif meta_data_course.card_image_url:
        response = requests.get(meta_data_course.card_image_url)
        if response.status_code == 200:
            img_name = meta_data_course.card_image_url.split('/')[-1]
            with io.BytesIO() as fp:
                fp.write(response.content)
                publisher_course.image.save(img_name, File(fp))
        else:
            logger.error(
                'Failed to download image for course [%s] from [%s]. Server responded with status [%d].',
                meta_data_course.uuid,
                meta_data_course.card_image_url,
                response.status_code
            )


def create_course_runs(meta_data_course, publisher_course, course_run=None):
    # If we have a provided course run, update that in Publisher instead of the Canonical Run
    if course_run:
        create_course_run(publisher_course, course_run)
    # If we only want to update the canonical course run for the course instead
    else:
        # create or update canonical course-run for the course.
        canonical_course_run = meta_data_course.canonical_course_run

        if canonical_course_run and canonical_course_run.key:
            create_course_run(publisher_course, canonical_course_run)
        else:
            logger.warning(
                'Canonical course-run not found for metadata course [%s].', meta_data_course.uuid
            )


def create_course_run(publisher_course, course_run):
    defaults = {
        'course': publisher_course,
        'start': course_run.start, 'end': course_run.end,
        'min_effort': course_run.min_effort, 'max_effort': course_run.max_effort,
        'language': course_run.language, 'pacing_type': course_run.pacing_type,
        'length': course_run.weeks_to_complete,
        'card_image_url': course_run.card_image_url,
        'lms_course_id': course_run.key,
        'short_description_override': course_run.short_description_override
    }

    publisher_course_run, created = CourseRun.objects.update_or_create(
        lms_course_id=course_run.key, defaults=defaults
    )

    # add many to many fields.
    publisher_course_run.transcript_languages.add(*course_run.transcript_languages.all())
    publisher_course_run.staff.add(*course_run.staff.all())
    publisher_course_run.language = course_run.language

    # Initialize workflow for Course-run.
    if created:
        state, created = CourseRunState.objects.get_or_create(course_run=publisher_course_run)
        if created:
            state.approved_by_role = PublisherUserRole.ProjectCoordinator
            state.owner_role = PublisherUserRole.Publisher
            state.preview_accepted = True
            state.name = CourseRunStateChoices.Published
            state.save()

        logger.info(
            'Import course-run with id [%s], lms_course_id [%s].',
            publisher_course_run.id, publisher_course_run.lms_course_id
        )

    # create seat against the course-run.
    create_seats(course_run, publisher_course_run)


def create_seats(metadata_course_run, publisher_course_run):
    # create or update canonical course-run related seats..
    seats = metadata_course_run.seats.all()
    if seats:
        for metadata_seat in seats:
            defaults = {
                'price': metadata_seat.price, 'currency': metadata_seat.currency,
                'credit_provider': metadata_seat.credit_provider, 'credit_hours': metadata_seat.credit_hours,
                'upgrade_deadline': metadata_seat.upgrade_deadline
            }

            seat, created = Seat.objects.update_or_create(
                course_run=publisher_course_run,
                type=metadata_seat.type,
                defaults=defaults
            )

            if created:
                logger.info(
                    'Import seat with id [%s], type [%s].',
                    seat.id, metadata_seat.type
                )

    else:
        logger.warning(
            'No seats found for course-run [%s].', metadata_course_run.uuid
        )


def organizations_requirements(organizations, meta_data_course):
    """ Before adding course make sure organization exists and has OrganizationExtension
    object also.
    """
    available_organization = organizations.first()

    if not available_organization:
        logger.warning(
            'Course has no organization. Course uuid is [%s].', meta_data_course.uuid
        )
        return None

    return available_organization
