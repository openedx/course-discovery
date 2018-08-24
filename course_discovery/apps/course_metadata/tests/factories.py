
from datetime import datetime

import factory
from factory.fuzzy import FuzzyChoice, FuzzyDateTime, FuzzyDecimal, FuzzyInteger, FuzzyText
from pytz import UTC

from course_discovery.apps.core.tests.factories import PartnerFactory, add_m2m_data
from course_discovery.apps.core.tests.utils import FuzzyURL
from course_discovery.apps.course_metadata.models import *  # pylint: disable=wildcard-import
from course_discovery.apps.ietf_language_tags.models import LanguageTag


# pylint: disable=unused-argument


class AbstractMediaModelFactory(factory.DjangoModelFactory):
    src = FuzzyURL()
    description = FuzzyText()


class AbstractNamedModelFactory(factory.DjangoModelFactory):
    name = FuzzyText()


class ImageFactory(AbstractMediaModelFactory):
    height = 100
    width = 100

    class Meta:
        model = Image


class VideoFactory(AbstractMediaModelFactory):
    image = factory.SubFactory(ImageFactory)

    class Meta:
        model = Video


class SubjectFactory(factory.DjangoModelFactory):
    class Meta:
        model = Subject

    name = FuzzyText()
    description = FuzzyText()
    banner_image_url = FuzzyURL()
    card_image_url = FuzzyURL()
    partner = factory.SubFactory(PartnerFactory)
    uuid = factory.LazyFunction(uuid4)


class TopicFactory(factory.DjangoModelFactory):
    class Meta:
        model = Topic

    name = FuzzyText()
    description = FuzzyText()
    long_description = FuzzyText()
    banner_image_url = FuzzyURL()
    partner = factory.SubFactory(PartnerFactory)
    uuid = factory.LazyFunction(uuid4)


class LevelTypeFactory(AbstractNamedModelFactory):
    class Meta:
        model = LevelType


class PrerequisiteFactory(AbstractNamedModelFactory):
    class Meta:
        model = Prerequisite


class CourseFactory(factory.DjangoModelFactory):
    uuid = factory.LazyFunction(uuid4)
    key = FuzzyText(prefix='course-id/')
    title = FuzzyText(prefix="Test çօմɾʂҽ ")
    short_description = FuzzyText(prefix="Test çօմɾʂҽ short description")
    full_description = FuzzyText(prefix="Test çօմɾʂҽ FULL description")
    level_type = factory.SubFactory(LevelTypeFactory)
    card_image_url = FuzzyURL()
    video = factory.SubFactory(VideoFactory)
    partner = factory.SubFactory(PartnerFactory)
    prerequisites_raw = FuzzyText()
    syllabus_raw = FuzzyText()
    outcome = FuzzyText()
    image = factory.django.ImageField()

    class Meta:
        model = Course

    @factory.post_generation
    def subjects(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.subjects, extracted)

    @factory.post_generation
    def authoring_organizations(self, create, extracted, **kwargs):
        if create:
            add_m2m_data(self.authoring_organizations, extracted)

    @factory.post_generation
    def sponsoring_organizations(self, create, extracted, **kwargs):
        if create:
            add_m2m_data(self.sponsoring_organizations, extracted)


class CourseRunFactory(factory.DjangoModelFactory):
    status = CourseRunStatus.Published
    uuid = factory.LazyFunction(uuid4)
    key = FuzzyText(prefix='course-run-id/', suffix='/fake')
    course = factory.SubFactory(CourseFactory)
    title_override = None
    short_description_override = None
    full_description_override = None
    language = factory.Iterator(LanguageTag.objects.all())
    start = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    end = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC)).end_dt
    enrollment_start = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    enrollment_end = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC)).end_dt
    announcement = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    card_image_url = FuzzyURL()
    video = factory.SubFactory(VideoFactory)
    min_effort = FuzzyInteger(1, 10)
    max_effort = FuzzyInteger(10, 20)
    pacing_type = FuzzyChoice([name for name, __ in CourseRunPacing.choices])
    reporting_type = FuzzyChoice([name for name, __ in ReportingType.choices])
    slug = FuzzyText()
    hidden = False
    weeks_to_complete = FuzzyInteger(1)
    license = 'all-rights-reserved'

    @factory.post_generation
    def staff(self, create, extracted, **kwargs):
        if create:
            add_m2m_data(self.staff, extracted)

    class Meta:
        model = CourseRun

    @factory.post_generation
    def transcript_languages(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.transcript_languages, extracted)

    @factory.post_generation
    def authoring_organizations(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.authoring_organizations, extracted)


