# pylint: disable=test-inherits-tests
import datetime
import itertools
import re
from unittest import mock
from urllib.parse import urlencode

import ddt
import pytest
import responses
from django.test import TestCase
from django.utils.text import slugify
from haystack.query import SearchQuerySet
from opaque_keys.edx.keys import CourseKey
from pytz import UTC
from rest_framework.test import APIRequestFactory
from taggit.models import Tag
from waffle.testutils import override_switch

from course_discovery.apps.api.fields import ImageField, StdImageSerializerField
from course_discovery.apps.api.serializers import (
    AdditionalPromoAreaSerializer, AffiliateWindowSerializer, CatalogSerializer, CollaboratorSerializer,
    ContainedCourseRunsSerializer, ContainedCoursesSerializer, ContentTypeSerializer, CorporateEndorsementSerializer,
    CourseEditorSerializer, CourseEntitlementSerializer, CourseRunSearchModelSerializer, CourseRunSearchSerializer,
    CourseRunSerializer, CourseRunWithProgramsSerializer, CourseSearchModelSerializer, CourseSearchSerializer,
    CourseSerializer, CourseWithProgramsSerializer, CurriculumSerializer, DegreeCostSerializer,
    DegreeDeadlineSerializer, EndorsementSerializer, FAQSerializer, FlattenedCourseRunWithCourseSerializer,
    IconTextPairingSerializer, ImageSerializer, MinimalCourseRunSerializer, MinimalCourseSerializer,
    MinimalOrganizationSerializer, MinimalPersonSerializer, MinimalProgramCourseSerializer, MinimalProgramSerializer,
    NestedProgramSerializer, OrganizationSerializer, PathwaySerializer, PersonSearchModelSerializer,
    PersonSearchSerializer, PersonSerializer, PositionSerializer, PrerequisiteSerializer,
    ProgramsAffiliateWindowSerializer, ProgramSearchModelSerializer, ProgramSearchSerializer, ProgramSerializer,
    ProgramTypeAttrsSerializer, ProgramTypeSerializer, RankingSerializer, SeatSerializer, SubjectSerializer,
    TopicSerializer, TypeaheadCourseRunSearchSerializer, TypeaheadProgramSearchSerializer, VideoSerializer,
    get_lms_course_url_for_archived, get_utm_source_for_user
)
from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.models import Partner, User
from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin, LMSAPIClientMixin
from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Person, Program
from course_discovery.apps.course_metadata.tests.factories import (
    AdditionalPromoAreaFactory, CollaboratorFactory, CorporateEndorsementFactory, CourseEditorFactory,
    CourseEntitlementFactory, CourseFactory, CourseRunFactory, CurriculumCourseMembershipFactory, CurriculumFactory,
    CurriculumProgramMembershipFactory, DegreeCostFactory, DegreeDeadlineFactory, DegreeFactory, EndorsementFactory,
    ExpectedLearningItemFactory, IconTextPairingFactory, ImageFactory, JobOutlookItemFactory, OrganizationFactory,
    PathwayFactory, PersonAreaOfExpertiseFactory, PersonFactory, PersonSocialNetworkFactory, PositionFactory,
    PrerequisiteFactory, ProgramFactory, ProgramTypeFactory, RankingFactory, SeatFactory, SeatTypeFactory,
    SubjectFactory, TopicFactory, VideoFactory
)
from course_discovery.apps.course_metadata.utils import get_course_run_estimated_hours
from course_discovery.apps.ietf_language_tags.models import LanguageTag


def json_date_format(datetime_obj):
    return datetime_obj and datetime.datetime.strftime(datetime_obj, "%Y-%m-%dT%H:%M:%S.%fZ")


def make_request(query_param=None):
    user = UserFactory()
    if query_param:
        request = APIRequestFactory().get('/', query_param)
    else:
        request = APIRequestFactory().get('/')
    request.user = user
    return request


def serialize_language(language):
    if language.code.startswith('zh'):
        return language.name

    return language.macrolanguage


def serialize_language_to_code(language):
    return language.code


def get_uuids(items):
    return [str(item.uuid) for item in items]


class CatalogSerializerTests(ElasticsearchTestMixin, TestCase):
    def test_data(self):
        user = UserFactory()
        catalog = CatalogFactory(query='*:*', viewers=[user])  # We intentionally use a query for all Courses.
        courses = CourseFactory.create_batch(10)
        serializer = CatalogSerializer(catalog)

        expected = {
            'id': catalog.id,
            'name': catalog.name,
            'query': catalog.query,
            'courses_count': len(courses),
            'viewers': [user.username]
        }
        self.assertDictEqual(serializer.data, expected)

    def test_invalid_data_user_create(self):
        """Verify that users are not created if the serializer data is invalid."""
        username = 'test-user'
        data = {
            'viewers': [username],
            'id': None,
            'name': '',
            'query': '',
        }
        serializer = CatalogSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(User.objects.filter(username=username).count(), 0)


class MinimalCourseSerializerTests(SiteMixin, TestCase):
    serializer_class = MinimalCourseSerializer

    @classmethod
    def get_expected_data(cls, course, request):
        context = {'request': request}

        return {
            'key': course.key,
            'uuid': str(course.uuid),
            'title': course.title,
            'course_runs': MinimalCourseRunSerializer(course.course_runs, many=True, context=context).data,
            'entitlements': [],
            'owners': MinimalOrganizationSerializer(course.authoring_organizations, many=True, context=context).data,
            'image': ImageField().to_representation(course.image_url),
            'short_description': course.short_description,
            'type': course.type.uuid,
            'url_slug': None,
        }

    def test_data(self):
        request = make_request()
        organizations = OrganizationFactory(partner=self.partner)
        course = CourseFactory(authoring_organizations=[organizations], partner=self.partner)
        CourseRunFactory.create_batch(2, course=course)
        serializer = self.serializer_class(course, context={'request': request})
        expected = self.get_expected_data(course, request)
        self.assertDictEqual(serializer.data, expected)


class CourseSerializerTests(MinimalCourseSerializerTests):
    serializer_class = CourseSerializer

    @classmethod
    def get_expected_data(cls, course, request):
        expected = super().get_expected_data(course, request)

        expected.update({
            'short_description': course.short_description,
            'full_description': course.full_description,
            'level_type': course.level_type.name_t,
            'extra_description': AdditionalPromoAreaSerializer(course.extra_description).data,
            'subjects': [],
            'prerequisites': [],
            'expected_learning_items': [],
            'video': VideoSerializer(course.video).data,
            'sponsors': OrganizationSerializer(course.sponsoring_organizations, many=True).data,
            'modified': json_date_format(course.modified),
            'marketing_url': '{url}?{params}'.format(
                url=course.marketing_url,
                params=urlencode({
                    'utm_source': request.user.username,
                    'utm_medium': request.user.referral_tracking_id,
                })
            ),
            'course_runs': CourseRunSerializer(course.course_runs, many=True, context={'request': request}).data,
            'entitlements': CourseEntitlementSerializer(many=True).data,
            'owners': OrganizationSerializer(course.authoring_organizations, many=True).data,
            'prerequisites_raw': course.prerequisites_raw,
            'syllabus_raw': course.syllabus_raw,
            'outcome': course.outcome,
            'original_image': ImageField().to_representation(course.original_image_url),
            'card_image_url': course.card_image_url,
            'canonical_course_run_key': None,
            'additional_information': course.additional_information,
            'faq': course.faq,
            'learner_testimonials': course.learner_testimonials,
            'enrollment_count': 0,
            'recent_enrollment_count': 0,
            'topics': list(course.topics.names()),
            'key_for_reruns': course.key_for_reruns,
            'url_slug': course.active_url_slug,
            'url_slug_history': [course.active_url_slug],
            'url_redirects': [],
            'course_run_statuses': course.course_run_statuses,
            'editors': CourseEditorSerializer(course.editors, many=True, read_only=True).data,
            'collaborators': [],
        })

        return expected

    def test_exclude_utm(self):
        request = make_request()
        course = CourseFactory()
        course_runs = CourseRunFactory.create_batch(3, course=course)
        course.canonical_course_run = course_runs[0]
        serializer = self.serializer_class(course, context={'request': request, 'exclude_utm': 1})

        self.assertEqual(serializer.data['marketing_url'], course.marketing_url)

    def test_canonical_course_run_key(self):
        request = make_request()
        course = CourseFactory()
        course_runs = CourseRunFactory.create_batch(3, course=course)
        course.course_runs.set(course_runs)
        course.canonical_course_run = course_runs[0]
        serializer = self.serializer_class(course, context={'request': request, 'exclude_utm': 1})

        self.assertEqual(serializer.data['canonical_course_run_key'], course_runs[0].key)

    def test_draft_no_marketing_url(self):
        request = make_request()
        course_draft = CourseFactory(draft=True)
        draft_course_run = CourseRunFactory(draft=True, course=course_draft)
        course_draft.canonical_course_run = draft_course_run
        course_draft.save()
        serializer = self.serializer_class(course_draft, context={'request': request, 'exclude_utm': 1, 'editable': 1})

        self.assertIsNone(serializer.data['marketing_url'])

    def test_draft_and_official(self):
        request = make_request()
        course_draft = CourseFactory(draft=True)
        draft_course_run = CourseRunFactory(draft=True, course=course_draft)
        course_draft.canonical_course_run = draft_course_run
        course_draft.save()

        course = CourseFactory(draft=False, draft_version_id=course_draft.id)
        course_run = CourseRunFactory(draft=False, course=course, draft_version_id=draft_course_run.id)
        course.canonical_course_run = course_run
        course.save()

        serializer = self.serializer_class(course, context={'request': request, 'exclude_utm': 1, 'editable': 1})
        self.assertIsNotNone(serializer.data['marketing_url'])
        self.assertEqual(serializer.data['marketing_url'], course.marketing_url)


class CourseEditorSerializerTests(TestCase):

    def test_data(self):
        course_editor = CourseEditorFactory()
        serializer = CourseEditorSerializer(course_editor)

        expected = {
            'id': course_editor.id,
            'course': course_editor.course.uuid,
            'user': {
                'id': course_editor.user.id,
                'full_name': course_editor.user.full_name,
                'email': course_editor.user.email
            }
        }

        self.assertEqual(expected, serializer.data)


