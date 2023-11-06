# pylint: disable=test-inherits-tests
import datetime
import itertools
import re
from urllib.parse import urlencode

import ddt
import pytest
import responses
from django.test import TestCase
from django.utils.text import slugify
from elasticsearch_dsl.query import Q as ESDSLQ
from opaque_keys.edx.keys import CourseKey
from pytz import UTC
from taggit.models import Tag
from waffle.testutils import override_switch

from course_discovery.apps.api.fields import ImageField, StdImageSerializerField
from course_discovery.apps.api.serializers import (
    AdditionalMetadataSerializer, AdditionalPromoAreaSerializer, AffiliateWindowSerializer, CatalogSerializer,
    CertificateInfoSerializer, CollaboratorSerializer, ContainedCourseRunsSerializer, ContainedCoursesSerializer,
    ContentTypeSerializer, CorporateEndorsementSerializer, CourseEditorSerializer, CourseEntitlementSerializer,
    CourseLocationRestrictionSerializer, CourseRecommendationSerializer, CourseReviewSerializer, CourseRunSerializer,
    CourseRunWithProgramsSerializer, CourseSerializer, CourseWithProgramsSerializer,
    CourseWithRecommendationsSerializer, CurriculumSerializer, DegreeAdditionalMetadataSerializer, DegreeCostSerializer,
    DegreeDeadlineSerializer, EndorsementSerializer, FactSerializer, FAQSerializer,
    FlattenedCourseRunWithCourseSerializer, GeoLocationSerializer, IconTextPairingSerializer, ImageSerializer,
    LevelTypeSerializer, MinimalCourseRunSerializer, MinimalCourseSerializer, MinimalOrganizationSerializer,
    MinimalPersonSerializer, MinimalProgramCourseSerializer, MinimalProgramSerializer, NestedProgramSerializer,
    OrganizationSerializer, PathwaySerializer, PersonSerializer, PositionSerializer, PrerequisiteSerializer,
    ProductMetaSerializer, ProductValueSerializer, ProgramLocationRestrictionSerializer,
    ProgramsAffiliateWindowSerializer, ProgramSerializer, ProgramTypeAttrsSerializer, ProgramTypeSerializer,
    RankingSerializer, SeatSerializer, SourceSerializer, SubjectSerializer, TaxiFormSerializer, TopicSerializer,
    TypeaheadCourseRunSearchSerializer, TypeaheadProgramSearchSerializer, VideoSerializer,
    get_lms_course_url_for_archived, get_utm_source_for_user
)
from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.api.tests.test_utils import make_post_request, make_request
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.models import Currency, User
from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin, LMSAPIClientMixin
from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import AbstractLocationRestrictionModel, CourseReview
from course_discovery.apps.course_metadata.search_indexes.documents import (
    CourseDocument, CourseRunDocument, LearnerPathwayDocument, PersonDocument, ProgramDocument
)
from course_discovery.apps.course_metadata.search_indexes.serializers import (
    CourseRunSearchDocumentSerializer, CourseRunSearchModelSerializer, CourseSearchDocumentSerializer,
    CourseSearchModelSerializer, LearnerPathwaySearchDocumentSerializer, LearnerPathwaySearchModelSerializer,
    PersonSearchDocumentSerializer, PersonSearchModelSerializer, ProgramSearchDocumentSerializer,
    ProgramSearchModelSerializer
)
from course_discovery.apps.course_metadata.tests.factories import (
    AdditionalMetadataFactory, AdditionalPromoAreaFactory, CertificateInfoFactory, CollaboratorFactory,
    CorporateEndorsementFactory, CourseEditorFactory, CourseEntitlementFactory, CourseFactory,
    CourseLocationRestrictionFactory, CourseRunFactory, CourseSkillsFactory, CurriculumCourseMembershipFactory,
    CurriculumFactory, CurriculumProgramMembershipFactory, DegreeAdditionalMetadataFactory, DegreeCostFactory,
    DegreeDeadlineFactory, DegreeFactory, EndorsementFactory, ExpectedLearningItemFactory, FactFactory,
    IconTextPairingFactory, ImageFactory, JobOutlookItemFactory, OrganizationFactory, PathwayFactory,
    PersonAreaOfExpertiseFactory, PersonFactory, PersonSocialNetworkFactory, PositionFactory, PrerequisiteFactory,
    ProgramFactory, ProgramLocationRestrictionFactory, ProgramSkillFactory, ProgramSubscriptionFactory,
    ProgramSubscriptionPriceFactory, ProgramTypeFactory, RankingFactory, SeatFactory, SeatTypeFactory,
    SpecializationFactory, SubjectFactory, TopicFactory, VideoFactory
)
from course_discovery.apps.course_metadata.utils import get_course_run_estimated_hours
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.learner_pathway.api.serializers import LearnerPathwayStepSerializer
from course_discovery.apps.learner_pathway.tests.factories import (
    LearnerPathwayCourseFactory, LearnerPathwayFactory, LearnerPathwayProgramFactory, LearnerPathwayStepFactory
)
from course_discovery.apps.learner_pathway.tests.test_serializer import TestLearnerPathwaySerializer


def json_date_format(datetime_obj):
    return datetime_obj and datetime.datetime.strftime(datetime_obj, "%Y-%m-%dT%H:%M:%S.%fZ")


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
        assert not serializer.is_valid()
        assert User.objects.filter(username=username).count() == 0