class SeatFactory(factory.DjangoModelFactory):
    type = FuzzyChoice([name for name, __ in Seat.SEAT_TYPE_CHOICES])
    price = FuzzyDecimal(0.0, 650.0)
    currency = factory.Iterator(Currency.objects.all())
    upgrade_deadline = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    sku = FuzzyText(length=8)
    bulk_sku = FuzzyText(length=8)
    course_run = factory.SubFactory(CourseRunFactory)

    class Meta:
        model = Seat


class OrganizationFactory(factory.DjangoModelFactory):
    uuid = factory.LazyFunction(uuid4)
    key = FuzzyText()
    name = FuzzyText()
    description = FuzzyText()
    homepage_url = FuzzyURL()
    logo_image_url = FuzzyURL()
    banner_image_url = FuzzyURL()
    certificate_logo_image_url = FuzzyURL()
    partner = factory.SubFactory(PartnerFactory)
    marketing_url_path = FuzzyText()

    class Meta:
        model = Organization


class PersonFactory(factory.DjangoModelFactory):
    uuid = factory.LazyFunction(uuid4)
    partner = factory.SubFactory(PartnerFactory)
    given_name = factory.Faker('first_name')
    family_name = factory.Faker('last_name')
    bio = FuzzyText()
    profile_image_url = FuzzyURL()
    profile_image = FuzzyText(prefix='https://example.com/person/profile_image')

    class Meta:
        model = Person


class PositionFactory(factory.DjangoModelFactory):
    person = factory.SubFactory(PersonFactory)
    title = FuzzyText()
    organization = factory.SubFactory(OrganizationFactory)

    class Meta:
        model = Position


class ProgramTypeFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = ProgramType

    name = FuzzyText()
    logo_image = FuzzyText(prefix='https://example.com/program/logo')

    @factory.post_generation
    def applicable_seat_types(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.applicable_seat_types, extracted)


class EndorsementFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = Endorsement

    endorser = factory.SubFactory(PersonFactory)
    quote = FuzzyText()


class CorporateEndorsementFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = CorporateEndorsement

    corporation_name = FuzzyText()
    statement = FuzzyText()
    image = factory.SubFactory(ImageFactory)

    @factory.post_generation
    def individual_endorsements(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.individual_endorsements, extracted)


class JobOutlookItemFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = JobOutlookItem

    value = FuzzyText()


class FAQFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = FAQ

    question = FuzzyText()
    answer = FuzzyText()


class ExpectedLearningItemFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = ExpectedLearningItem

    value = FuzzyText()


class RankingFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = Ranking

    rank = FuzzyText(length=9)
    description = FuzzyText(length=255)
    source = FuzzyText(length=99)


class ProgramFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = Program

    title = factory.Sequence(lambda n: 'test-program-{}'.format(n))  # pylint: disable=unnecessary-lambda
    uuid = factory.LazyFunction(uuid4)
    subtitle = FuzzyText()
    type = factory.SubFactory(ProgramTypeFactory)
    status = ProgramStatus.Active
    marketing_slug = factory.Sequence(lambda n: 'test-slug-{}'.format(n))  # pylint: disable=unnecessary-lambda
    banner_image_url = FuzzyText(prefix='https://example.com/program/banner')
    card_image_url = FuzzyText(prefix='https://example.com/program/card')
    partner = factory.SubFactory(PartnerFactory)
    video = factory.SubFactory(VideoFactory)
    overview = FuzzyText()
    total_hours_of_effort = FuzzyInteger(2)
    weeks_to_complete = FuzzyInteger(1)
    min_hours_effort_per_week = FuzzyInteger(2)
    max_hours_effort_per_week = FuzzyInteger(4)
    credit_redemption_overview = FuzzyText()
    order_courses_by_start_date = True
    hidden = False

    @factory.post_generation
    def courses(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.courses, extracted)

    @factory.post_generation
    def excluded_course_runs(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.excluded_course_runs, extracted)

    @factory.post_generation
    def authoring_organizations(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.authoring_organizations, extracted)

    @factory.post_generation
    def corporate_endorsements(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.corporate_endorsements, extracted)

    @factory.post_generation
    def credit_backing_organizations(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.credit_backing_organizations, extracted)

    @factory.post_generation
    def expected_learning_items(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.expected_learning_items, extracted)

    @factory.post_generation
    def faq(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.faq, extracted)

    @factory.post_generation
    def individual_endorsements(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.individual_endorsements, extracted)

    @factory.post_generation
    def job_outlook_items(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.job_outlook_items, extracted)

    @factory.post_generation
    def instructor_ordering(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.instructor_ordering, extracted)