@ddt.ddt
class CourseWithProgramsSerializerTests(CourseSerializerTests):
    serializer_class = CourseWithProgramsSerializer
    YESTERDAY = datetime.datetime.now(UTC) - datetime.timedelta(days=1)
    TOMORROW = datetime.datetime.now(UTC) + datetime.timedelta(days=1)
    TWO_WEEKS_FROM_TODAY = datetime.datetime.now(UTC) + datetime.timedelta(days=14)

    @classmethod
    def get_expected_data(cls, course, request):
        expected = super().get_expected_data(course, request)
        expected.update({
            'programs': NestedProgramSerializer(
                course.programs,
                many=True,
                context={'request': request}
            ).data,
            'course_run_keys': [course_run.key for course_run in course.course_runs.all()],
            'editable': False,
            'advertised_course_run_uuid': None,
        })

        return expected

    def create_upgradeable_seat_for_course_run(self, course_run):
        return SeatFactory(
            course_run=course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.TOMORROW
        )

    def create_not_upgradeable_seat_for_course_run(self, course_run):
        return SeatFactory(
            course_run=course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=datetime.datetime(2014, 1, 1, tzinfo=UTC)
        )

    def setUp(self):
        super().setUp()
        self.request = make_request()
        self.course = CourseFactory(partner=self.partner)
        self.deleted_program = ProgramFactory(
            courses=[self.course],
            partner=self.partner,
            status=ProgramStatus.Deleted
        )

    def test_data(self):
        expected = self.get_expected_data(self.course, self.request)
        serializer = self.serializer_class(self.course, context={'request': self.request})
        self.assertDictEqual(serializer.data, expected)

    def test_advertised_course_run_is_upgradeable_and_end_not_within_two_weeks(self):
        start_days = [
            self.YESTERDAY,
            datetime.datetime.now(UTC) - datetime.timedelta(days=2),
            self.TOMORROW,
            datetime.datetime.now(UTC) - datetime.timedelta(days=30),
        ]

        end_days = [
            datetime.datetime.now(UTC) + datetime.timedelta(days=13),
            self.TWO_WEEKS_FROM_TODAY,
            datetime.datetime.now(UTC) - datetime.timedelta(days=30),
            self.YESTERDAY,
        ]

        expected_advertised_course_run = CourseRunFactory(
            course=self.course,
            start=self.YESTERDAY,
            end=self.TWO_WEEKS_FROM_TODAY,
            status=CourseRunStatus.Published,
            enrollment_end=self.TWO_WEEKS_FROM_TODAY,
        )

        self.create_upgradeable_seat_for_course_run(expected_advertised_course_run)

        not_upgradeable_course_run = CourseRunFactory(
            course=self.course,
            start=self.YESTERDAY,
            end=self.TWO_WEEKS_FROM_TODAY,
            status=CourseRunStatus.Published,
            enrollment_end=self.TWO_WEEKS_FROM_TODAY,
        )

        self.create_not_upgradeable_seat_for_course_run(not_upgradeable_course_run)

        not_marketable_course_run = CourseRunFactory(
            course=self.course,
            start=self.YESTERDAY,
            end=self.TWO_WEEKS_FROM_TODAY,
            status=CourseRunStatus.Unpublished,
            enrollment_end=self.TWO_WEEKS_FROM_TODAY,
        )

        self.create_upgradeable_seat_for_course_run(not_marketable_course_run)

        for i in range(4):
            cr = CourseRunFactory(
                course=self.course,
                start=start_days[i],
                end=end_days[i],
                status=CourseRunStatus.Published,
                enrollment_end=end_days[i],
            )
            self.create_upgradeable_seat_for_course_run(cr)

        serializer = self.serializer_class(self.course, context={'request': self.request})
        self.assertEqual(serializer.data['advertised_course_run_uuid'], expected_advertised_course_run.uuid)

    def test_advertised_course_run_is_upgradeable_and_starts_in_the_future(self):
        start_days = [
            self.YESTERDAY,
            datetime.datetime.now(UTC) + datetime.timedelta(days=2),
            datetime.datetime.now(UTC) - datetime.timedelta(days=30),
        ]

        end_days = [
            datetime.datetime.now(UTC) + datetime.timedelta(days=13),
            self.TWO_WEEKS_FROM_TODAY,
            datetime.datetime.now(UTC) - datetime.timedelta(days=1),
        ]

        expected_advertised_course_run = CourseRunFactory(
            course=self.course,
            start=self.TOMORROW,
            status=CourseRunStatus.Published,
            enrollment_end=None,
            end=None
        )

        self.create_upgradeable_seat_for_course_run(expected_advertised_course_run)

        not_upgradeable_course_run = CourseRunFactory(
            course=self.course,
            start=self.TOMORROW,
            end=datetime.datetime.now(UTC) + datetime.timedelta(days=30),
            status=CourseRunStatus.Published,
            enrollment_end=datetime.datetime.now(UTC) + datetime.timedelta(days=30),
        )

        self.create_not_upgradeable_seat_for_course_run(not_upgradeable_course_run)

        not_marketable_course_run = CourseRunFactory(
            course=self.course,
            start=self.YESTERDAY,
            end=self.TWO_WEEKS_FROM_TODAY,
            status=CourseRunStatus.Unpublished,
            enrollment_end=self.TWO_WEEKS_FROM_TODAY,
        )

        self.create_upgradeable_seat_for_course_run(not_marketable_course_run)

        for i in range(3):
            cr = CourseRunFactory(
                course=self.course,
                start=start_days[i],
                end=end_days[i],
                status=CourseRunStatus.Published,
                enrollment_end=end_days[i]
            )
            self.create_upgradeable_seat_for_course_run(cr)

        serializer = self.serializer_class(self.course, context={'request': self.request})
        self.assertEqual(serializer.data['advertised_course_run_uuid'], expected_advertised_course_run.uuid)

    def test_advertise_course_run_else_condition(self):
        start_days = [
            self.YESTERDAY,
            self.TOMORROW,
            datetime.datetime.now(UTC) - datetime.timedelta(days=30),
        ]

        end_days = [
            datetime.datetime.now(UTC) + datetime.timedelta(days=13),
            self.TWO_WEEKS_FROM_TODAY,
            datetime.datetime.now(UTC) - datetime.timedelta(days=1),
        ]

        expected_advertised_course_run = CourseRunFactory(
            course=self.course,
            start=datetime.datetime.now(UTC) + datetime.timedelta(days=2),
            end=datetime.datetime.now(UTC) + datetime.timedelta(days=30),
            status=CourseRunStatus.Published
        )

        self.create_not_upgradeable_seat_for_course_run(expected_advertised_course_run)

        not_marketable_course_run = CourseRunFactory(
            course=self.course,
            start=self.YESTERDAY,
            end=self.TWO_WEEKS_FROM_TODAY,
            status=CourseRunStatus.Unpublished
        )

        self.create_upgradeable_seat_for_course_run(not_marketable_course_run)

        for i in range(3):
            cr = CourseRunFactory(
                course=self.course,
                start=start_days[i],
                end=end_days[i],
                status=CourseRunStatus.Published
            )
            if not i == 0:
                self.create_not_upgradeable_seat_for_course_run(cr)

        serializer = self.serializer_class(self.course, context={'request': self.request})
        self.assertEqual(serializer.data['advertised_course_run_uuid'], expected_advertised_course_run.uuid)

    def test_advertised_course_run_no_start_date(self):
        expected_advertised_course_run = CourseRunFactory(
            course=self.course,
            start=datetime.datetime.now(UTC) + datetime.timedelta(days=2),
            end=datetime.datetime.now(UTC) + datetime.timedelta(days=30),
            status=CourseRunStatus.Published
        )
        self.create_not_upgradeable_seat_for_course_run(expected_advertised_course_run)

        other_run_no_start = CourseRunFactory(
            course=self.course,
            start=None,
            end=datetime.datetime.now(UTC) + datetime.timedelta(days=30),
            status=CourseRunStatus.Published
        )
        self.create_not_upgradeable_seat_for_course_run(other_run_no_start)
        serializer = self.serializer_class(self.course, context={'request': self.request})
        self.assertEqual(serializer.data['advertised_course_run_uuid'], expected_advertised_course_run.uuid)


class CurriculumSerializerTests(TestCase):
    serializer_class = CurriculumSerializer

    @classmethod
    def get_expected_data(cls, curriculum, request):

        curriculum_programs = [m.program for m in list(curriculum.curriculumprogrammembership_set.all())]
        curriculum_courses = [m.course for m in list(curriculum.curriculumcoursemembership_set.all())]
        curriculum_course_runs = [
            course_run for course in curriculum_courses
            for course_run in list(course.course_runs.all())
        ]

        return {
            'uuid': str(curriculum.uuid),
            'name': curriculum.name,
            'marketing_text': curriculum.marketing_text,
            'marketing_text_brief': curriculum.marketing_text_brief,
            'is_active': curriculum.is_active,
            'courses': MinimalProgramCourseSerializer(
                curriculum_courses,
                many=True,
                context={
                    'request': request,
                    'course_runs': curriculum_course_runs
                }
            ).data,
            'programs': MinimalProgramSerializer(
                curriculum_programs,
                many=True,
                context={
                    'request': request
                }
            ).data
        }

    def test_data(self):
        request = make_request()

        person = PersonFactory()
        parent_program = ProgramFactory()
        child_program = ProgramFactory()

        curriculum = CurriculumFactory(program=parent_program)
        course = CourseFactory()
        CourseRunFactory(course=course, staff=[person])
        CurriculumCourseMembershipFactory(
            course=course,
            curriculum=curriculum
        )
        CurriculumProgramMembershipFactory(
            program=child_program,
            curriculum=curriculum
        )
        expected = self.get_expected_data(curriculum, request)

        serializer = CurriculumSerializer(curriculum, context={'request': request})
        self.assertDictEqual(serializer.data, expected)


class MinimalCourseRunBaseTestSerializer(TestCase):
    serializer_class = MinimalCourseRunSerializer

    @classmethod
    def get_expected_data(cls, course_run, request):
        return {
            'key': course_run.key,
            'uuid': str(course_run.uuid),
            'title': course_run.title,
            'short_description': course_run.short_description,
            'image': ImageField().to_representation(course_run.image_url),
            'marketing_url': '{url}?{params}'.format(
                url=course_run.marketing_url,
                params=urlencode({
                    'utm_source': request.user.username,
                    'utm_medium': request.user.referral_tracking_id,
                })
            ),
            'start': json_date_format(course_run.start),
            'end': json_date_format(course_run.end),
            'go_live_date': json_date_format(course_run.go_live_date),
            'enrollment_start': json_date_format(course_run.enrollment_start),
            'enrollment_end': json_date_format(course_run.enrollment_end),
            'pacing_type': course_run.pacing_type,
            'type': course_run.type_legacy,
            'run_type': course_run.type.uuid,
            'seats': SeatSerializer(course_run.seats, many=True).data,
            'status': course_run.status,
            'external_key': course_run.external_key,
            'is_enrollable': course_run.is_enrollable,
            'is_marketable': course_run.is_marketable,
        }