class MinimalCourseSerializerTests(SiteMixin, TestCase):
    serializer_class = MinimalCourseSerializer

    @classmethod
    def get_expected_data(cls, course, course_skill, request):  # pylint: disable=unused-argument
        context = {'request': request}

        return {
            'key': course.key,
            'uuid': str(course.uuid),
            'title': course.title,
            'excluded_from_search': course.excluded_from_search,
            'excluded_from_seo': course.excluded_from_seo,
            'course_runs': MinimalCourseRunSerializer(course.course_runs, many=True, context=context).data,
            'entitlements': [],
            'owners': MinimalOrganizationSerializer(course.authoring_organizations, many=True, context=context).data,
            'image': ImageField().to_representation(course.image_url),
            'short_description': course.short_description,
            'type': course.type.uuid,
            'course_type': course.type.slug,
            'enterprise_subscription_inclusion': course.enterprise_subscription_inclusion,
            'url_slug': None,
        }

    def test_data(self):
        self.maxDiff = None
        request = make_request()
        organizations = OrganizationFactory(partner=self.partner)
        course = CourseFactory(authoring_organizations=[organizations], partner=self.partner)
        CourseRunFactory.create_batch(2, course=course)
        serializer = self.serializer_class(course, context={'request': request})
        course_skill = CourseSkillsFactory(course_key=course.key)
        CourseSkillsFactory(course_key=course.key, is_blacklisted=True)
        expected = self.get_expected_data(course, course_skill, request)
        self.assertDictEqual(serializer.data, expected)


class CourseSerializerTests(MinimalCourseSerializerTests):
    serializer_class = CourseSerializer

    @classmethod
    def get_expected_data(cls, course, course_skill, request):
        expected = super().get_expected_data(course, course_skill, request)

        expected.update({
            'short_description': course.short_description,
            'full_description': course.full_description,
            'level_type': course.level_type.name_t,
            'extra_description': AdditionalPromoAreaSerializer(course.extra_description).data,
            'product_source': SourceSerializer(course.product_source).data,
            'additional_metadata': AdditionalMetadataSerializer(course.additional_metadata).data,
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
            'data_modified_timestamp': json_date_format(course.data_modified_timestamp),
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
            'skill_names': [course_skill.skill.name],
            'skills': [
                {
                    'name': course_skill.skill.name,
                    'description': course_skill.skill.description,
                    'category': None,
                    'subcategory': None,
                }
            ],
            'organization_short_code_override': course.organization_short_code_override,
            'organization_logo_override_url': course.organization_logo_override_url,
            'enterprise_subscription_inclusion': course.enterprise_subscription_inclusion,
            'geolocation': GeoLocationSerializer(course.geolocation).data,
            'location_restriction': CourseLocationRestrictionSerializer(
                course.location_restriction
            ).data,
            'in_year_value': ProductValueSerializer(course.in_year_value).data,
            'watchers': [],
        })

        return expected

    def test_exclude_utm(self):
        request = make_request()
        course = CourseFactory()
        course_runs = CourseRunFactory.create_batch(3, course=course)
        course.canonical_course_run = course_runs[0]
        serializer = self.serializer_class(course, context={'request': request, 'exclude_utm': 1})

        assert serializer.data['marketing_url'] == course.marketing_url

    def test_canonical_course_run_key(self):
        request = make_request()
        course = CourseFactory()
        course_runs = CourseRunFactory.create_batch(3, course=course)
        course.course_runs.set(course_runs)
        course.canonical_course_run = course_runs[0]
        serializer = self.serializer_class(course, context={'request': request, 'exclude_utm': 1})

        assert serializer.data['canonical_course_run_key'] == course_runs[0].key

    def test_draft_no_marketing_url(self):
        request = make_request()
        course_draft = CourseFactory(draft=True)
        draft_course_run = CourseRunFactory(draft=True, course=course_draft)
        course_draft.canonical_course_run = draft_course_run
        course_draft.save()
        serializer = self.serializer_class(course_draft, context={'request': request, 'exclude_utm': 1, 'editable': 1})

        assert serializer.data['marketing_url'] is None

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
        assert serializer.data['marketing_url'] is not None
        assert serializer.data['marketing_url'] == course.marketing_url

    def test_shortcode_and_logo_override(self):
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
        assert serializer.data['organization_short_code_override'] is not None
        assert serializer.data['organization_logo_override_url'] is not None


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

        assert expected == serializer.data


