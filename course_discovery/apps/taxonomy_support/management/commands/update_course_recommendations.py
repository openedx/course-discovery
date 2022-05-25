import datetime
import logging

from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone as tz
from django.utils.translation import gettext as _
from taxonomy.models import CourseSkills

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.taxonomy_support.models import CourseRecommendation, UpdateCourseRecommendationsConfig

logger = logging.getLogger(__name__)

RECOMMENDATION_OBJECTS_CHUNK_SIZE = 10000


class Command(BaseCommand):
    help = _('Update the course recommendations based on skills.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Add course recommendations for all courses'
        )
        parser.add_argument(
            '-uuids',
            nargs="*",
            help='Add course recommendations for specific courses'
        )
        parser.add_argument(
            '-num-past-days',
            action='store',
            dest='num_past_days',
            type=int,
            help='Add recommendations for courses created or updated in the past n days.')
        parser.add_argument(
            '--args-from-database',
            action='store_true',
            help=_('Use arguments from the UpdateCourseRecommendationsConfig model instead of the command line.'),
        )

    def get_args_from_database(self):
        """ Returns an options dictionary from the current UpdateCourseRecommendationsConfig model. """
        config = UpdateCourseRecommendationsConfig.get_solo()
        return {'all': config.all_courses, 'uuids': config.uuids.split(), 'num_past_days': config.num_past_days}

    def get_course_recommendations(self, course, all_courses):
        """ Adds recommendations for a course. """
        course_skills = set(list(
            CourseSkills.objects.filter(course_key=course.key).values_list('skill__name', flat=True)
        ))
        course_subjects = set(list(course.subjects.all()))
        course_skills_count = len(course_skills)
        course_subjects_count = len(course_subjects)
        if course_skills_count == 0 and course_subjects_count == 0:
            return [], False
        recommendation_objects = []
        for course_candidate in all_courses:
            if course.uuid == course_candidate.uuid:
                continue
            course_candidate_skills = set(list(
                CourseSkills.objects.filter(course_key=course_candidate.key).values_list('skill__name', flat=True)
            ))
            skills_intersection = course_skills.intersection(course_candidate_skills)
            skills_intersection_length = len(skills_intersection)
            skills_intersection_ratio = skills_intersection_length / course_skills_count \
                if course_skills_count != 0 else 0
            course_candidate_subjects = set(list(course_candidate.subjects.all()))
            subjects_intersection = course_subjects.intersection(course_candidate_subjects)
            subjects_intersection_length = len(subjects_intersection)
            subjects_intersection_ratio = subjects_intersection_length / course_subjects_count \
                if course_subjects_count != 0 else 0
            if skills_intersection_length > 0 or subjects_intersection_length > 0:
                obj = CourseRecommendation(
                    course=course,
                    recommended_course=course_candidate,
                    skills_intersection_ratio=skills_intersection_ratio,
                    skills_intersection_length=skills_intersection_length,
                    subjects_intersection_ratio=subjects_intersection_ratio,
                    subjects_intersection_length=subjects_intersection_length
                )
                recommendation_objects.append(obj)
        return recommendation_objects, True

    def add_recommendations(self, **kwargs):
        """ Adds recommendations for courses. """
        all_courses = Course.objects.all().prefetch_related('subjects')
        if kwargs['uuids']:
            courses = Course.objects.filter(uuid__in=kwargs['uuids']).all()
        elif kwargs['all']:
            courses = all_courses
        else:
            num_past_days = kwargs['num_past_days'] or 10
            from_date = tz.now() - datetime.timedelta(days=num_past_days)
            courses_with_modified_skills = CourseSkills.objects.filter(
                modified__gt=from_date).values_list('course_key', flat=True)
            courses = all_courses.filter(Q(created__gt=from_date) | Q(key__in=list(courses_with_modified_skills)))
        logger.info(
            '[UPDATE_COURSE_RECOMMENDATIONS] Updating {course_count} courses'.format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                course_count=courses.count()
            )
        )
        failures = set()
        recommendation_object_chunks = []
        for course in courses:
            recommendation_objects, success = self.get_course_recommendations(course, all_courses)
            if success:
                recommendation_object_chunks.extend(recommendation_objects)
                CourseRecommendation.objects.filter(course=course).delete()
            else:
                failures.add(course)
            if len(recommendation_object_chunks) > RECOMMENDATION_OBJECTS_CHUNK_SIZE:
                CourseRecommendation.objects.bulk_create(recommendation_object_chunks, batch_size=1000)
                recommendation_object_chunks.clear()
        CourseRecommendation.objects.bulk_create(recommendation_object_chunks, batch_size=1000)
        if failures:
            keys = sorted(f'{failure.key} ({failure.id})' for failure in failures)
            logger.warning(
                '[UPDATE_COURSE_RECOMMENDATIONS] Skipping the following courses: {course_keys}'.format(  # lint-amnesty, pylint: disable=logging-format-interpolation
                    course_keys=', '.join(keys)
                )
            )

    def handle(self, *args, **options):
        if not bool(options['args_from_database']) ^ (
                bool(options['uuids']) ^ bool(options['all']) ^ bool(options['num_past_days'])):
            raise CommandError('Invalid arguments')
        options_dict = options
        if options_dict['args_from_database']:
            options_dict = self.get_args_from_database()
        self.add_recommendations(**options_dict)