class MinimalCourseRunSerializerTests(MinimalCourseRunBaseTestSerializer):

    def test_data(self):
        request = make_request()
        course_run = CourseRunFactory()
        serializer = self.serializer_class(course_run, context={'request': request})
        expected = self.get_expected_data(course_run, request)
        assert serializer.data == expected

    def test_get_lms_course_url(self):
        partner = PartnerFactory()
        course_key = 'course-v1:testX+test1.23+2018T1'
        lms_course_url = get_lms_course_url_for_archived(partner, '')
        self.assertIsNone(lms_course_url)

        partner.lms_url = 'http://127.0.0.1:8000'
        lms_course_url = get_lms_course_url_for_archived(partner, course_key)
        expected_url = f'{partner.lms_url}/courses/{course_key}/course/'
        self.assertEqual(lms_course_url, expected_url)


class CourseRunSerializerTests(MinimalCourseRunBaseTestSerializer):
    serializer_class = CourseRunSerializer

    @classmethod
    def get_expected_data(cls, course_run, request):
        expected = super().get_expected_data(course_run, request)
        expected.update({
            'course': course_run.course.key,
            'key': course_run.key,
            'title': course_run.title,
            'full_description': course_run.full_description,
            'announcement': json_date_format(course_run.announcement),
            'video': VideoSerializer(course_run.video).data,
            'mobile_available': course_run.mobile_available,
            'eligible_for_financial_aid': course_run.eligible_for_financial_aid,
            'hidden': course_run.hidden,
            'content_language': course_run.language.code,
            'transcript_languages': [],
            'min_effort': course_run.min_effort,
            'max_effort': course_run.max_effort,
            'weeks_to_complete': course_run.weeks_to_complete,
            'instructors': [],
            'staff': [],
            'seats': [],
            'modified': json_date_format(course_run.modified),
            'level_type': course_run.level_type.name_t,
            'availability': course_run.availability,
            'reporting_type': course_run.reporting_type,
            'status': course_run.status,
            'license': course_run.license,
            'outcome': course_run.outcome,
            'has_ofac_restrictions': course_run.has_ofac_restrictions,
            'enrollment_count': 0,
            'recent_enrollment_count': 0,
            'course_uuid': course_run.course.uuid,
            'expected_program_name': course_run.expected_program_name,
            'expected_program_type': course_run.expected_program_type,
            'first_enrollable_paid_seat_price': course_run.first_enrollable_paid_seat_price,
            'ofac_comment': course_run.ofac_comment,
            'estimated_hours': get_course_run_estimated_hours(course_run)
        })
        return expected

    def test_data(self):
        request = make_request()
        course_run = CourseRunFactory()
        serializer = self.serializer_class(course_run, context={'request': request})
        expected = self.get_expected_data(course_run, request)

        assert serializer.data == expected

    def test_exclude_utm(self):
        request = make_request()
        course_run = CourseRunFactory()
        serializer = self.serializer_class(course_run, context={'request': request, 'exclude_utm': 1})

        self.assertEqual(serializer.data['marketing_url'], course_run.marketing_url)

    def test_draft_no_marketing_url(self):
        request = make_request()
        draft_course_run = CourseRunFactory(draft=True)
        serializer = self.serializer_class(draft_course_run, context={'request': request, 'editable': 1})

        self.assertIsNone(serializer.data['marketing_url'])

    def test_draft_and_official(self):
        request = make_request()
        draft_course_run = CourseRunFactory(draft=True)
        course_run = CourseRunFactory(draft=False, draft_version_id=draft_course_run.id)

        serializer = self.serializer_class(course_run, context={'request': request, 'exclude_utm': 1, 'editable': 1})
        self.assertIsNotNone(serializer.data['marketing_url'])
        self.assertEqual(serializer.data['marketing_url'], course_run.marketing_url)


class CourseRunWithProgramsSerializerTests(TestCase):
    def setUp(self):
        super().setUp()
        self.request = make_request()
        self.course_run = CourseRunFactory()
        self.serializer_context = {'request': self.request}

    def test_data(self):
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        ProgramFactory(courses=[self.course_run.course])
        self.assertDictEqual(serializer.data, self.get_expected_data(self.course_run, self.request))

    def test_data_excluded_course_run(self):
        """
        If a course run is excluded on a program, that program should not be
        returned for that course run on the course run endpoint.
        """
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        ProgramFactory(courses=[self.course_run.course], excluded_course_runs=[self.course_run])
        expected = CourseRunSerializer(self.course_run, context=self.serializer_context).data
        expected.update({'programs': []})
        assert serializer.data == expected

    def test_exclude_unpublished_program(self):
        """
        If a program is unpublished, that program should not be returned on the course run endpoint by default.
        """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Unpublished)
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        self.assertEqual(serializer.data['programs'], [])

    def test_include_unpublished_programs(self):
        """
        If a program is unpublished, that program should only be returned on the course run endpoint if we are
        sending the 'include_unpublished_programs' flag.
        """
        unpublished_program = ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Unpublished)
        self.serializer_context['include_unpublished_programs'] = 1
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        self.assertEqual(
            serializer.data['programs'],
            NestedProgramSerializer([unpublished_program], many=True, context=self.serializer_context).data
        )

    def test_exclude_retired_program(self):
        """
        If a program is retired, that program should not be returned on the course run endpoint by default.
        """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Retired)
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        self.assertEqual(serializer.data['programs'], [])

    def test_include_retired_programs(self):
        """
        If a program is retired, that program should only be returned on the course run endpoint if we are
        sending the 'include_retired_programs' flag.
        """
        retired_program = ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Retired)
        self.serializer_context['include_retired_programs'] = 1
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        self.assertEqual(
            serializer.data['programs'],
            NestedProgramSerializer([retired_program], many=True, context=self.serializer_context).data
        )

    @classmethod
    def get_expected_data(cls, course_run, request):
        expected = CourseRunSerializer(course_run, context={'request': request}).data
        expected.update({
            'programs': NestedProgramSerializer(
                course_run.course.programs,
                many=True,
                context={'request': request},
            ).data,
        })
        return expected


class FlattenedCourseRunWithCourseSerializerTests(TestCase):  # pragma: no cover
    @classmethod
    def serialize_seats(cls, course_run):
        seats = {
            'audit': {
                'type': ''
            },
            'honor': {
                'type': ''
            },
            'verified': {
                'type': '',
                'currency': '',
                'price': '',
                'upgrade_deadline': '',
            },
            'professional': {
                'type': '',
                'currency': '',
                'price': '',
                'upgrade_deadline': '',
            },
            'credit': {
                'type': [],
                'currency': [],
                'price': [],
                'upgrade_deadline': [],
                'credit_provider': [],
                'credit_hours': [],
            },
            'masters': {
                'type': ''
            },
        }

        for seat in course_run.seats.all():
            for key in seats[seat.type.slug].keys():
                if seat.type.slug == 'credit':
                    seats['credit'][key].append(SeatSerializer(seat).data[key])
                else:
                    seats[seat.type.slug][key] = SeatSerializer(seat).data[key]

        for credit_attr in seats['credit']:
            seats['credit'][credit_attr] = ','.join([str(e) for e in seats['credit'][credit_attr]])

        return seats

    @classmethod
    def serialize_items(cls, organizations, attr):
        return ','.join([getattr(organization, attr) for organization in organizations])

    @classmethod
    def get_expected_data(cls, request, course_run):
        course = course_run.course
        serializer_context = {'request': request}
        expected = dict(CourseRunSerializer(course_run, context=serializer_context).data)
        expected.update({
            'subjects': cls.serialize_items(course.subjects.all(), 'name'),
            'seats': cls.serialize_seats(course_run),
            'owners': cls.serialize_items(course.authoring_organizations.all(), 'key'),
            'sponsors': cls.serialize_items(course.sponsoring_organizations.all(), 'key'),
            'prerequisites': cls.serialize_items(course.prerequisites.all(), 'name'),
            'level_type': course_run.level_type.name_t if course_run.level_type else None,
            'expected_learning_items': cls.serialize_items(course.expected_learning_items.all(), 'value'),
            'course_key': course.key,
            'image': ImageField().to_representation(course_run.card_image_url),
            'term': 'example-term',
        })

        # Remove fields found in CourseRunSerializer, but not in FlattenedCourseRunWithCourseSerializer.
        fields_to_remove = set(CourseRunSerializer.Meta.fields) - set(
            FlattenedCourseRunWithCourseSerializer.Meta.fields)
        for key in fields_to_remove:
            del expected[key]

        return expected

    def test_data(self):
        request = make_request()
        course_run = CourseRunFactory()
        SeatFactory(course_run=course_run, type=SeatTypeFactory.audit())
        serializer_context = {'request': request}
        serializer = FlattenedCourseRunWithCourseSerializer(course_run, context=serializer_context)
        expected = self.get_expected_data(request, course_run)
        self.assertDictEqual(serializer.data, expected)

    def test_data_without_level_type(self):
        """ Verify the serializer handles courses with no level type set. """
        request = make_request()
        course_run = CourseRunFactory(course__level_type=None)
        SeatFactory(course_run=course_run, type=SeatTypeFactory.audit())
        serializer_context = {'request': request}
        serializer = FlattenedCourseRunWithCourseSerializer(course_run, context=serializer_context)
        expected = self.get_expected_data(request, course_run)
        self.assertDictEqual(serializer.data, expected)