class DegreeFactory(ProgramFactory):
    class Meta(object):
        model = Degree

    apply_url = FuzzyURL()
    overall_ranking = FuzzyText()
    lead_capture_list_name = FuzzyText()
    application_requirements = FuzzyText()
    prerequisite_coursework = FuzzyText()
    micromasters_url = FuzzyText()
    micromasters_long_title = FuzzyText()
    micromasters_long_description = FuzzyText()
    search_card_ranking = FuzzyText()
    search_card_cost = FuzzyText()
    search_card_courses = FuzzyText()

    @factory.post_generation
    def rankings(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.rankings, extracted)


class IconTextPairingFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = IconTextPairing

    degree = factory.SubFactory(DegreeFactory)
    icon = FuzzyText(length=25)
    text = FuzzyText(length=255)


class CurriculumFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = Curriculum

    uuid = factory.LazyFunction(uuid4)
    marketing_text = FuzzyText()
    degree = factory.SubFactory(DegreeFactory)

    @factory.post_generation
    def program_curriculum(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.program_curriculum, extracted)

    @factory.post_generation
    def course_curriculum(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.course_curriculum, extracted)


class DegreeDeadlineFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = DegreeDeadline

    degree = factory.SubFactory(DegreeFactory)
    semester = FuzzyText()
    name = FuzzyText()
    date = FuzzyText()
    time = FuzzyText()


class DegreeCostFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = DegreeCost

    degree = factory.SubFactory(DegreeFactory)
    description = FuzzyText()
    amount = FuzzyText()


class DegreeProgramCurriculumFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = DegreeProgramCurriculum

    program = factory.SubFactory(ProgramFactory)
    curriculum = factory.SubFactory(CurriculumFactory)


class DegreeCourseCurriculumFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = DegreeCourseCurriculum

    course = factory.SubFactory(CourseFactory)
    curriculum = factory.SubFactory(CurriculumFactory)


class PathwayFactory(factory.DjangoModelFactory):
    uuid = factory.LazyFunction(uuid4)
    partner = factory.SubFactory(PartnerFactory)
    name = FuzzyText()
    org_name = FuzzyText()
    email = factory.Sequence(lambda n: 'test-email-{}@test.com'.format(n))  # pylint: disable=unnecessary-lambda
    description = FuzzyText()
    destination_url = FuzzyURL()

    class Meta:
        model = Pathway


class AbstractSocialNetworkModelFactory(factory.DjangoModelFactory):
    type = FuzzyChoice([name for name, __ in AbstractSocialNetworkModel.SOCIAL_NETWORK_CHOICES])
    value = FuzzyText()


class PersonSocialNetworkFactory(AbstractSocialNetworkModelFactory):
    person = factory.SubFactory(PersonFactory)

    class Meta:
        model = PersonSocialNetwork


class CourseRunSocialNetworkFactory(AbstractSocialNetworkModelFactory):
    course_run = factory.SubFactory(CourseRunFactory)

    class Meta:
        model = CourseRunSocialNetwork


class SeatTypeFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = SeatType

    name = FuzzyText()


class SyllabusItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SyllabusItem


class PersonWorkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PersonWork

    person = factory.SubFactory(PersonFactory)


class CourseEntitlementFactory(factory.DjangoModelFactory):
    mode = factory.SubFactory(SeatTypeFactory)
    price = FuzzyDecimal(0.0, 650.0)
    currency = factory.Iterator(Currency.objects.all())
    sku = FuzzyText(length=8)
    expires = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    course = factory.SubFactory(CourseFactory)

    class Meta:
        model = CourseEntitlement
