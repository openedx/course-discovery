import logging

from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand, CommandError
from django.utils.translation import ugettext as _

from course_discovery.apps.core.models import SalesforceConfiguration
from course_discovery.apps.course_metadata.models import Course as CourseMetadataCourse
from course_discovery.apps.course_metadata.models import MigrateCommentsToSalesforce
from course_discovery.apps.course_metadata.salesforce import SalesforceUtil
from course_discovery.apps.publisher.models import Course as PublisherCourse
from course_discovery.apps.publisher.models import CourseRun as PublisherCourseRun
from course_discovery.apps.publisher_comments.models import Comments

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (_(
        'Based on the configuration object, goes through all of the courses for an Organization and '
        'takes all of the Course Metadata Courses, Course Metadata Course Runs, and Publisher Comments, '
        'and writes them to Salesforce.'
    ))

    def handle(self, *args, **options):
        config = MigrateCommentsToSalesforce.get_solo()
        orgs = config.orgs.all()
        if not orgs:
            logger.error(_(
                'No organizations were defined. Please add organizations to the MigrateCommentsToSalesforce model.'
            ))
            raise CommandError(_('No organizations were defined.'))
        partner = config.partner
        if not partner:
            logger.error(_('No partner was defined. Please add a partner to the MigrateCommentsToSalesforce model.'))
            raise CommandError(_('No partner was defined.'))
        try:
            util = SalesforceUtil(partner)
        except SalesforceConfiguration.DoesNotExist:
            logger.error(_('Salesforce configuration for {} does not exist').format(partner.name))
            raise CommandError(_('Salesforce configuration for {} does not exist').format(partner.name))
        for org in orgs:
            logger.info(_('Executing for Organization: {}').format(org.name))
            courses = CourseMetadataCourse.objects.filter_drafts().filter(
                authoring_organizations__in=[org]
            )
            logger.info(_('Found {} courses for {}').format(len(courses), org.name))
            for course in courses:
                # Just need to create a case for the course here, as it will also create the Org and the Course itself
                util.create_case_for_course(course)
                logger.info(_('Creating Salesforce Case for Course: {}').format(course.key))
                comments = []

                # Don't just get the PublisherCourse from CourseMetadataCourse, as they might not match
                # Instead get it from the course run keys that DO match, and set them here
                publisher_courses = set()
                for course_run in course.course_runs.all():
                    logger.info(_('Creating Salesforce Course_Run__c for Course Run: {}').format(course_run.key))
                    util.create_course_run(course_run)
                    # Start at the course_run level because that's the only real way to get the Publisher Course
                    try:
                        publisher_course_run = PublisherCourseRun.objects.select_related('course').get(
                            lms_course_id=course_run.key
                        )
                    except PublisherCourseRun.DoesNotExist:
                        logger.warning(_('No PublisherCourseRun found for {}.').format(course_run.key))
                        continue
                    publisher_courses.add(publisher_course_run.course)
                    # Order by submit_date as that is when comments were added
                    publisher_course_run_comments = Comments.objects.filter(
                        content_type=ContentType.objects.get_for_model(PublisherCourseRun),
                        object_pk=publisher_course_run.id,
                    ).select_related('user')
                    for comment in publisher_course_run_comments:
                        user_comment_body = util.format_user_comment_body(
                            comment.user, comment.comment, course_run_key=course_run.key
                        )
                        comments.append({
                            'ParentId': course.salesforce_case_id,
                            'Body': user_comment_body,
                            # Use modified for CreatedDate as that is the time this exact comment began to exist
                            'CreatedDate': comment.modified.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        })
                if publisher_courses:
                    publisher_course_ids = [publisher_course.id for publisher_course in publisher_courses]
                    publisher_course_comments = Comments.objects.filter(
                        content_type=ContentType.objects.get_for_model(PublisherCourse),
                        object_pk__in=publisher_course_ids,
                    ).select_related('user')
                    for comment in publisher_course_comments:
                        user_comment_body = util.format_user_comment_body(comment.user, comment.comment)
                        comments.append({
                            'ParentId': course.salesforce_case_id,
                            'Body': user_comment_body,
                            # Use modified for CreatedDate as that is the time this exact comment began to exist
                            'CreatedDate': comment.modified.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        })
                    if comments:
                        util.client.bulk.FeedItem.insert(comments)
                        logger.info(_('Inserted {} comments for {}').format(len(comments), course.title))
                else:
                    logger.warning(_('No PublisherCourses found for {}').format(course.key))