class MinimalProgramCourseSerializerTests(TestCase):
    def setUp(self):
        super().setUp()
        self.program = ProgramFactory(courses=[CourseFactory()])

    def assert_program_courses_serialized(self, program):
        request = make_request()

        serializer = MinimalProgramCourseSerializer(
            program.courses,
            many=True,
            context={
                'request': request,
                'program': program,
                'course_runs': list(program.course_runs)
            }
        )
        expected = MinimalCourseSerializer(program.courses, many=True, context={'request': request}).data
        self.assertSequenceEqual(serializer.data, expected)

    def test_data(self):
        for course in self.program.courses.all():
            CourseRunFactory(course=course)

        self.assert_program_courses_serialized(self.program)

    def test_data_without_course_runs(self):
        """
        Make sure that if a course has no runs, the serializer still works as expected
        """
        self.assert_program_courses_serialized(self.program)

    def test_with_exclusions(self):
        """
        Test serializer with course_run exclusions within program
        """
        request = make_request()
        course = CourseFactory()
        excluded_runs = []
        course_runs = CourseRunFactory.create_batch(2, course=course)
        excluded_runs.append(course_runs[0])
        program = ProgramFactory(courses=[course], excluded_course_runs=excluded_runs)

        serializer_context = {'request': request, 'program': program, 'course_runs': list(program.course_runs)}
        serializer = MinimalProgramCourseSerializer(course, context=serializer_context)

        expected = MinimalCourseSerializer(course, context=serializer_context).data
        expected['course_runs'] = MinimalCourseRunSerializer(
            [course_runs[1]], many=True, context={'request': request}).data
        self.assertDictEqual(serializer.data, expected)

    def test_with_published_course_runs_only_context(self):
        """ Verify setting the published_course_runs_only context value excludes unpublished course runs. """
        # Create a program and course. The course should have both published and un-published course runs.
        request = make_request()
        course = CourseFactory()
        program = ProgramFactory(courses=[course])
        unpublished_course_run = CourseRunFactory(status=CourseRunStatus.Unpublished, course=course)
        CourseRunFactory(status=CourseRunStatus.Published, course=course)

        # We do NOT expect the results to included the unpublished data
        expected = MinimalCourseSerializer(course, context={'request': request}).data
        expected['course_runs'] = [course_run for course_run in expected['course_runs'] if
                                   course_run['key'] != str(unpublished_course_run.key)]
        self.assertEqual(len(expected['course_runs']), 1)

        serializer = MinimalProgramCourseSerializer(
            course,
            context={
                'request': request,
                'program': program,
                'published_course_runs_only': True,
                'course_runs': list(program.course_runs),
            }
        )

        self.assertSequenceEqual(serializer.data, expected)

    def test_use_full_course_serializer(self):
        """
        Verify that we can use the `use_full_course_serializer` parameter to use the
        CourseRun serializer.
        """
        request = make_request()
        course = CourseFactory()
        program = ProgramFactory(courses=[course])
        CourseRunFactory(course=course)

        serializer_data = MinimalProgramCourseSerializer(
            course,
            context={
                'request': request,
                'program': program,
                'use_full_course_serializer': 1,
                'course_runs': list(program.course_runs),
            }
        ).data

        expected = CourseRunSerializer(
            course.course_runs.all(),
            many=True,
            context={
                'request': request,
                'use_full_course_serializer': 1
            }
        ).data

        assert serializer_data['course_runs'] == expected


class MinimalProgramSerializerTests(TestCase):
    serializer_class = MinimalProgramSerializer

    def create_program(self):
        organizations = OrganizationFactory.create_batch(2)
        person = PersonFactory()

        topic = Tag.objects.create(name="topic")
        courses = CourseFactory.create_batch(3)
        for course in courses:
            CourseRunFactory.create_batch(2, course=course, staff=[person], start=datetime.datetime.now(UTC))
            course.topics.set(topic)

        return ProgramFactory(
            courses=courses,
            authoring_organizations=organizations,
            credit_backing_organizations=organizations,
            corporate_endorsements=CorporateEndorsementFactory.create_batch(1),
            individual_endorsements=EndorsementFactory.create_batch(1),
            expected_learning_items=ExpectedLearningItemFactory.create_batch(1),
            job_outlook_items=JobOutlookItemFactory.create_batch(1),
            banner_image=make_image_file('test_banner.jpg'),
            video=VideoFactory(),
            order_courses_by_start_date=False,
        )

    @classmethod
    def get_expected_data(cls, program, request):
        image_field = StdImageSerializerField()
        image_field._context = {'request': request}  # pylint: disable=protected-access

        return {
            'uuid': str(program.uuid),
            'title': program.title,
            'subtitle': program.subtitle,
            'type': program.type.name_t,
            'type_attrs': ProgramTypeAttrsSerializer(program.type).data,
            'status': program.status,
            'marketing_slug': program.marketing_slug,
            'marketing_url': program.marketing_url,
            'banner_image': image_field.to_representation(program.banner_image),
            'hidden': program.hidden,
            'courses': MinimalProgramCourseSerializer(
                program.courses,
                many=True,
                context={
                    'request': request,
                    'program': program,
                    'course_runs': list(program.course_runs),
                }).data,
            'authoring_organizations': MinimalOrganizationSerializer(program.authoring_organizations, many=True).data,
            'card_image_url': program.card_image_url,
            'is_program_eligible_for_one_click_purchase': program.is_program_eligible_for_one_click_purchase,
            'degree': None,
            'curricula': [],
            'marketing_hook': program.marketing_hook,
        }

    def test_data(self):
        request = make_request()
        program = self.create_program()
        serializer = self.serializer_class(program, context={'request': request})
        expected = self.get_expected_data(program, request)
        self.assertDictEqual(serializer.data, expected)


