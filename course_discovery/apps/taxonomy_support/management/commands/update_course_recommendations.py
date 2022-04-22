import logging

from django.core.management import BaseCommand, CommandError
from django.utils.translation import gettext as _
from taxonomy.models import CourseSkills

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.taxonomy_support.models import CourseRecommendation, UpdateCourseRecommendationsConfig

logger = logging.getLogger(__name__)


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
            '--args-from-database',
            action='store_true',
            help=_('Use arguments from the UpdateCourseRecommendationsConfig model instead of the command line.'),
        )

    def get_args_from_database(self):
        """ Returns an options dictionary from the current UpdateCourseRecommendationsConfig model. """
        config = UpdateCourseRecommendationsConfig.get_solo()
        return {"all": config.all_courses, "uuids": config.uuids.split()}

    def update_course_recommendations(self, course, all_courses):
        """ Adds recommendations for a course. """
        CourseRecommendation.objects.filter(course=course).delete()
        course_skills = set(list(
            CourseSkills.objects.filter(course_key=course.key).values_list('skill__name', flat=True)
        ))
        course_subjects = set(list(course.subjects.all()))
        course_skills_count = len(course_skills)
        course_subjects_count = len(course_subjects)
        if course_skills_count == 0 and course_subjects_count == 0:
            return False
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
        CourseRecommendation.objects.bulk_create(recommendation_objects, batch_size=1000, ignore_conflicts=False)
        return True

    def add_recommendations(self, **kwargs):
        """ Adds recommendations for courses. """
        all_courses = Course.objects.all().prefetch_related('subjects')
        if kwargs['uuids']:
            courses = Course.objects.filter(uuid__in=kwargs['uuids']).all()
        else:
            courses = all_courses
        failures = set()
        for course in courses:
            if not self.update_course_recommendations(course, all_courses):
                failures.add(course)

        if failures:
            keys = sorted(f'{failure.key} ({failure.id})' for failure in failures)
            logger.warning(
                '[UPDATE_COURSE_RECOMMENDATIONS] Skipping the following courses: {course_keys}'.format(
                    course_keys=', '.join(keys)
                )
            )

    def handle(self, *args, **options):
        if not bool(options['args_from_database']) ^ (bool(options['uuids']) ^ bool(options['all'])):
            raise CommandError('Invalid arguments')
        options_dict = options
        if options_dict['args_from_database']:
            options_dict = self.get_args_from_database()
        self.add_recommendations(**options_dict)
