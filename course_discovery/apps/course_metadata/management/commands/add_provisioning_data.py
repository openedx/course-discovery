"""
Management command for adding predefined set of courses, programs, degrees
and subjects.

Example usage:
    $ ./manage.py add_provisioning_data
"""
import logging
import random
import string

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from course_discovery.apps.api.serializers import CourseRunWithProgramsSerializer, CourseWithProgramsSerializer
from course_discovery.apps.api.utils import StudioAPI
from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.management.commands.constants import STARTER_COURSES, STARTER_SUBJECTS
from course_discovery.apps.course_metadata.models import (
    Course, CourseEntitlement, CourseRunType, CourseType, Degree, LevelType, LevelTypeTranslation, Organization, Person,
    Position, Program, ProgramType, Subject
)

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Add base provisioning data to discovery.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site, _ = Site.objects.get_or_create(name='edX', defaults={
            'domain': 'localhost:18381'
        })
        self.partner, _ = Partner.objects.get_or_create(name="edX", defaults={
            'short_code': 'edx',
            'site': self.site,
            'organizations_api_url': "http://edx.devstack.lms:18000/api/organizations/v0/",
            'studio_url': "http://edx.devstack.cms:18010/"
        })
        self.org, _ = Organization.objects.get_or_create(key="edX", defaults={
            'partner': self.partner,
            'name': "edX",
        })
        self.staff = self.create_instructor("Tom Jerry")
        self.user, _ = User.objects.get_or_create(username='edX', defaults={})

    def handle(self, *args, **kwargs):
        # Create standard Level Types
        for level_type in ["Introductory", "Intermediate", "Advanced"]:
            self.create_level_type(level_type)

        # Create all subjects listed on edx.org
        for subj in STARTER_SUBJECTS:
            self.create_subject(subj)

        # Create courses using the metadata in STARTER_COURSES
        self.create_course_batch()
        # Create some programs using the courses created above
        self.create_program_batch()
        # Create some degrees too
        self.create_degree_batch()

    def get_image_file_with_dims(self, width, height):
        '''
        Get an image file (SimpleUploadedFile) with the given width and height.
        The filename is randomly generated.
        '''
        return make_image_file(''.join(random.choices(string.ascii_letters, k=6)), width, height)

    def create_level_type(self, name):
        level_type, created = LevelType.objects.get_or_create(name=name)
        if created:
            LevelTypeTranslation.objects.create(name_t=name, master=level_type, language_code='en')
        return level_type

    def create_subject(self, name):
        matching_subjects = Subject.objects.filter(translations__name=name)
        if matching_subjects:
            return matching_subjects.last()

        subject = Subject(partner=self.partner)
        subject.set_current_language = 'en'
        subject.name = name
        subject.save()
        return subject

    def create_instructor(self, name):
        name = name.replace(" ", "_")
        instructor, created = Person.objects.get_or_create(
            given_name=name,
            partner=self.partner,
            email=f"{name}@example.com",
            defaults={
                "profile_image": self.get_image_file_with_dims(110, 110),
            }
        )
        if created:
            Position.objects.create(person=instructor, title='Professor', organization=self.org)

        return instructor

    def create_course_dict(self, course_info):
        '''
        Extends course info to add dummy information about other course
        attributes
        '''
        course_dict = {
            **course_info,
            "org": f"{self.org.key}",
            "type": f"{CourseType.objects.get(slug=course_info['type']).uuid}",
            "key": f"{self.org.key}+{course_info['number']}",
            "partner": self.partner.pk,
            "level_type": "Introductory",
            "short_description": "<p>A short description of the course</p>",
            "full_description": "<p>A detailed description of the course</p>",
            "outcome": "<p>Outcomes of the course</p>",
            "course_run": {
                "prices": {**course_info['prices']},
                "start": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": (timezone.now() + timezone.timedelta(days=50)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "run_type": f"{CourseRunType.objects.get(slug=course_info['course_run']['run_type']).uuid}",
                "min_effort": 5,
                "max_effort": 10,
                "weeks_to_complete": 8,
                "go_live_date": (timezone.now() + timezone.timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "staff": [f"{self.staff.uuid}"],
            },
        }
        return course_dict

    @transaction.atomic
    def create_course(self, course_info):
        course_dict = self.create_course_dict(course_info)
        if Course.everything.filter(key=course_dict['key']):
            logger.info(f"Course with key {course_dict['key']} already exists")
            return
        subject_names = course_dict.pop('subjects')
        course_serializer = CourseWithProgramsSerializer(data=course_dict)

        if course_serializer.is_valid():
            course = course_serializer.save(draft=True)
        else:
            logger.error('Unexpected Errors while adding course.')
            raise serializers.ValidationError(course_serializer.errors)

        course.image = self.get_image_file_with_dims(1134, 675)
        subjects = list(map(lambda name: Subject.objects.filter(slug=name).first(), subject_names))
        course.subjects.set(subjects)
        course.authoring_organizations.add(self.org)

        entitlement_types = course.type.entitlement_types.all()
        prices = course_dict['prices']
        for entitlement_type in entitlement_types:
            CourseEntitlement.objects.create(
                course=course,
                mode=entitlement_type,
                price=prices.get(entitlement_type.slug, 0),
                draft=True,
            )

        course_run_fields = course_dict["course_run"]
        course_run_fields.update({"course": course.key, "pacing_type": 'instructor_paced'})
        course_run_serializer = CourseRunWithProgramsSerializer(data=course_run_fields)
        if course_run_serializer.is_valid():
            course_run = course_run_serializer.save(draft=True)
        else:
            logger.error('Unexpected Errors while adding course run.')
            raise serializers.ValidationError(course_run_serializer.errors)
        course_run.update_or_create_seats(course_run.type, prices)
        course.canonical_course_run = course_run
        course.save()

        # Push to studio
        api = StudioAPI(partner=self.partner)
        api.create_course_run_in_studio(course_run, self.user)

        # Publish the course
        if course_dict["publish"]:
            course_run.status = CourseRunStatus.Published
            course_run.save()
            course_run.update_or_create_official_version()

    def create_course_batch(self):
        for course_info in STARTER_COURSES:
            self.create_course(course_info)

    def get_program_or_degree_defaults(self, program_or_degree_type_slug):
        '''
        Get a predefined collection of base data for programs or degrees
        '''
        return {
            'type': ProgramType.objects.get(slug=program_or_degree_type_slug),
            'status': 'active',
            'partner': self.partner,
            'overview': 'This is to ease local testing and development.',
            'total_hours_of_effort': 12,
            'min_hours_effort_per_week': 1,
            'max_hours_effort_per_week': 30,
            'one_click_purchase_enabled': True,
        }

    def create_program(self, title, program_type_slug, course_list):
        if Program.objects.filter(marketing_slug=slugify(title)):
            logger.info("Program with title already exists")
            return None

        program, _ = Program.objects.update_or_create(
            title=title,
            marketing_slug=slugify(title),
            defaults=self.get_program_or_degree_defaults(program_type_slug),
        )
        program.courses.set(course_list)
        program.authoring_organizations.set([self.org])
        program.credit_backing_organizations.set([self.org])
        return program

    def create_degree(self, title, degree_type_slug, course_list):
        if Degree.objects.filter(marketing_slug=slugify(title)):
            logger.info("Degree with title already exists")
            return None

        degree, _ = Degree.objects.update_or_create(
            title=title,
            marketing_slug=slugify(title),
            defaults=self.get_program_or_degree_defaults(degree_type_slug),
        )
        degree.courses.set(course_list)
        degree.authoring_organizations.set([self.org])
        degree.credit_backing_organizations.set([self.org])
        return degree

    def create_program_batch(self):
        courses = Course.objects.order_by("-created")[0:2]
        self.create_program('Sample MicroBachelors Program', 'microbachelors', [courses[0]])
        self.create_program('Sample Masters Program', 'masters', [courses[1]])

    def create_degree_batch(self):
        courses = Course.objects.order_by("-created")[0:2]
        self.create_degree('Sample MicroBachelors Degree', 'microbachelors', [courses[0]])
        self.create_degree('Sample MicroMasters Degree', 'micromasters', [courses[1]])