class ProgramSerializerTests(MinimalProgramSerializerTests):
    serializer_class = ProgramSerializer

    @classmethod
    def get_expected_data(cls, program, request):
        expected = super().get_expected_data(program, request)
        expected.update({
            'authoring_organizations': OrganizationSerializer(program.authoring_organizations, many=True).data,
            'video': VideoSerializer(program.video).data,
            'credit_redemption_overview': program.credit_redemption_overview,
            'applicable_seat_types': list(program.type.applicable_seat_types.values_list('slug', flat=True)),
            'corporate_endorsements': CorporateEndorsementSerializer(program.corporate_endorsements, many=True).data,
            'credit_backing_organizations': OrganizationSerializer(
                program.credit_backing_organizations,
                many=True
            ).data,
            'expected_learning_items': [item.value for item in program.expected_learning_items.all()],
            'faq': FAQSerializer(program.faq, many=True).data,
            'individual_endorsements': EndorsementSerializer(
                program.individual_endorsements, many=True, context={'request': request}
            ).data,
            'staff': MinimalPersonSerializer(program.staff, many=True, context={'request': request}).data,
            'instructor_ordering': MinimalPersonSerializer(
                program.instructor_ordering,
                many=True,
                context={'request': request}
            ).data,
            'job_outlook_items': [item.value for item in program.job_outlook_items.all()],
            'languages': [serialize_language_to_code(p_lang) for p_lang in program.languages],
            'weeks_to_complete': program.weeks_to_complete,
            'total_hours_of_effort': program.total_hours_of_effort,
            'weeks_to_complete_min': program.weeks_to_complete_min,
            'weeks_to_complete_max': program.weeks_to_complete_max,
            'max_hours_effort_per_week': program.max_hours_effort_per_week,
            'min_hours_effort_per_week': program.min_hours_effort_per_week,
            'overview': program.overview,
            'price_ranges': program.price_ranges,
            'subjects': SubjectSerializer(program.subjects, many=True).data,
            'transcript_languages': [serialize_language_to_code(p_t_l) for p_t_l in program.transcript_languages],
            'enrollment_count': 0,
            'recent_enrollment_count': 0,
            'topics': [topic.name for topic in program.topics],
            'credit_value': program.credit_value,
        })
        return expected

    def test_data_with_exclusions(self):
        """
        Verify we can specify program excluded_course_runs and the serializers will
        render the course_runs with exclusions
        """
        request = make_request()
        program = self.create_program()

        excluded_course_run = program.courses.all()[0].course_runs.all()[0]
        program.excluded_course_runs.add(excluded_course_run)

        expected = self.get_expected_data(program, request)
        serializer = self.serializer_class(program, context={'request': request})
        self.assertDictEqual(serializer.data, expected)

    def test_course_ordering(self):
        """
        Verify that courses in a program are ordered by ascending run start date,
        with ties broken by earliest run enrollment start date.
        """
        request = make_request()
        course_list = CourseFactory.create_batch(3)

        # Create a course run with arbitrary start and empty enrollment_start.
        CourseRunFactory(
            course=course_list[2],
            enrollment_start=None,
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a second run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime.datetime(2014, 1, 2, tzinfo=UTC),
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a third run with later start and enrollment_start.
        CourseRunFactory(
            course=course_list[0],
            enrollment_start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
            start=datetime.datetime(2014, 3, 1, tzinfo=UTC),
        )

        program = ProgramFactory(courses=course_list)
        serializer = self.serializer_class(program, context={'request': request})

        expected = MinimalProgramCourseSerializer(
            # The expected ordering is the reverse of course_list.
            course_list[::-1],
            many=True,
            context={'request': request, 'program': program, 'course_runs': list(program.course_runs)}
        ).data

        self.assertEqual(serializer.data['courses'], expected)

    def test_course_ordering_with_exclusions(self):
        """
        Verify that excluded course runs aren't used when ordering courses.
        """
        request = make_request()
        course_list = CourseFactory.create_batch(3)

        # Create a course run with arbitrary start and empty enrollment_start.
        # This run will be excluded from the program. If it wasn't excluded,
        # the expected course ordering, by index, would be: 0, 2, 1.
        excluded_run = CourseRunFactory(
            course=course_list[0],
            enrollment_start=None,
            start=datetime.datetime(2014, 1, 1, tzinfo=UTC),
        )

        # Create a run with later start and empty enrollment_start.
        CourseRunFactory(
            course=course_list[2],
            enrollment_start=None,
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime.datetime(2014, 1, 2, tzinfo=UTC),
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a run with later start and enrollment_start.
        CourseRunFactory(
            course=course_list[0],
            enrollment_start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
            start=datetime.datetime(2014, 3, 1, tzinfo=UTC),
        )

        program = ProgramFactory(courses=course_list, excluded_course_runs=[excluded_run])
        serializer = self.serializer_class(program, context={'request': request})

        expected = MinimalProgramCourseSerializer(
            # The expected ordering is the reverse of course_list.
            course_list[::-1],
            many=True,
            context={'request': request, 'program': program, 'course_runs': list(program.course_runs)}
        ).data

        self.assertEqual(serializer.data['courses'], expected)

    def test_course_ordering_with_no_start(self):
        """
        Verify that a courses run with missing start date appears last when ordering courses.
        """
        request = make_request()
        course_list = CourseFactory.create_batch(3)

        # Create a course run with arbitrary start and empty enrollment_start.
        CourseRunFactory(
            course=course_list[2],
            enrollment_start=None,
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a second run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime.datetime(2014, 1, 2, tzinfo=UTC),
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a third run with empty start and enrollment_start.
        CourseRunFactory(
            course=course_list[0],
            enrollment_start=None,
            start=None,
        )

        program = ProgramFactory(courses=course_list)
        serializer = self.serializer_class(program, context={'request': request})

        expected = MinimalProgramCourseSerializer(
            # The expected ordering is the reverse of course_list.
            course_list[::-1],
            many=True,
            context={'request': request, 'program': program, 'course_runs': list(program.course_runs)}
        ).data

        self.assertEqual(serializer.data['courses'], expected)

    def test_data_without_course_sorting(self):
        request = make_request()

        program = self.create_program()
        program.order_courses_by_start_date = False
        program.save()

        serializer = self.serializer_class(program, context={'request': request})
        expected = self.get_expected_data(program, request)
        self.assertDictEqual(serializer.data, expected)

    def test_marketable_enrollable_course_runs_with_archived(self):
        """ Test that the marketable_enrollable_course_runs_with_archived flag hides course runs
        that are not marketable or enrollable
        """
        course = CourseFactory()
        CourseRunFactory(status=CourseRunStatus.Unpublished, course=course)
        marketable_enrollable_run = CourseRunFactory(
            status=CourseRunStatus.Published,
            end=datetime.datetime.now(UTC) + datetime.timedelta(days=10),
            enrollment_start=None,
            enrollment_end=None,
            course=course
        )
        SeatFactory(course_run=marketable_enrollable_run)
        program = ProgramFactory(courses=[course])
        request = make_request()

        serializer = self.serializer_class(
            program,
            context={
                'request': request,
                'marketable_enrollable_course_runs_with_archived': True
            }
        )

        expected = MinimalProgramCourseSerializer(
            [course],
            many=True,
            context={
                'request': request,
                'program': program,
                'course_runs': [marketable_enrollable_run]
            }
        ).data

        assert len(expected[0]['course_runs']) == 1
        assert sorted(serializer.data['courses'][0]['course_runs'], key=lambda x: x['key']) == \
            sorted(expected[0]['course_runs'], key=lambda x: x['key'])

    def test_degree_marketing_data(self):
        request = make_request()

        lead_capture_image_field = StdImageSerializerField()
        lead_capture_image_field._context = {'request': request}  # pylint: disable=protected-access

        mm_background_image_field = StdImageSerializerField()
        mm_background_image_field._context = {'request': request}  # pylint: disable=protected-access

        rankings = RankingFactory.create_batch(3)
        degree = DegreeFactory.create(rankings=rankings)
        curriculum = CurriculumFactory.create(program=degree)
        degree.curricula.set([curriculum])
        quick_facts = IconTextPairingFactory.create_batch(3, degree=degree)
        degree.deadline = DegreeDeadlineFactory.create_batch(size=3, degree=degree)
        degree.cost = DegreeCostFactory.create_batch(size=3, degree=degree)

        serializer = self.serializer_class(degree, context={'request': request})
        expected = self.get_expected_data(degree, request)
        expected_rankings = RankingSerializer(rankings, many=True).data
        expected_curriculum = CurriculumSerializer(curriculum).data
        expected_quick_facts = IconTextPairingSerializer(quick_facts, many=True).data
        expected_degree_deadlines = DegreeDeadlineSerializer(degree.deadline, many=True).data
        expected_degree_costs = DegreeCostSerializer(degree.cost, many=True).data

        url = re.compile(r"https?:\/\/[^\/]*")
        expected_micromasters_path = url.sub('', degree.micromasters_url)

        # Tack in degree data
        expected['curricula'] = [expected_curriculum]
        expected['degree'] = {
            'application_requirements': degree.application_requirements,
            'apply_url': degree.apply_url,
            'overall_ranking': degree.overall_ranking,
            'banner_border_color': degree.banner_border_color,
            'campus_image': degree.campus_image,
            'costs': expected_degree_costs,
            'deadlines': expected_degree_deadlines,
            'quick_facts': expected_quick_facts,
            'prerequisite_coursework': degree.prerequisite_coursework,
            'rankings': expected_rankings,
            'lead_capture_list_name': degree.lead_capture_list_name,
            'lead_capture_image': lead_capture_image_field.to_representation(degree.lead_capture_image),
            'hubspot_lead_capture_form_id': degree.hubspot_lead_capture_form_id,
            'micromasters_path': expected_micromasters_path,
            'micromasters_url': degree.micromasters_url,
            'micromasters_long_title': degree.micromasters_long_title,
            'micromasters_long_description': degree.micromasters_long_description,
            'micromasters_background_image': mm_background_image_field.to_representation(
                degree.micromasters_background_image
            ),
            'micromasters_org_name_override': degree.micromasters_org_name_override,
            'costs_fine_print': degree.costs_fine_print,
            'deadlines_fine_print': degree.deadlines_fine_print,
            'title_background_image': degree.title_background_image,
        }
        self.assertDictEqual(serializer.data, expected)

    def test_data_with_card_image(self):
        program = self.create_program()
        request = make_request()
        card_image_file = make_image_file('test_card.jpg')
        program.card_image = card_image_file
        serializer = self.serializer_class(program, context={'request': request})
        expected = self.get_expected_data(program, request)
        expected.update({
            'card_image_url': '/media/test_card.jpg'
        })
        self.assertDictEqual(serializer.data, expected)


class PathwaySerialzerTests(TestCase):
    def test_data(self):
        pathway = PathwayFactory()
        serializer = PathwaySerializer(pathway)

        expected = {
            'id': pathway.id,
            'uuid': str(pathway.uuid),
            'name': pathway.name,
            'org_name': pathway.org_name,
            'email': pathway.email,
            'programs': MinimalProgramSerializer(pathway.programs, many=True).data,
            'description': pathway.description,
            'destination_url': pathway.destination_url,
            'pathway_type': pathway.pathway_type,
        }
        self.assertDictEqual(serializer.data, expected)


class ProgramTypeSerializerTests(TestCase):
    serializer_class = ProgramTypeSerializer

    @classmethod
    def get_expected_data(cls, program_type, request):
        image_field = StdImageSerializerField()
        image_field._context = {'request': request}  # pylint: disable=protected-access

        return {
            'uuid': str(program_type.uuid),
            'name': program_type.name_t,
            'logo_image': image_field.to_representation(program_type.logo_image),
            'applicable_seat_types': [seat_type.slug for seat_type in program_type.applicable_seat_types.all()],
            'slug': program_type.slug,
            'coaching_supported': program_type.coaching_supported
        }

    def test_data(self):
        request = make_request()
        applicable_seat_types = SeatTypeFactory.create_batch(3)
        program_type = ProgramTypeFactory(applicable_seat_types=applicable_seat_types)
        serializer = self.serializer_class(program_type, context={'request': request})
        expected = self.get_expected_data(program_type, request)
        self.assertDictEqual(serializer.data, expected)


class ContainedCourseRunsSerializerTests(TestCase):
    def test_data(self):
        instance = {
            'course_runs': {
                'course-v1:edX+DemoX+Demo_Course': True,
                'a/b/c': False
            }
        }
        serializer = ContainedCourseRunsSerializer(instance)
        self.assertDictEqual(serializer.data, instance)


class ContainedCoursesSerializerTests(TestCase):
    def test_data(self):
        instance = {
            'courses': {
                'course-v1:edX+DemoX+Demo_Course': True,
                'a/b/c': False
            }
        }
        serializer = ContainedCoursesSerializer(instance)
        self.assertDictEqual(serializer.data, instance)


@ddt.ddt
class ContentTypeSerializerTests(TestCase):
    @ddt.data(
        (CourseFactory, 'course'),
        (CourseRunFactory, 'courserun'),
        (ProgramFactory, 'program'),
    )
    @ddt.unpack
    def test_data(self, factory_class, expected_content_type):
        obj = factory_class()
        serializer = ContentTypeSerializer(obj)
        expected = {
            'content_type': expected_content_type
        }
        assert serializer.data == expected


@ddt.ddt
class NamedModelSerializerTests(TestCase):
    @ddt.data(
        (PrerequisiteFactory, PrerequisiteSerializer),
    )
    @ddt.unpack
    def test_data(self, factory_class, serializer_class):
        link_object = factory_class()
        serializer = serializer_class(link_object)

        expected = {
            'name': link_object.name
        }

        self.assertDictEqual(serializer.data, expected)


class SubjectSerializerTests(TestCase):
    def test_data(self):
        subject = SubjectFactory()
        serializer = SubjectSerializer(subject)

        expected = {
            'name': subject.name,
            'description': subject.description,
            'banner_image_url': subject.banner_image_url,
            'card_image_url': subject.card_image_url,
            'subtitle': subject.subtitle,
            'slug': subject.slug,
            'uuid': str(subject.uuid),
        }

        self.assertDictEqual(serializer.data, expected)


class TopicSerializerTests(TestCase):
    def test_data(self):
        topic = TopicFactory()
        serializer = TopicSerializer(topic)

        expected = {
            'name': topic.name,
            'description': topic.description,
            'long_description': topic.long_description,
            'banner_image_url': topic.banner_image_url,
            'subtitle': topic.subtitle,
            'slug': topic.slug,
            'uuid': str(topic.uuid),
        }

        self.assertDictEqual(serializer.data, expected)


class ImageSerializerTests(TestCase):
    def test_data(self):
        image = ImageFactory()
        serializer = ImageSerializer(image)

        expected = {
            'src': image.src,
            'description': image.description,
            'height': image.height,
            'width': image.width
        }

        self.assertDictEqual(serializer.data, expected)


class CorporateEndorsementSerializerTests(TestCase):
    def test_data(self):
        corporate_endorsement = CorporateEndorsementFactory()
        serializer = CorporateEndorsementSerializer(corporate_endorsement)

        expected = {
            'corporation_name': corporate_endorsement.corporation_name,
            'statement': corporate_endorsement.statement,
            'image': ImageSerializer(corporate_endorsement.image).data,
            'individual_endorsements': EndorsementSerializer(
                corporate_endorsement.individual_endorsements,
                many=True
            ).data
        }

        self.assertDictEqual(serializer.data, expected)


class NestedProgramSerializerTests(TestCase):
    def test_data(self):
        course_run = CourseRunFactory()
        program = ProgramFactory(courses=[course_run.course])
        serializer = NestedProgramSerializer(program)

        expected = {
            'uuid': str(program.uuid),
            'marketing_slug': program.marketing_slug,
            'marketing_url': program.marketing_url,
            'type': program.type.name,
            'type_attrs': ProgramTypeAttrsSerializer(program.type).data,
            'title': program.title,
            'number_of_courses': program.courses.count(),
        }

        self.assertDictEqual(serializer.data, expected)


class VideoSerializerTests(TestCase):
    def test_data(self):
        video = VideoFactory()
        image = video.image
        serializer = VideoSerializer(video)

        expected = {
            'src': video.src,
            'description': video.description,
            'image': ImageSerializer(image).data
        }

        self.assertDictEqual(serializer.data, expected)


class MinimalOrganizationSerializerTests(TestCase):
    serializer_class = MinimalOrganizationSerializer

    def create_organization(self):
        return OrganizationFactory()

    @classmethod
    def get_expected_data(cls, organization):
        return {
            'uuid': str(organization.uuid),
            'key': organization.key,
            'name': organization.name,
            'auto_generate_course_run_keys': organization.auto_generate_course_run_keys,
        }

    def test_data(self):
        organization = self.create_organization()
        serializer = self.serializer_class(organization)
        expected = self.get_expected_data(organization)
        self.assertDictEqual(serializer.data, expected)


class OrganizationSerializerTests(MinimalOrganizationSerializerTests):
    TAG = 'test-tag'
    serializer_class = OrganizationSerializer

    def create_organization(self):
        organization = super().create_organization()
        organization.tags.add(self.TAG)
        return organization

    @classmethod
    def get_expected_data(cls, organization):
        expected = super().get_expected_data(organization)
        expected.update({
            'certificate_logo_image_url': organization.certificate_logo_image.url,
            'description': organization.description,
            'homepage_url': organization.homepage_url,
            'logo_image_url': organization.logo_image.url,
            'tags': [cls.TAG],
            'marketing_url': organization.marketing_url,
            'slug': organization.slug,
            'banner_image_url': organization.banner_image.url,
        })

        return expected


@ddt.ddt
class CourseEntitlementSerializerTests(TestCase):
    def setUp(self):
        super().setUp()
        self.entitlement = CourseEntitlementFactory()

    def test_data(self):
        serializer = CourseEntitlementSerializer(self.entitlement)

        expected = {
            'price': str(self.entitlement.price),
            'currency': self.entitlement.currency.code,
            'sku': self.entitlement.sku,
            'mode': str(self.entitlement.mode).lower(),
            'expires': None,
        }

        self.assertDictEqual(serializer.data, expected)

    @ddt.data('0.000', '100000000.00', '-1')
    def test_price_validation_errors(self, price):
        """Test Cases: More than two decimals, More than 8 digits, Less than 0"""
        self.entitlement.price = price
        serializer = CourseEntitlementSerializer(data=self.entitlement.__dict__)
        serializer.is_valid()

        self.assertTrue(serializer.errors['price'])


@ddt.ddt
class SeatSerializerTests(TestCase):
    def setUp(self):
        super().setUp()
        course_run = CourseRunFactory()
        self.seat = SeatFactory(course_run=course_run)

    def test_data(self):
        serializer = SeatSerializer(self.seat)

        expected = {
            'type': self.seat.type.slug,
            'price': str(self.seat.price),
            'currency': self.seat.currency.code,
            'upgrade_deadline': json_date_format(self.seat.upgrade_deadline),
            'credit_provider': self.seat.credit_provider,
            'credit_hours': self.seat.credit_hours,
            'sku': self.seat.sku,
            'bulk_sku': self.seat.bulk_sku
        }

        self.assertDictEqual(serializer.data, expected)

    @ddt.data('0.000', '100000000.00', '-1')
    def test_price_validation_errors(self, price):
        """Test Cases: More than two decimals, More than 8 digits, Less than 0"""
        self.seat.price = price
        serializer = SeatSerializer(data=self.seat.__dict__)
        serializer.is_valid()

        self.assertTrue(serializer.errors['price'])


class MinimalPersonSerializerTests(TestCase):
    def setUp(self):
        super().setUp()
        request = make_request()
        self.context = {'request': request}
        image_field = StdImageSerializerField()
        image_field._context = self.context  # pylint: disable=protected-access

        self.serializer = MinimalPersonSerializer
        position = PositionFactory()
        self.person = position.person
        self.person.salutation = 'Dr.'
        self.expected = {
            'uuid': str(self.person.uuid),
            'salutation': self.person.salutation,
            'given_name': self.person.given_name,
            'family_name': self.person.family_name,
            'bio': self.person.bio,
            'profile_image': image_field.to_representation(self.person.profile_image),
            'profile_image_url': self.person.get_profile_image_url,
            'position': PositionSerializer(position).data,
            'works': [],
            'major_works': self.person.major_works,
            'urls': {
                'facebook': None,
                'twitter': None,
                'blog': None,
            },
            'urls_detailed': [],
            'areas_of_expertise': [],
            'slug': self.person.slug,
            'email': None,  # always None
            'published': True,
        }

    def test_data(self):
        serializer = self.serializer(self.person, context=self.context)
        self.assertDictEqual(serializer.data, self.expected)

    def test_social_networks(self):
        facebook = PersonSocialNetworkFactory(person=self.person, type='facebook', title='')
        twitter = PersonSocialNetworkFactory(person=self.person, type='twitter', title='@MrTerry')
        others = PersonSocialNetworkFactory(person=self.person, type='others', title='')
        self.expected['urls'] = {
            'facebook': facebook.url,
            'twitter': twitter.url,
            'blog': None,
        }
        self.expected['urls_detailed'] = [
            {
                'id': facebook.id,
                'type': facebook.type,
                'url': facebook.url,
                'title': facebook.title,
                'display_title': facebook.display_title,
            },
            {
                'id': twitter.id,
                'type': twitter.type,
                'url': twitter.url,
                'title': twitter.title,
                'display_title': twitter.display_title,
            },
            {
                'id': others.id,
                'type': others.type,
                'url': others.url,
                'title': others.title,
                'display_title': others.display_title,
            },
        ]
        serializer = self.serializer(self.person, context=self.context)
        self.assertDictEqual(serializer.data, self.expected)

        # Test display_title
        # Test that empty string titles get changed to type when looking at display title for not OTHERS
        self.assertEqual('Facebook', self.person.person_networks.get(type='facebook', title='').display_title)
        # Test that defined titles are shown
        self.assertEqual('@MrTerry', self.person.person_networks.get(type='twitter', title='@MrTerry').display_title)
        # Test that empty string titles get changed to url when looking at display title for OTHERS
        self.assertEqual(others.url, self.person.person_networks.get(type='others', title='').display_title)

    def test_areas_of_expertise(self):
        area_1 = PersonAreaOfExpertiseFactory(person=self.person)
        area_2 = PersonAreaOfExpertiseFactory(person=self.person)
        self.expected['areas_of_expertise'] = [
            {
                'id': area_1.id,
                'value': area_1.value,
            },
            {
                'id': area_2.id,
                'value': area_2.value,
            },
        ]
        serializer = self.serializer(self.person, context=self.context)
        self.assertDictEqual(serializer.data, self.expected)


class PersonSerializerTests(MinimalPersonSerializerTests):
    def setUp(self):
        super().setUp()
        self.serializer = PersonSerializer


class PositionSerializerTests(TestCase):
    def test_data(self):
        position = PositionFactory()
        serializer = PositionSerializer(position)
        expected = {
            'title': str(position.title),
            'organization_name': position.organization_name,
            'organization_id': position.organization_id,
            'organization_override': position.organization_override,
            'organization_marketing_url': position.organization.marketing_url,
            'organization_uuid': position.organization.uuid,
            'organization_logo_image_url': position.organization.logo_image.url
        }

        self.assertDictEqual(serializer.data, expected)

    def test_position_with_no_org(self):
        position = PositionFactory(organization=None)
        serializer = PositionSerializer(position)
        expected = {
            'title': str(position.title),
            'organization_name': None,
            'organization_id': None,
            'organization_override': None,
            'organization_marketing_url': None,
            'organization_logo_image_url': None,
            'organization_uuid': None,
        }

        self.assertDictEqual(serializer.data, expected)

    def test_position_with_org_no_image(self):
        organization = OrganizationFactory(logo_image=None)
        position = PositionFactory(organization=organization)
        serializer = PositionSerializer(position)
        expected = {
            'title': str(position.title),
            'organization_name': position.organization_name,
            'organization_id': position.organization_id,
            'organization_override': position.organization_override,
            'organization_marketing_url': position.organization.marketing_url,
            'organization_uuid': position.organization.uuid,
            'organization_logo_image_url': None
        }

        self.assertDictEqual(serializer.data, expected)


class AdditionalPromoAreaSerializerTests(TestCase):
    serializer_class = AdditionalPromoAreaSerializer

    def test_data(self):
        extra_description = AdditionalPromoAreaFactory()
        serializer = AdditionalPromoAreaSerializer(extra_description)
        expected = {
            'title': extra_description.title,
            'description': extra_description.description,
        }
        assert serializer.data == expected


class AffiliateWindowSerializerTests(TestCase):
    def test_data(self):
        user = UserFactory()
        CatalogFactory(query='*:*', viewers=[user])
        course_run = CourseRunFactory(card_image_url='')
        course_run.weeks_to_complete = 1
        course_run.save()
        seat = SeatFactory(course_run=course_run)
        serializer = AffiliateWindowSerializer(seat)

        # Verify none of the course run attributes are empty; otherwise, Affiliate Window will report errors.
        assert all((course_run.title, course_run.short_description, course_run.marketing_url))

        expected = {
            'pid': f'{course_run.key}-{seat.type.slug}',
            'name': course_run.title,
            'desc': course_run.full_description,
            'purl': course_run.marketing_url,
            'price': {
                'actualp': seat.price
            },
            'currency': seat.currency.code,
            'imgurl': course_run.image_url,
            'category': 'Other Experiences',
            'validfrom': course_run.start.strftime('%Y-%m-%d'),
            'validto': course_run.end.strftime('%Y-%m-%d'),
            'lang': course_run.language.code.split('-')[0].lower(),
            'custom1': course_run.pacing_type,
            'custom2': course_run.level_type.name_t,
            'custom3': ','.join(subject.name for subject in course_run.subjects.all()),
            'custom4': ','.join(org.name for org in course_run.authoring_organizations.all()),
            'custom5': course_run.short_description,
            'custom6': str(course_run.weeks_to_complete) + ' week',
        }

        assert serializer.data == expected


class ProgramsAffiliateWindowSerializerTests(TestCase):
    def test_data(self):
        user = UserFactory()

        CatalogFactory(query='*:*', program_query='*', viewers=[user])
        course = CourseFactory()
        course_run = CourseRunFactory(
            transcript_languages=LanguageTag.objects.filter(code__in=['en-us']),
            authoring_organizations=[OrganizationFactory()]
        )
        course_run.save()
        course.course_runs.add(course_run)
        course.canonical_course_run = course_run
        course.save()

        applicable_seat_types = SeatTypeFactory.create_batch(3)
        SeatFactory.create(
            course_run=course_run,
            type=applicable_seat_types[0],
            price=10,
            sku='ABCDEF'
        )
        program_type = ProgramTypeFactory(applicable_seat_types=applicable_seat_types)
        program = ProgramFactory(
            courses=[course_run.course],
            type=program_type,
            banner_image=make_image_file('test_banner.jpg'),
        )
        serializer = ProgramsAffiliateWindowSerializer(program)

        expected = {
            'pid': str(program.uuid),
            'name': program.title,
            'desc': program.overview,
            'purl': program.marketing_url,
            'price': str(program.price_ranges[0].get('total')),
            'currency': program.price_ranges[0].get('currency'),
            'imgurl': program.banner_image.url,
            'category': 'Other Experiences',
            'lang': program.languages.pop().code.split('-')[0].lower(),
            'custom1': program.type.slug,
        }
        assert serializer.data == expected


class CourseSearchSerializerMixin:
    serializer_class = None

    def serialize_course(self, course, request):
        """ Serializes the given `Course` as a search result. """
        result = SearchQuerySet().models(Course).filter(key=course.key)[0]
        return self.serializer_class(result, context={'request': request})  # pylint: disable=not-callable


class CourseSearchSerializerTests(TestCase, CourseSearchSerializerMixin):
    serializer_class = CourseSearchSerializer

    def test_data(self):
        request = make_request()
        organization = OrganizationFactory()
        # 'organizations' in serialized data should not return duplicate organization names
        # Add the same organization twice to the course and make sure only one is in the serialized data
        course = CourseFactory(
            subjects=SubjectFactory.create_batch(3),
            authoring_organizations=[organization],
            sponsoring_organizations=[organization],
        )
        course_run = CourseRunFactory(course=course)
        course.course_runs.add(course_run)
        course.save()
        seat = SeatFactory(course_run=course_run)
        serializer = self.serialize_course(course, request)
        assert serializer.data == self.get_expected_data(course, course_run, seat)

    def test_exclude_expired_and_keep_current_course_run(self):
        request = make_request({'exclude_expired_course_run': True})
        organization = OrganizationFactory()
        course = CourseFactory(
            subjects=SubjectFactory.create_batch(3),
            authoring_organizations=[organization],
            sponsoring_organizations=[organization],
        )
        course_run = CourseRunFactory(
            course=course,
            end=datetime.datetime.now(UTC) + datetime.timedelta(days=10)
        )
        course_run_expired = CourseRunFactory(
            course=course,
            end=datetime.datetime.now(UTC) - datetime.timedelta(days=10),
            enrollment_end=datetime.datetime.now(UTC) - datetime.timedelta(days=10)
        )
        course.course_runs.add(course_run, course_run_expired)
        course.save()
        seat = SeatFactory(course_run=course_run)
        serializer = self.serialize_course(course, request)
        assert serializer.data["course_runs"] == self.get_expected_data(course, course_run, seat)["course_runs"]

    def test_exclude_expired_course_run(self):
        request = make_request({'exclude_expired_course_run': True})
        organization = OrganizationFactory()
        course = CourseFactory(
            subjects=SubjectFactory.create_batch(3),
            authoring_organizations=[organization],
            sponsoring_organizations=[organization],
        )
        course_run = CourseRunFactory(
            course=course,
            end=datetime.datetime.now(UTC) - datetime.timedelta(days=10),
            enrollment_end=datetime.datetime.now(UTC) - datetime.timedelta(days=10)
        )
        course.course_runs.add(course_run)
        course.save()
        seat = SeatFactory(course_run=course_run)
        expected = {
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
            'content_type': 'course',
            'aggregation_key': f'course:{course.key}',
            'card_image_url': course.card_image_url,
            'image_url': course.image_url,
            'course_runs': [],
            'uuid': str(course.uuid),
            'subjects': [subject.name for subject in course.subjects.all()],
            'languages': [
                serialize_language(course_run.language) for course_run in course.course_runs.all()
                if course_run.language
            ],
            'seat_types': [seat.type.slug],
            'organizations': [
                '{key}: {name}'.format(
                    key=course.sponsoring_organizations.first().key,
                    name=course.sponsoring_organizations.first().name,
                )
            ]
        }

        serializer = self.serialize_course(course, request)
        self.assertDictEqual(serializer.data, expected)

    def test_detail_fields_in_response(self):
        request = make_request({'detail_fields': True})
        organization = OrganizationFactory()
        # 'organizations' in serialized data should not return duplicate organization names
        # Add the same organization twice to the course and make sure only one is in the serialized data
        course = CourseFactory(
            subjects=SubjectFactory.create_batch(3),
            authoring_organizations=[organization],
            sponsoring_organizations=[organization],
        )
        course_run = CourseRunFactory(course=course)
        course.course_runs.add(course_run)
        course.save()
        seat = SeatFactory(course_run=course_run)
        expected = {
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
            'content_type': 'course',
            'aggregation_key': f'course:{course.key}',
            'card_image_url': course.card_image_url,
            'image_url': course.image_url,
            'course_runs': [{
                'key': course_run.key,
                'enrollment_start': course_run.enrollment_start,
                'enrollment_end': course_run.enrollment_end,
                'go_live_date': course_run.go_live_date,
                'start': course_run.start,
                'end': course_run.end,
                'modified': course_run.modified,
                'availability': course_run.availability,
                'status': course_run.status,
                'pacing_type': course_run.pacing_type,
                'enrollment_mode': course_run.type_legacy,
                'min_effort': course_run.min_effort,
                'max_effort': course_run.max_effort,
                'weeks_to_complete': course_run.weeks_to_complete,
                'estimated_hours': get_course_run_estimated_hours(course_run),
                'first_enrollable_paid_seat_price': course_run.first_enrollable_paid_seat_price or 0.0,
                'is_enrollable': course_run.is_enrollable,
                'staff': MinimalPersonSerializer(course_run.staff, many=True,
                                                 context={'request': request}).data,
                'content_language': course_run.language.code if course_run.language else None,

            }],
            'uuid': str(course.uuid),
            'subjects': [subject.name for subject in course.subjects.all()],
            'languages': [
                serialize_language(course_run.language) for course_run in course.course_runs.all()
                if course_run.language
            ],
            'seat_types': [seat.type.slug],
            'organizations': [
                '{key}: {name}'.format(
                    key=course.sponsoring_organizations.first().key,
                    name=course.sponsoring_organizations.first().name,
                )
            ],
            'outcome': course.outcome,
            'level_type': course.level_type.name,
            'modified': course.modified.strftime('%Y-%m-%dT%H:%M:%SZ'),
        }

        serializer = self.serialize_course(course, request)
        self.assertDictEqual(serializer.data, expected)

    @classmethod
    def get_expected_data(cls, course, course_run, seat):
        return {
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
            'content_type': 'course',
            'aggregation_key': f'course:{course.key}',
            'card_image_url': course.card_image_url,
            'image_url': course.image_url,
            'course_runs': [{
                'key': course_run.key,
                'enrollment_start': course_run.enrollment_start,
                'enrollment_end': course_run.enrollment_end,
                'go_live_date': course_run.go_live_date,
                'start': course_run.start,
                'end': course_run.end,
                'modified': course_run.modified,
                'availability': course_run.availability,
                'status': course_run.status,
                'pacing_type': course_run.pacing_type,
                'enrollment_mode': course_run.type_legacy,
                'min_effort': course_run.min_effort,
                'max_effort': course_run.max_effort,
                'weeks_to_complete': course_run.weeks_to_complete,
                'estimated_hours': get_course_run_estimated_hours(course_run),
                'first_enrollable_paid_seat_price': course_run.first_enrollable_paid_seat_price or 0.0,
                'is_enrollable': course_run.is_enrollable,
            }],
            'uuid': str(course.uuid),
            'subjects': [subject.name for subject in course.subjects.all()],
            'languages': [
                serialize_language(course_run.language) for course_run in course.course_runs.all()
                if course_run.language
            ],
            'seat_types': [seat.type.slug],
            'organizations': [
                '{key}: {name}'.format(
                    key=course.sponsoring_organizations.first().key,
                    name=course.sponsoring_organizations.first().name,
                )
            ]
        }


class CourseSearchModelSerializerTests(TestCase, CourseSearchSerializerMixin):
    serializer_class = CourseSearchModelSerializer

    def test_data(self):
        request = make_request()
        course = CourseFactory()
        course_run = CourseRunFactory(course=course)
        course.course_runs.add(course_run)
        course.save()
        serializer = self.serialize_course(course, request)
        assert serializer.data == self.get_expected_data(course, course_run, request)

    @classmethod
    def get_expected_data(cls, course, course_run, request):
        expected_data = CourseWithProgramsSerializerTests.get_expected_data(course, request)
        expected_data.update({'content_type': 'course'})
        return expected_data


class CourseRunSearchSerializerTests(ElasticsearchTestMixin, TestCase):
    serializer_class = CourseRunSearchSerializer

    def test_data(self):
        request = make_request()
        course_run = CourseRunFactory(transcript_languages=LanguageTag.objects.filter(code__in=['en-us', 'zh-cn']),
                                      authoring_organizations=[OrganizationFactory()])
        SeatFactory.create(course_run=course_run, type=SeatTypeFactory.verified(), price=10, sku='ABCDEF')
        program = ProgramFactory(courses=[course_run.course])
        self.reindex_courses(program)
        serializer = self.serialize_course_run(course_run, request)
        assert serializer.data == self.get_expected_data(course_run, request)

    def test_data_without_serializers(self):
        """ Verify a null `LevelType` is properly serialized as None. """
        request = make_request()
        course_run = CourseRunFactory(course__level_type=None)
        serializer = self.serialize_course_run(course_run, request)
        assert serializer.data['level_type'] is None

    def serialize_course_run(self, course_run, request):
        """ Serializes the given `CourseRun` as a search result. """
        result = SearchQuerySet().models(CourseRun).filter(key=course_run.key)[0]
        serializer = self.serializer_class(result, context={'request': request})
        return serializer

    @classmethod
    def get_expected_data(cls, course_run, request):
        return {
            'transcript_languages': [serialize_language(cr_t_l) for cr_t_l in course_run.transcript_languages.all()],
            'min_effort': course_run.min_effort,
            'max_effort': course_run.max_effort,
            'weeks_to_complete': course_run.weeks_to_complete,
            'short_description': course_run.short_description,
            'start': serialize_datetime(course_run.start),
            'end': serialize_datetime(course_run.end),
            'go_live_date': serialize_datetime(course_run.go_live_date),
            'enrollment_start': serialize_datetime(course_run.enrollment_start),
            'enrollment_end': serialize_datetime(course_run.enrollment_end),
            'key': course_run.key,
            'marketing_url': course_run.marketing_url,
            'pacing_type': course_run.pacing_type,
            'mobile_available': course_run.mobile_available,
            'language': serialize_language(course_run.language),
            'full_description': course_run.full_description,
            'title': course_run.title,
            'content_type': 'courserun',
            'org': CourseKey.from_string(course_run.key).org,
            'number': CourseKey.from_string(course_run.key).course,
            'seat_types': [seat.slug for seat in course_run.seat_types],
            'image_url': course_run.image_url,
            'type': course_run.type_legacy,
            'level_type': course_run.level_type.name,
            'availability': course_run.availability,
            'published': course_run.status == CourseRunStatus.Published,
            'partner': course_run.course.partner.short_code,
            'program_types': course_run.program_types,
            'logo_image_urls': [org.logo_image.url for org in course_run.authoring_organizations.all()],
            'authoring_organization_uuids': get_uuids(course_run.authoring_organizations.all()),
            'subject_uuids': get_uuids(course_run.subjects.all()),
            'staff_uuids': get_uuids(course_run.staff.all()),
            'aggregation_key': f'courserun:{course_run.course.key}',
            'has_enrollable_seats': course_run.has_enrollable_seats,
            'first_enrollable_paid_seat_sku': course_run.first_enrollable_paid_seat_sku(),
            'first_enrollable_paid_seat_price': course_run.first_enrollable_paid_seat_price,
            'is_enrollable': course_run.is_enrollable,
        }


class CourseRunSearchModelSerializerTests(CourseRunSearchSerializerTests):
    serializer_class = CourseRunSearchModelSerializer

    @classmethod
    def get_expected_data(cls, course_run, request):
        expected_data = CourseRunWithProgramsSerializerTests.get_expected_data(course_run, request)
        expected_data.update({'content_type': 'courserun'})
        # This explicit conversion needs to happen, apparently because the real type is DRF's 'ReturnDict'. It's weird.
        return dict(expected_data)


class PersonSearchSerializerTest(ElasticsearchTestMixin, TestCase):
    serializer_class = PersonSearchSerializer

    @classmethod
    def get_expected_data(cls, person, request):
        return {
            'salutation': person.salutation,
            'position': [person.position.title, person.position.organization_override],
            'uuid': str(person.uuid),
            'bio': person.bio,
            'bio_language': person.bio_language,
            'content_type': 'person',
            'aggregation_key': 'person:' + str(person.uuid),
            'profile_image_url': person.get_profile_image_url,
            'full_name': person.full_name,
            'organizations': [],
        }

    def test_data(self):
        request = make_request()
        position = PositionFactory()
        person = position.person
        self.reindex_people(person)

        result = SearchQuerySet().models(Person)[0]
        serializer = self.serializer_class(result, context={'request': request})
        # Get data
        assert serializer.data == self.get_expected_data(person, request)


class PersonSearchModelSerializerTests(PersonSearchSerializerTest):
    serializer_class = PersonSearchModelSerializer

    @classmethod
    def get_expected_data(cls, person, request):
        context = {'request': request}
        image_field = StdImageSerializerField()
        image_field._context = context  # pylint: disable=protected-access

        return {
            'uuid': str(person.uuid),
            'salutation': person.salutation,
            'given_name': person.given_name,
            'family_name': person.family_name,
            'bio': person.bio,
            'profile_image': image_field.to_representation(person.profile_image),
            'profile_image_url': person.profile_image.url,
            'position': PositionSerializer(person.position).data,
            'works': [],
            'major_works': person.major_works,
            'urls': {
                'facebook': None,
                'twitter': None,
                'blog': None,
            },
            'urls_detailed': [],
            'areas_of_expertise': [],
            'slug': person.slug,
            'email': None,  # always None
            'content_type': 'person',
            'published': True,
        }


@pytest.mark.django_db
@pytest.mark.usefixtures('haystack_default_connection')
class TestProgramSearchSerializer(TestCase):
    serializer_class = ProgramSearchSerializer

    def setUp(self):
        super().setUp()
        self.request = make_request()

    @classmethod
    def get_expected_data(cls, program, request):
        return {
            'uuid': str(program.uuid),
            'title': program.title,
            'subtitle': program.subtitle,
            'type': program.type.name_t,
            'marketing_url': program.marketing_url,
            'authoring_organizations': OrganizationSerializer(program.authoring_organizations, many=True).data,
            'content_type': 'program',
            'card_image_url': program.card_image_url,
            'status': program.status,
            'published': program.status == ProgramStatus.Active,
            'partner': program.partner.short_code,
            'authoring_organization_uuids': get_uuids(program.authoring_organizations.all()),
            'subject_uuids': get_uuids(
                itertools.chain.from_iterable(course.subjects.all() for course in program.courses.all())
            ),
            'staff_uuids': get_uuids(
                itertools.chain.from_iterable(course.staff.all() for course in list(program.course_runs))
            ),
            'aggregation_key': f'program:{program.uuid}',
            'weeks_to_complete_min': program.weeks_to_complete_min,
            'weeks_to_complete_max': program.weeks_to_complete_max,
            'min_hours_effort_per_week': program.min_hours_effort_per_week,
            'max_hours_effort_per_week': program.max_hours_effort_per_week,
            'language': [serialize_language(language) for language in program.languages],
            'hidden': program.hidden,
            'is_program_eligible_for_one_click_purchase': program.is_program_eligible_for_one_click_purchase,
            'search_card_display': [],
        }

    def serialize_program(self, program, request):
        """ Serializes the given `Program` as a search result. """
        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        serializer = self.serializer_class(result, context={'request': request})
        return serializer

    def test_data(self):
        authoring_organization, crediting_organization = OrganizationFactory.create_batch(2)
        program = ProgramFactory(authoring_organizations=[authoring_organization],
                                 credit_backing_organizations=[crediting_organization])
        serializer = self.serialize_program(program, self.request)
        expected = self.get_expected_data(program, self.request)
        assert serializer.data == expected

    def test_data_without_organizations(self):
        """ Verify the serializer serialized programs with no associated organizations.
        In such cases the organizations value should be an empty array. """
        program = ProgramFactory(authoring_organizations=[], credit_backing_organizations=[])
        serializer = self.serialize_program(program, self.request)
        expected = self.get_expected_data(program, self.request)
        assert serializer.data == expected

    def test_data_with_languages(self):
        """
        Verify that program languages are serialized.
        """
        course_run = CourseRunFactory(language=LanguageTag.objects.get(code='en-us'),
                                      authoring_organizations=[OrganizationFactory()])
        CourseRunFactory(course=course_run.course, language=LanguageTag.objects.get(code='zh-cmn'))
        program = ProgramFactory(courses=[course_run.course])
        serializer = self.serialize_program(program, self.request)
        expected = self.get_expected_data(program, self.request)
        assert serializer.data == expected
        if 'language' in expected:
            assert {'English', 'Chinese - Mandarin'} == {*expected['language']}
        else:
            assert {'en-us', 'zh-cmn'} == {*expected['languages']}


class ProgramSearchModelSerializerTest(TestProgramSearchSerializer):
    serializer_class = ProgramSearchModelSerializer

    @classmethod
    def get_expected_data(cls, program, request):
        expected = ProgramSerializerTests.get_expected_data(program, request)
        expected.update({'content_type': 'program'})
        expected.update({'marketing_hook': program.marketing_hook})
        return expected


@pytest.mark.django_db
@pytest.mark.usefixtures('haystack_default_connection')
class TestTypeaheadCourseRunSearchSerializer:
    serializer_class = TypeaheadCourseRunSearchSerializer

    @classmethod
    def get_expected_data(cls, course_run):
        return {
            'key': course_run.key,
            'title': course_run.title,
            'orgs': [org.key for org in course_run.authoring_organizations.all()],
            'marketing_url': course_run.marketing_url,
        }

    def test_data(self):
        authoring_organization = OrganizationFactory()
        course_run = CourseRunFactory(authoring_organizations=[authoring_organization])
        serialized_course = self.serialize_course_run(course_run)
        assert serialized_course.data == self.get_expected_data(course_run)

    def serialize_course_run(self, course_run):
        """ Serializes the given `CourseRun` as a typeahead result. """
        result = SearchQuerySet().models(CourseRun).filter(key=course_run.key)[0]
        serializer = self.serializer_class(result)
        return serializer


@pytest.mark.django_db
@pytest.mark.usefixtures('haystack_default_connection')
class TestTypeaheadProgramSearchSerializer:
    serializer_class = TypeaheadProgramSearchSerializer

    @classmethod
    def get_expected_data(cls, program):
        return {
            'uuid': str(program.uuid),
            'title': program.title,
            'type': program.type.name_t,
            'orgs': [org.key for org in program.authoring_organizations.all()],
            'marketing_url': program.marketing_url,
        }

    def test_data(self):
        authoring_organization = OrganizationFactory()
        program = ProgramFactory(authoring_organizations=[authoring_organization])
        serialized_program = self.serialize_program(program)
        expected = self.get_expected_data(program)
        assert serialized_program.data == expected

    def test_data_multiple_authoring_organizations(self):
        authoring_organizations = OrganizationFactory.create_batch(3)
        program = ProgramFactory(authoring_organizations=authoring_organizations)
        serialized_program = self.serialize_program(program)
        expected = [org.key for org in authoring_organizations]
        assert serialized_program.data['orgs'] == expected

    def serialize_program(self, program):
        """ Serializes the given `Program` as a typeahead result. """
        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        serializer = self.serializer_class(result)
        return serializer


@override_switch('use_company_name_as_utm_source_value', True)
class TestGetUTMSourceForUser(LMSAPIClientMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.user = UserFactory.create()
        self.partner = PartnerFactory.create()

    @override_switch('use_company_name_as_utm_source_value', active=False)
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_with_waffle_switch_turned_off(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_utm_source_for_user` returns User's username when waffle switch
        `use_company_name_as_utm_source_value` is turned off.
        """

        assert get_utm_source_for_user(self.partner, self.user) == self.user.username

    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_with_missing_lms_url(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_utm_source_for_user` returns default value if
        `Partner.lms_url` is not set in the database.
        """
        assert get_utm_source_for_user(self.partner, self.user) == self.user.username

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_when_api_response_is_not_valid(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_utm_source_for_user` returns default value if
        LMS API does not return a valid response.
        """
        self.partner.lms_url = 'http://127.0.0.1:8000'
        self.mock_api_access_request(self.partner.lms_url, self.user, status=400)
        assert get_utm_source_for_user(self.partner, self.user) == self.user.username

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_get_utm_source_for_user(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_utm_source_for_user` returns correct value.
        """
        self.partner.lms_url = 'http://127.0.0.1:8000'
        company_name = 'Test Company'
        expected_utm_source = slugify(f'{self.user.username} {company_name}')

        self.mock_api_access_request(
            self.partner.lms_url, self.user, api_access_request_overrides={'company_name': company_name},
        )
        assert get_utm_source_for_user(self.partner, self.user) == expected_utm_source


class CollaboratorSerializerTests(TestCase):
    serializer_class = CollaboratorSerializer

    def test_data(self):
        self.maxDiff = None

        request = make_request()

        image_field = StdImageSerializerField()
        image_field._context = {'request': request}  # pylint: disable=protected-access

        collaborator = CollaboratorFactory()
        serializer = self.serializer_class(collaborator, context={'request': request})
        image = image_field.to_representation(collaborator.image)

        expected = {
            'name': collaborator.name,
            'image': image,
            'image_url': collaborator.image_url,
            'uuid': str(collaborator.uuid)
        }

        self.assertDictEqual(serializer.data, expected)