@ddt.ddt
class CourseWithProgramsSerializerTests(CourseSerializerTests):
    serializer_class = CourseWithProgramsSerializer
    YESTERDAY = datetime.datetime.now(UTC) - datetime.timedelta(days=1)
    TOMORROW = datetime.datetime.now(UTC) + datetime.timedelta(days=1)
    TWO_WEEKS_FROM_TODAY = datetime.datetime.now(UTC) + datetime.timedelta(days=14)

    @classmethod
    def get_expected_data(cls, course, course_skill, request):
        expected = super().get_expected_data(course, course_skill, request)
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
        self.course_skill = CourseSkillsFactory(course_key=self.course.key)
        self.blacklisted_course_skill = CourseSkillsFactory(course_key=self.course.key, is_blacklisted=True)
        self.deleted_program = ProgramFactory(
            courses=[self.course],
            partner=self.partner,
            status=ProgramStatus.Deleted
        )

    def test_data(self):
        expected = self.get_expected_data(self.course, self.course_skill, self.request)
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
        assert serializer.data['advertised_course_run_uuid'] == expected_advertised_course_run.uuid

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
        assert serializer.data['advertised_course_run_uuid'] == expected_advertised_course_run.uuid

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
        assert serializer.data['advertised_course_run_uuid'] == expected_advertised_course_run.uuid

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
        assert serializer.data['advertised_course_run_uuid'] == expected_advertised_course_run.uuid


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
            'weeks_to_complete': course_run.weeks_to_complete,
            'pacing_type': course_run.pacing_type,
            'type': course_run.type_legacy,
            'run_type': course_run.type.uuid,
            'seats': SeatSerializer(course_run.seats, many=True).data,
            'status': course_run.status,
            'external_key': course_run.external_key,
            'is_enrollable': course_run.is_enrollable,
            'is_marketable': course_run.is_marketable,
            'availability': course_run.availability,
            'variant_id': str(course_run.variant_id),
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
        assert lms_course_url is None

        partner.lms_url = 'http://127.0.0.1:8000'
        lms_course_url = get_lms_course_url_for_archived(partner, course_key)
        expected_url = f'{partner.lms_url}/courses/{course_key}/course/'
        assert lms_course_url == expected_url


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
            'content_language_search_facet_name': course_run.language.get_search_facet_display(translate=True),
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
            'estimated_hours': get_course_run_estimated_hours(course_run),
            'enterprise_subscription_inclusion': course_run.enterprise_subscription_inclusion,
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

        assert serializer.data['marketing_url'] == course_run.marketing_url

    def test_draft_no_marketing_url(self):
        request = make_request()
        draft_course_run = CourseRunFactory(draft=True)
        serializer = self.serializer_class(draft_course_run, context={'request': request, 'editable': 1})

        assert serializer.data['marketing_url'] is None

    def test_draft_and_official(self):
        request = make_request()
        draft_course_run = CourseRunFactory(draft=True)
        course_run = CourseRunFactory(draft=False, draft_version_id=draft_course_run.id)

        serializer = self.serializer_class(course_run, context={'request': request, 'exclude_utm': 1, 'editable': 1})
        assert serializer.data['marketing_url'] is not None
        assert serializer.data['marketing_url'] == course_run.marketing_url


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
        assert serializer.data['programs'] == []

    def test_include_unpublished_programs(self):
        """
        If a program is unpublished, that program should only be returned on the course run endpoint if we are
        sending the 'include_unpublished_programs' flag.
        """
        unpublished_program = ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Unpublished)
        self.serializer_context['include_unpublished_programs'] = 1
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        assert serializer.data['programs'] ==\
               NestedProgramSerializer([unpublished_program], many=True, context=self.serializer_context).data

    def test_exclude_retired_program(self):
        """
        If a program is retired, that program should not be returned on the course run endpoint by default.
        """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Retired)
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        assert serializer.data['programs'] == []

    def test_include_retired_programs(self):
        """
        If a program is retired, that program should only be returned on the course run endpoint if we are
        sending the 'include_retired_programs' flag.
        """
        retired_program = ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Retired)
        self.serializer_context['include_retired_programs'] = 1
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        assert serializer.data['programs'] == NestedProgramSerializer([retired_program],
                                                                      many=True, context=self.serializer_context).data

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
        assert len(expected['course_runs']) == 1

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
            course.topics.set([topic])

        program = ProgramFactory(
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
        program.labels.add(topic)
        return program

    @classmethod
    def get_expected_data(cls, program, request, include_labels=True):
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
            'data_modified_timestamp': json_date_format(program.data_modified_timestamp),
            'authoring_organizations': MinimalOrganizationSerializer(program.authoring_organizations, many=True).data,
            'card_image_url': program.card_image_url,
            'is_program_eligible_for_one_click_purchase': program.is_program_eligible_for_one_click_purchase,
            'degree': None,
            'taxi_form': TaxiFormSerializer(program.taxi_form).data,
            'curricula': [],
            'marketing_hook': program.marketing_hook,
            'total_hours_of_effort': program.total_hours_of_effort,
            'recent_enrollment_count': 0,
            'organization_short_code_override': program.organization_short_code_override,
            'organization_logo_override_url': program.organization_logo_override_url,
            'primary_subject_override': SubjectSerializer(program.primary_subject_override).data,
            'level_type_override': LevelTypeSerializer(program.level_type_override).data,
            'language_override': program.language_override.code,
            'labels': ['topic'] if include_labels else [],
            'program_duration_override': program.program_duration_override,
            'excluded_from_seo': program.excluded_from_seo,
            'excluded_from_search': program.excluded_from_search,
            'has_ofac_restrictions': program.has_ofac_restrictions,
            'ofac_comment': program.ofac_comment,
            'subscription_eligible': None,
            'subscription_prices': [],
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
    def get_expected_data(cls, program, request, include_labels=True):
        expected = super().get_expected_data(program, request, include_labels)
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
            'enterprise_subscription_inclusion': program.enterprise_subscription_inclusion,
            'product_source': SourceSerializer(program.product_source).data,
            'organization_short_code_override': program.organization_short_code_override,
            'organization_logo_override_url': program.organization_logo_override_url,
            'primary_subject_override': SubjectSerializer(program.primary_subject_override).data,
            'level_type_override': LevelTypeSerializer(program.level_type_override).data,
            'language_override': program.language_override.code,
            'is_2u_degree_program': program.is_2u_degree_program,
            'geolocation': GeoLocationSerializer(program.geolocation).data,
            'location_restriction': ProgramLocationRestrictionSerializer(
                program.location_restriction, read_only=True
            ).data,
            'in_year_value': ProductValueSerializer(program.in_year_value).data,
            'skill_names': [],
            'skills': [],
            'subscription_eligible': None,
            'subscription_prices': [],
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

    def test_data_with_skills(self):
        """
        Verify we can specify program excluded_course_runs and the serializers will
        render the course_runs with exclusions
        """
        request = make_request()
        program = self.create_program()
        program_skill = ProgramSkillFactory(
            program_uuid=program.uuid
        )

        expected = self.get_expected_data(program, request)
        expected['skill_names'] = [program_skill.skill.name]
        expected['skills'] = [
            {
                'name': program_skill.skill.name,
                'description': program_skill.skill.description,
                'category': None,
                'subcategory': None,
            }
        ]
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

        assert serializer.data['courses'] == expected

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

        assert serializer.data['courses'] == expected

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

        assert serializer.data['courses'] == expected

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
        specializations = SpecializationFactory.create_batch(3)
        degree = DegreeFactory.create(rankings=rankings)
        curriculum = CurriculumFactory.create(program=degree)
        degree.curricula.set([curriculum])
        degree.specializations.set(specializations)
        quick_facts = IconTextPairingFactory.create_batch(3, degree=degree)
        degree.deadline = DegreeDeadlineFactory.create_batch(size=3, degree=degree)
        degree.cost = DegreeCostFactory.create_batch(size=3, degree=degree)
        degree.additional_metadata = DegreeAdditionalMetadataFactory.create(degree=degree)
        topic = Tag.objects.create(name="topic")

        degree.labels.add(topic)

        serializer = self.serializer_class(degree, context={'request': request})
        expected = self.get_expected_data(degree, request)
        expected_rankings = RankingSerializer(rankings, many=True).data
        expected_curriculum = CurriculumSerializer(curriculum).data
        expected_quick_facts = IconTextPairingSerializer(quick_facts, many=True).data
        expected_degree_deadlines = DegreeDeadlineSerializer(degree.deadline, many=True).data
        expected_degree_costs = DegreeCostSerializer(degree.cost, many=True).data
        expected_degree_additional_metadata = DegreeAdditionalMetadataSerializer(degree.additional_metadata).data
        expected_specializations = [specialization.value for specialization in specializations]

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
            'additional_metadata': expected_degree_additional_metadata,
            'specializations': expected_specializations,
            'program_duration_override': degree.program_duration_override,
            'display_on_org_page': degree.display_on_org_page,
            'excluded_from_seo': degree.excluded_from_seo,
            'excluded_from_search': degree.excluded_from_search,
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

    def test_data_without_subscription(self):
        program = self.create_program()
        request = make_request()
        serializer = self.serializer_class(program, context={'request': request})
        self.assertIsNone(serializer.data['subscription_eligible'])

    def test_data_with_subscription(self):
        program = self.create_program()
        program.subscription = ProgramSubscriptionFactory(subscription_eligible=True)
        currency = Currency.objects.get(code='USD')
        ProgramSubscriptionPriceFactory(program_subscription=program.subscription, price=20.0, currency=currency)
        request = make_request()
        serializer = self.serializer_class(program, context={'request': request})
        self.assertIsNotNone(serializer.data['subscription_eligible'])
        self.assertIsNotNone(serializer.data['subscription_prices'])


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
        certificate_logo_image_url = getattr(
            getattr(
                organization,
                'certificate_logo_image',
                None
            ),
            'url',
            None
        )
        logo_image_url = getattr(
            getattr(
                organization,
                'logo_image',
                None
            ),
            'url',
            None
        )
        return {
            'uuid': str(organization.uuid),
            'key': organization.key,
            'name': organization.name,
            'auto_generate_course_run_keys': organization.auto_generate_course_run_keys,
            'certificate_logo_image_url': certificate_logo_image_url,
            'logo_image_url': logo_image_url,
            'organization_hex_color': organization.organization_hex_color,
            'data_modified_timestamp': json_date_format(organization.data_modified_timestamp),
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
            'description_es': organization.description_es,
            'homepage_url': organization.homepage_url,
            'logo_image_url': organization.logo_image.url,
            'tags': [cls.TAG],
            'marketing_url': organization.marketing_url,
            'slug': organization.slug,
            'banner_image_url': organization.banner_image.url,
            'enterprise_subscription_inclusion': False,
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

        assert serializer.errors['price']


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
            'upgrade_deadline_override': None,
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

        assert serializer.errors['price']


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
        assert 'Facebook' == self.person.person_networks.get(type='facebook', title='').display_title
        # Test that defined titles are shown
        assert '@MrTerry' == self.person.person_networks.get(type='twitter', title='@MrTerry').display_title
        # Test that empty string titles get changed to url when looking at display title for OTHERS
        assert others.url == self.person.person_networks.get(type='others', title='').display_title

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


class FactSerializerTests(TestCase):
    serializer_class = FactSerializer

    def test_data(self):
        fact = FactFactory()
        serializer = FactSerializer(fact)
        expected = {
            'heading': fact.heading,
            'blurb': fact.blurb,
        }
        assert serializer.data == expected


class CertificateInfoSerializerTests(TestCase):
    serializer_class = CertificateInfoSerializer

    def test_data(self):
        certificate_info = CertificateInfoFactory()
        serializer = CertificateInfoSerializer(certificate_info)
        expected = {
            'heading': certificate_info.heading,
            'blurb': certificate_info.blurb,
        }
        assert serializer.data == expected


class AdditionalMetadataSerializerTests(TestCase):
    serializer_class = AdditionalMetadataSerializer

    def test_data(self):
        additional_metadata = AdditionalMetadataFactory(
            facts=[FactFactory(), FactFactory()],
        )
        serializer = AdditionalMetadataSerializer(additional_metadata)
        expected = {
            'external_identifier': additional_metadata.external_identifier,
            'external_url': additional_metadata.external_url,
            'lead_capture_form_url': additional_metadata.lead_capture_form_url,
            'certificate_info': CertificateInfoSerializer(additional_metadata.certificate_info).data,
            'facts': FactSerializer(additional_metadata.facts, many=True).data,
            'product_meta': ProductMetaSerializer(additional_metadata.product_meta).data,
            'organic_url': additional_metadata.organic_url,
            'start_date': serialize_datetime(additional_metadata.start_date),
            'end_date': serialize_datetime(additional_metadata.end_date),
            'registration_deadline': serialize_datetime(additional_metadata.registration_deadline),
            'variant_id': str(additional_metadata.variant_id),
            'course_term_override': additional_metadata.course_term_override,
            'product_status': additional_metadata.product_status,
            'external_course_marketing_type': additional_metadata.external_course_marketing_type,
            'display_on_org_page': additional_metadata.display_on_org_page,
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
        result = CourseDocument.search().filter('term', **{'key.raw': course.key}).execute()[0]

        return self.serializer_class(result, context={'request': request})  # pylint: disable=not-callable


@ddt.ddt
class CourseSearchDocumentSerializerTests(ElasticsearchTestMixin, TestCase, CourseSearchSerializerMixin):
    serializer_class = CourseSearchDocumentSerializer

    def test_data(self):
        request = make_request()
        organization = OrganizationFactory()
        # 'organizations' in serialized data should not return duplicate organization names
        # Add the same organization twice to the course and make sure only one is in the serialized data
        course = CourseFactory(
            subjects=SubjectFactory.create_batch(3),
            authoring_organizations=[organization],
            sponsoring_organizations=[organization],
            course_length='medium',
        )
        course_run = CourseRunFactory(course=course)
        course.course_runs.add(course_run)
        course.save()
        course.refresh_from_db()
        course_run.refresh_from_db()
        seat = SeatFactory(course_run=course_run)
        course_skill = CourseSkillsFactory(
            course_key=course.key
        )
        CourseSkillsFactory(
            course_key=course.key,
            is_blacklisted=True,
        )
        serializer = self.serialize_course(course, request)
        assert serializer.data == self.get_expected_data(course, course_run, course_skill, seat)

    @ddt.data(True, False)
    def test_exclude_expired_and_keep_current_course_run(self, is_post_request):
        if is_post_request:
            request = make_post_request({'exclude_expired_course_run': True})
        else:
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
        course.refresh_from_db()
        course_run.refresh_from_db()
        seat = SeatFactory(course_run=course_run)
        course_skill = CourseSkillsFactory(
            course_key=course.key
        )
        serializer = self.serialize_course(course, request)
        assert serializer.data["course_runs"] == self.get_expected_data(
            course, course_run, course_skill, seat
        )["course_runs"]

    @ddt.data(True, False)
    def test_exclude_expired_course_run(self, is_post_request):
        if is_post_request:
            request = make_post_request({'exclude_expired_course_run': True})
        else:
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
        course_skill = CourseSkillsFactory(
            course_key=course.key
        )
        expected = {
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
            'content_type': 'course',
            'course_type': course.type.slug,
            'enterprise_subscription_inclusion': course.enterprise_subscription_inclusion,
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
            'skill_names': [course_skill.skill.name],
            'skills': [
                {
                    'name': course_skill.skill.name,
                    'description': course_skill.skill.description,
                    'category': None,
                    'subcategory': None,
                }
            ],
            'course_ends': course.course_ends,
            'end_date': serialize_datetime(course.end_date),
            'organizations': [
                '{key}: {name}'.format(
                    key=course.sponsoring_organizations.first().key,
                    name=course.sponsoring_organizations.first().name,
                )
            ],
            'course_length': course.course_length,
            'external_course_marketing_type': course.additional_metadata.external_course_marketing_type,
            'product_source': course.product_source.slug,
        }

        serializer = self.serialize_course(course, request)
        self.assertDictEqual(serializer.data, expected)

    @ddt.data(True, False)
    def test_detail_fields_in_response(self, is_post_request):
        if is_post_request:
            request = make_post_request({'detail_fields': True})
        else:
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
        course.refresh_from_db()
        course_run.refresh_from_db()
        seat = SeatFactory(course_run=course_run)
        course_skill = CourseSkillsFactory(
            course_key=course.key
        )
        CourseSkillsFactory(
            course_key=course.key,
            is_blacklisted=True,
        )
        expected = {
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
            'content_type': 'course',
            'course_type': course.type.slug,
            'enterprise_subscription_inclusion': course.enterprise_subscription_inclusion,
            'aggregation_key': f'course:{course.key}',
            'card_image_url': course.card_image_url,
            'image_url': course.image_url,
            'course_runs': [{
                'key': course_run.key,
                'enrollment_start': serialize_datetime(course_run.enrollment_start),
                'enrollment_end': serialize_datetime(course_run.enrollment_end),
                'go_live_date': course_run.go_live_date,
                'start': serialize_datetime(course_run.start),
                'end': serialize_datetime(course_run.end),
                'modified': serialize_datetime(course_run.modified),
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
            'skill_names': [course_skill.skill.name],
            'skills': [
                {
                    'name': course_skill.skill.name,
                    'description': course_skill.skill.description,
                    'category': None,
                    'subcategory': None,
                }
            ],
            'course_ends': course.course_ends,
            'end_date': serialize_datetime(course.end_date),
            'organizations': [
                '{key}: {name}'.format(
                    key=course.sponsoring_organizations.first().key,
                    name=course.sponsoring_organizations.first().name,
                )
            ],
            'outcome': course.outcome,
            'level_type': course.level_type.name,
            'modified': course.modified,
            'course_length': course.course_length,
            'external_course_marketing_type': course.additional_metadata.external_course_marketing_type,
            'product_source': course.product_source.slug,
        }
        if is_post_request:
            del expected['outcome']
            del expected['level_type']
            del expected['modified']
        serializer = self.serialize_course(course, request)
        self.assertDictEqual(serializer.data, expected)

    @classmethod
    def get_expected_data(cls, course, course_run, course_skill, seat):
        return {
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
            'content_type': 'course',
            'course_type': course.type.slug,
            'enterprise_subscription_inclusion': course.enterprise_subscription_inclusion,
            'aggregation_key': f'course:{course.key}',
            'card_image_url': course.card_image_url,
            'image_url': course.image_url,
            'course_runs': [{
                'key': course_run.key,
                'enrollment_start': serialize_datetime(course_run.enrollment_start),
                'enrollment_end': serialize_datetime(course_run.enrollment_end),
                'go_live_date': course_run.go_live_date,
                'start': serialize_datetime(course_run.start),
                'end': serialize_datetime(course_run.end),
                'modified': serialize_datetime(course_run.modified),
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
            'skill_names': [course_skill.skill.name],
            'skills': [
                {
                    'name': course_skill.skill.name,
                    'description': course_skill.skill.description,
                    'category': None,
                    'subcategory': None,
                }
            ],
            'course_ends': course.course_ends,
            'end_date': serialize_datetime(course.end_date),
            'organizations': [
                '{key}: {name}'.format(
                    key=course.sponsoring_organizations.first().key,
                    name=course.sponsoring_organizations.first().name,
                )
            ],
            'course_length': course.course_length,
            'external_course_marketing_type': course.additional_metadata.external_course_marketing_type,
            'product_source': course.product_source.slug,
        }


class CourseSearchModelSerializerTests(ElasticsearchTestMixin, TestCase, CourseSearchSerializerMixin):
    serializer_class = CourseSearchModelSerializer

    def test_data(self):
        request = make_request()
        course = CourseFactory()
        course_skill = CourseSkillsFactory(course_key=course.key)
        CourseSkillsFactory(course_key=course.key, is_blacklisted=True)
        course_run = CourseRunFactory(course=course)
        course.course_runs.add(course_run)
        course.save()
        serializer = self.serialize_course(course, request)
        assert serializer.data == self.get_expected_data(course, course_skill, request)

    @classmethod
    def get_expected_data(cls, course, course_skill, request):
        course.refresh_from_db()
        expected_data = CourseWithProgramsSerializerTests.get_expected_data(course, course_skill, request)
        expected_data.update({'content_type': 'course'})
        return expected_data


class CourseRunSearchDocumentSerializerTests(ElasticsearchTestMixin, TestCase):
    serializer_class = CourseRunSearchDocumentSerializer

    def test_data(self):
        request = make_request()
        course_run = CourseRunFactory(transcript_languages=LanguageTag.objects.filter(code__in=['en-us', 'zh-cn']),
                                      authoring_organizations=[OrganizationFactory()])
        SeatFactory.create(course_run=course_run, type=SeatTypeFactory.verified(), price=10, sku='ABCDEF')
        program = ProgramFactory(courses=[course_run.course])
        self.reindex_courses(program)
        course_skill = CourseSkillsFactory(
            course_key=course_run.course.key
        )
        serializer = self.serialize_course_run(course_run, request)
        assert serializer.data == self.get_expected_data(course_run, course_skill, request)

    def test_data_without_serializers(self):
        """ Verify a null `LevelType` is properly serialized as None. """
        request = make_request()
        course_run = CourseRunFactory(course__level_type=None)
        serializer = self.serialize_course_run(course_run, request)
        assert serializer.data['level_type'] is None

    def serialize_course_run(self, course_run, request):
        """ Serializes the given `CourseRun` as a search result. """
        result = CourseRunDocument.search().filter('term', **{'key.raw': course_run.key}).execute()[0]
        serializer = self.serializer_class(result, context={'request': request})
        return serializer

    @classmethod
    def get_expected_data(cls, course_run, course_skill, request):
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
            'skill_names': [course_skill.skill.name],
            'skills': [
                {
                    'name': course_skill.skill.name,
                    'description': course_skill.skill.description,
                    'category': None,
                    'subcategory': None,
                }
            ],
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


class CourseRunSearchModelSerializerTests(CourseRunSearchDocumentSerializerTests):
    serializer_class = CourseRunSearchModelSerializer

    @classmethod
    def get_expected_data(cls, course_run, course_skill, request):
        expected_data = CourseRunWithProgramsSerializerTests.get_expected_data(course_run, request)
        expected_data.update({'content_type': 'courserun'})
        # This explicit conversion needs to happen, apparently because the real type is DRF's 'ReturnDict'. It's weird.
        return dict(expected_data)


class PersonSearchDocumentSerializerTest(ElasticsearchTestMixin, TestCase):
    serializer_class = PersonSearchDocumentSerializer

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

        result = PersonDocument.search().query(ESDSLQ('match_all')).execute()[0]
        serializer = self.serializer_class(result, context={'request': request})
        # Get data
        assert serializer.data == self.get_expected_data(person, request)


class PersonSearchModelSerializerTests(PersonSearchDocumentSerializerTest):
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
@pytest.mark.usefixtures('elasticsearch_dsl_default_connection')
class TestProgramSearchDocumentSerializer(TestCase):
    serializer_class = ProgramSearchDocumentSerializer

    def setUp(self):
        super().setUp()
        self.request = make_request()

    @classmethod
    def get_expected_data(cls, program, request):
        return {
            'uuid': str(program.uuid),
            'title': program.title,
            'excluded_from_search': program.excluded_from_search,
            'excluded_from_seo': program.excluded_from_seo,
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
            'is_2u_degree_program': program.is_2u_degree_program,
            'skill_names': [],
            'skills': []
        }

    def serialize_program(self, program, request):
        """ Serializes the given `Program` as a search result. """
        result = ProgramDocument.search().filter('term', uuid=program.uuid).execute()[0]
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


class ProgramSearchModelSerializerTest(TestProgramSearchDocumentSerializer):
    serializer_class = ProgramSearchModelSerializer

    @classmethod
    def get_expected_data(cls, program, request):
        expected = ProgramSerializerTests.get_expected_data(program, request, include_labels=False)
        expected.update({'content_type': 'program'})
        expected.update({'marketing_hook': program.marketing_hook})
        return expected


@pytest.mark.django_db
@pytest.mark.usefixtures('elasticsearch_dsl_default_connection')
class TestLearnerPathwaySearchDocumentSerializer(TestCase):
    serializer_class = LearnerPathwaySearchDocumentSerializer

    def setUp(self):
        super().setUp()
        self.request = make_request()

    @classmethod
    def get_expected_data(cls, learner_pathway, request):
        image_field = StdImageSerializerField()
        image_field._context = {'request': request}  # pylint: disable=protected-access
        return {
            'uuid': str(learner_pathway.uuid),
            'title': learner_pathway.title,
            'aggregation_key': f'learnerpathway:{learner_pathway.uuid}',
            'content_type': 'learnerpathway',
            'status': learner_pathway.status,
            'banner_image': image_field.to_representation(learner_pathway.banner_image),
            'card_image': image_field.to_representation(learner_pathway.card_image),
            'overview': learner_pathway.overview,
            'published': learner_pathway.status == ProgramStatus.Active,
            'skill_names': [skill['name'] for skill in learner_pathway.skills],
            'skills': learner_pathway.skills,
            'partner': learner_pathway.partner.short_code,
            'visible_via_association': True,
            'steps': LearnerPathwayStepSerializer(
                learner_pathway.steps.all(),
                many=True
            ).data,
            'created': serialize_datetime(learner_pathway.created),
        }

    def serialize_learner_pathway(self, learner_pathway, request):
        """ Serializes the given `Program` as a search result. """
        result = LearnerPathwayDocument.search().filter('term', uuid=learner_pathway.uuid).execute()[0]
        serializer = self.serializer_class(result, context={'request': request})
        return serializer

    def test_data(self):
        learner_pathway = LearnerPathwayFactory()
        step = LearnerPathwayStepFactory(pathway=learner_pathway)
        LearnerPathwayCourseFactory(step=step)
        LearnerPathwayProgramFactory(step=step)
        serializer = self.serialize_learner_pathway(learner_pathway, self.request)
        expected = self.get_expected_data(learner_pathway, self.request)
        assert serializer.data == expected


class LearnerPathwaySearchModelSerializerTest(TestLearnerPathwaySearchDocumentSerializer):
    serializer_class = LearnerPathwaySearchModelSerializer

    @classmethod
    def get_expected_data(cls, learner_pathway, request):
        expected = TestLearnerPathwaySerializer.get_expected_data(learner_pathway, request)
        expected.update({'content_type': 'learnerpathway'})
        return expected


@pytest.mark.django_db
@pytest.mark.usefixtures('elasticsearch_dsl_default_connection')
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
        result = CourseRunDocument.search().filter('term', **{'key.raw': course_run.key}).execute()[0]
        serializer = self.serializer_class(result)
        return serializer


@pytest.mark.django_db
@pytest.mark.usefixtures('elasticsearch_dsl_default_connection')
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
            'is_2u_degree_program': program.is_2u_degree_program,
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
        result = ProgramDocument.search().filter('term', uuid=program.uuid).execute()[0]
        serializer = self.serializer_class(result)
        return serializer


@override_switch('use_company_name_as_utm_source_value', True)
class TestGetUTMSourceForUser(LMSAPIClientMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.mock_access_token()
        self.user = UserFactory.create()
        self.partner = PartnerFactory.create()

    @override_switch('use_company_name_as_utm_source_value', active=False)
    def test_with_waffle_switch_turned_off(self):
        """
        Verify that `get_utm_source_for_user` returns User's username when waffle switch
        `use_company_name_as_utm_source_value` is turned off.
        """

        assert get_utm_source_for_user(self.partner, self.user) == self.user.username

    def test_with_missing_lms_url(self):
        """
        Verify that `get_utm_source_for_user` returns default value if
        `Partner.lms_url` is not set in the database.
        """
        assert get_utm_source_for_user(self.partner, self.user) == self.user.username

    @responses.activate
    def test_when_api_response_is_not_valid(self):
        """
        Verify that `get_utm_source_for_user` returns default value if
        LMS API does not return a valid response.
        """
        self.partner.lms_url = 'http://127.0.0.1:8000'
        self.mock_api_access_request(self.partner.lms_url, self.user, status=400)
        assert get_utm_source_for_user(self.partner, self.user) == self.user.username

    @responses.activate
    def test_get_utm_source_for_user(self):
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


class CourseRecommendationSerializerTests(MinimalCourseSerializerTests):
    serializer_class = CourseRecommendationSerializer

    @classmethod
    def get_expected_data(cls, course, course_skill, request):
        context = {'request': request}

        return {
            'key': course.key,
            'uuid': str(course.uuid),
            'title': course.title,
            'owners': MinimalOrganizationSerializer(course.authoring_organizations, many=True, context=context).data,
            'image': ImageField().to_representation(course.image_url),
            'short_description': course.short_description,
            'type': course.type.uuid,
            'url_slug': None,
            'course_run_keys': [course_run.key for course_run in course.course_runs.all()],
            'marketing_url': '{url}?{params}'.format(
                url=course.marketing_url,
                params=urlencode({
                    'utm_source': request.user.username,
                    'utm_medium': request.user.referral_tracking_id,
                })
            ),
        }

    def test_exclude_utm(self):
        request = make_request()
        course = CourseFactory()
        serializer = self.serializer_class(course, context={'request': request, 'exclude_utm': 1})

        assert serializer.data['marketing_url'] == course.marketing_url


class CourseWithRecommendationSerializerTests(MinimalCourseSerializerTests):
    serializer_class = CourseWithRecommendationsSerializer

    @classmethod
    def get_expected_data(cls, course, course_skill, request):
        return {
            'uuid': str(course.uuid),
            'recommendations': [],
        }

    def test_course_with_recommendations(self):
        self.maxDiff = None
        request = make_request()
        context = {'request': request}
        organization = OrganizationFactory(partner=self.partner)
        subject = SubjectFactory(partner=self.partner)
        course_with_recs = CourseFactory(authoring_organizations=[organization], subjects=[subject],
                                         partner=self.partner)
        recommended_course_0 = CourseFactory(partner=self.partner)
        recommended_course_1 = CourseFactory(authoring_organizations=[organization], subjects=[subject],
                                             partner=self.partner)
        course_run_0 = CourseRunFactory.create_batch(2, course=recommended_course_0)[0]
        SeatFactory.create_batch(2, course_run=course_run_0)

        course_run_1 = CourseRunFactory.create_batch(2, course=recommended_course_1)[0]
        SeatFactory.create_batch(2, course_run=course_run_1)

        ProgramFactory(courses=[course_with_recs, recommended_course_0], partner=self.partner)

        expected_data = {
            'uuid': str(course_with_recs.uuid),
            'recommendations': CourseRecommendationSerializer([recommended_course_0, recommended_course_1], many=True,
                                                              context=context).data
        }
        serializer = self.serializer_class(course_with_recs, context={'request': request})
        assert serializer.data == expected_data

    def test_exclude_utm(self):
        request = make_request()
        organization = OrganizationFactory(partner=self.partner)
        subject = SubjectFactory(partner=self.partner)
        course_with_recs = CourseFactory(authoring_organizations=[organization], subjects=[subject],
                                         partner=self.partner)
        recommended_course_0 = CourseFactory(authoring_organizations=[organization], subjects=[subject],
                                             partner=self.partner)
        for course_run in CourseRunFactory.create_batch(2, course=recommended_course_0):
            SeatFactory.create_batch(2, course_run=course_run)
        serializer = self.serializer_class(course_with_recs, context={'request': request, 'exclude_utm': 1})
        assert serializer.data['recommendations'][0]['marketing_url'] == recommended_course_0.marketing_url


class LocationRestrictionSerializerTests(TestCase):
    def test_course_data(self):
        request = make_request()
        location_restriction = CourseLocationRestrictionFactory()
        course = CourseFactory(location_restriction=location_restriction)
        serializer = CourseSerializer(course, context={'request': request})
        expected = {
            'restriction_type': location_restriction.restriction_type,
            'countries': location_restriction.countries,
            'states': location_restriction.states
        }
        assert serializer.data['location_restriction'] == expected

    def test_program_data(self):
        request = make_request()
        program = ProgramFactory(location_restriction=None)
        location_restriction = ProgramLocationRestrictionFactory(program=program)
        serializer = ProgramSerializer(program, context={'request': request})
        expected = {
            'restriction_type': location_restriction.restriction_type,
            'countries': location_restriction.countries,
            'states': location_restriction.states
        }
        assert serializer.data['location_restriction'] == expected

    def test_null_fields(self):
        request = make_request()
        location_restriction = CourseLocationRestrictionFactory()
        course = CourseFactory(location_restriction=location_restriction)
        data = {
            'location_restriction': {
                'restriction_type': None,
                'countries': None,
                'states': None,
            },
        }
        serializer = CourseSerializer(course, context={'request': request}, data=data)
        serializer.is_valid()
        assert 'location_restriction' not in serializer.errors

    def test_no_restriction_type(self):
        request = make_request()
        data = {
            'location_restriction': {
                'restriction_type': None,
                'countries': ['CA'],
                'states': ['MI'],
            }
        }
        location_restriction = CourseLocationRestrictionFactory()
        course = CourseFactory(location_restriction=location_restriction)
        serializer = CourseSerializer(course, context={'request': request}, data=data)
        serializer.is_valid()
        assert 'location_restriction' in serializer.errors
        assert 'Restriction Type' in serializer.errors['location_restriction']

    def test_no_countries(self):
        request = make_request()
        data = {
            'location_restriction': {
                'restriction_type': 'allowlist',
                'countries': None,
                'states': ['MI'],
            }
        }
        location_restriction = CourseLocationRestrictionFactory()
        course = CourseFactory(location_restriction=location_restriction)
        serializer = CourseSerializer(course, context={'request': request}, data=data)
        serializer.is_valid()
        assert 'location_restriction' not in serializer.errors

    def test_no_states(self):
        request = make_request()
        data = {
            'location_restriction': {
                'restriction_type': 'allowlist',
                'countries': ['CA'],
                'states': None,
            }
        }
        location_restriction = CourseLocationRestrictionFactory()
        course = CourseFactory(location_restriction=location_restriction)
        serializer = CourseSerializer(course, context={'request': request}, data=data)
        serializer.is_valid()
        assert 'location_restriction' not in serializer.errors

    def test_no_countries_or_states(self):
        request = make_request()
        data = {
            'location_restriction': {
                'restriction_type': 'allowlist',
                'countries': None,
                'states': None,
            }
        }
        location_restriction = CourseLocationRestrictionFactory()
        course = CourseFactory(location_restriction=location_restriction)
        serializer = CourseSerializer(course, context={'request': request}, data=data)
        serializer.is_valid()
        assert 'location_restriction' not in serializer.errors

    def test_invalid_codes(self):
        request = make_request()
        course = CourseFactory()
        invalid_data = {
            'location_restriction': {
                'restriction_type': AbstractLocationRestrictionModel.ALLOWLIST,
                'countries': ['ABC', 'XX'],
                'states': ['AB']
            }
        }
        serializer = CourseSerializer(course, context={'request': request}, data=invalid_data)
        serializer.is_valid()

        assert serializer.errors['location_restriction']


class CourseReviewSerializerTests(TestCase):
    def setUp(self):
        self.data = {
            'course_key': 'CS101',
            'reviews_count': 10,
            'avg_course_rating': 4.500001,
            'confident_learners_percentage': 80.012345,
            'most_common_goal': CourseReview.CHANGE_CAREERS,
            'most_common_goal_learners_percentage': 50.012345,
            'total_enrollments': 1000,
        }

    def test_valid_data(self):
        serializer = CourseReviewSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.data['course_key'], 'CS101')
        self.assertEqual(serializer.data['reviews_count'], 10)
        self.assertEqual(serializer.data['avg_course_rating'], '4.500001')
        self.assertEqual(serializer.data['confident_learners_percentage'], '80.012345')
        self.assertEqual(serializer.data['most_common_goal'], CourseReview.CHANGE_CAREERS)
        self.assertEqual(serializer.data['most_common_goal_learners_percentage'], '50.012345')
        self.assertEqual(serializer.data['total_enrollments'], 1000)

    def test_required_fields(self):
        required_fields = ['course_key', 'most_common_goal']
        for field in required_fields:
            data = self.data.copy()
            data.pop(field)
            serializer = CourseReviewSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertIn(field, serializer.errors)

    def test_decimal_fields(self):
        decimal_fields = ['avg_course_rating', 'confident_learners_percentage', 'most_common_goal_learners_percentage']
        for field in decimal_fields:
            data = self.data.copy()
            data[field] = 'invalid'
            serializer = CourseReviewSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertIn(field, serializer.errors)
