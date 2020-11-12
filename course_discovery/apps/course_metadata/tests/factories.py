from datetime import datetime

import factory
from django.db.models.signals import post_save
from factory.fuzzy import FuzzyChoice, FuzzyDateTime, FuzzyDecimal, FuzzyInteger, FuzzyText
from pytz import UTC

from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory, add_m2m_data
from course_discovery.apps.core.tests.utils import FuzzyURL
from course_discovery.apps.course_metadata.models import *  # pylint: disable=wildcard-import
from course_discovery.apps.ietf_language_tags.models import LanguageTag

# pylint: disable=unused-argument


class AbstractMediaModelFactory(factory.django.DjangoModelFactory):
    src = FuzzyURL()
    description = FuzzyText()


class AbstractNamedModelFactory(factory.django.DjangoModelFactory):
    name = FuzzyText()


class AbstractTitleDescriptionFactory(factory.django.DjangoModelFactory):
    title = FuzzyText(length=255)
    description = FuzzyText()


class ImageFactory(AbstractMediaModelFactory):
    height = 100
    width = 100

    class Meta:
        model = Image


class VideoFactory(AbstractMediaModelFactory):
    image = factory.SubFactory(ImageFactory)

    class Meta:
        model = Video


class SubjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subject

    name = FuzzyText()
    description = FuzzyText()
    banner_image_url = FuzzyURL()
    card_image_url = FuzzyURL()
    partner = factory.SubFactory(PartnerFactory)
    uuid = factory.LazyFunction(uuid4)


class TopicFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Topic

    name = FuzzyText()
    description = FuzzyText()
    long_description = FuzzyText()
    banner_image_url = FuzzyURL()
    partner = factory.SubFactory(PartnerFactory)
    uuid = factory.LazyFunction(uuid4)


class LevelTypeFactory(AbstractNamedModelFactory):
    name_t = FuzzyText()

    class Meta:
        model = LevelType


class PrerequisiteFactory(AbstractNamedModelFactory):
    class Meta:
        model = Prerequisite


class AdditionalPromoAreaFactory(AbstractTitleDescriptionFactory):
    class Meta:
        model = AdditionalPromoArea


class SalesforceRecordFactory(factory.django.DjangoModelFactory):
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        from course_discovery.apps.course_metadata.tests.utils import build_salesforce_exception  # pylint: disable=import-outside-toplevel
        try:
            return super()._create(model_class, *args, **kwargs)
        except requests.ConnectionError:
            # raise user friendly suggestion to use factory with muted signals
            raise ConnectionError(build_salesforce_exception(model_class.__name__))


class SeatTypeFactory(factory.django.DjangoModelFactory):
    name = FuzzyText()

    class Meta:
        model = SeatType

    @staticmethod
    def audit():
        return SeatType.objects.get(slug=Seat.AUDIT)

    @staticmethod
    def credit():
        return SeatType.objects.get(slug=Seat.CREDIT)

    @classmethod
    def honor(cls):
        return SeatType.objects.get_or_create(name=Seat.HONOR.capitalize())[0]  # name will create slug

    @classmethod
    def masters(cls):
        return SeatType.objects.get_or_create(name=Seat.MASTERS.capitalize())[0]  # name will create slug

    @staticmethod
    def professional():
        return SeatType.objects.get(slug=Seat.PROFESSIONAL)

    @staticmethod
    def verified():
        return SeatType.objects.get(slug=Seat.VERIFIED)


class ModeFactory(factory.django.DjangoModelFactory):
    name = FuzzyText()
    slug = FuzzyText()

    class Meta:
        model = Mode


class TrackFactory(factory.django.DjangoModelFactory):
    mode = factory.SubFactory(ModeFactory)
    seat_type = factory.SubFactory(SeatTypeFactory)

    class Meta:
        model = Track


class CourseRunTypeFactory(factory.django.DjangoModelFactory):
    uuid = factory.LazyFunction(uuid4)
    name = FuzzyText()
    slug = FuzzyText()
    is_marketable = True

    class Meta:
        model = CourseRunType

    @factory.post_generation
    def tracks(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.tracks, extracted)


class CourseTypeFactory(factory.django.DjangoModelFactory):
    uuid = factory.LazyFunction(uuid4)
    name = FuzzyText()
    slug = FuzzyText()

    class Meta:
        model = CourseType

    @factory.post_generation
    def entitlement_types(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.entitlement_types, extracted)

    @factory.post_generation
    def course_run_types(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.course_run_types, extracted)


class CourseFactory(SalesforceRecordFactory):
    uuid = factory.LazyFunction(uuid4)
    key = FuzzyText(prefix='course-id/')
    key_for_reruns = FuzzyText(prefix='OrgX+')
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
    canonical_course_run = None
    extra_description = factory.SubFactory(AdditionalPromoAreaFactory)
    additional_information = FuzzyText()
    faq = FuzzyText()
    learner_testimonials = FuzzyText()
    type = factory.SubFactory(CourseTypeFactory)

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

    @factory.post_generation
    def url_slug_history(self, create, extracted, **kwargs):
        if create:
            data = {'is_active': True, 'is_active_on_draft': True, 'course': self, 'partner': self.partner}
            if extracted:
                data.update(extracted)
            CourseUrlSlugFactory(**data)


class CourseUrlSlugFactory(factory.django.DjangoModelFactory):
    course = factory.SubFactory(CourseFactory)
    partner = factory.SelfAttribute('course.partner')
    url_slug = FuzzyText()

    class Meta:
        model = CourseUrlSlug


class CourseUrlRedirectFactory(factory.django.DjangoModelFactory):
    course = factory.SubFactory(CourseFactory)
    partner = factory.SelfAttribute('course.partner')
    value = FuzzyText()

    class Meta:
        model = CourseUrlRedirect


@factory.django.mute_signals(post_save)
class CourseFactoryNoSignals(CourseFactory):
    pass


class CourseEditorFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    course = factory.SubFactory(CourseFactory)

    class Meta:
        model = CourseEditor


class CourseRunFactory(SalesforceRecordFactory):
    status = CourseRunStatus.Published
    uuid = factory.LazyFunction(uuid4)
    key = FuzzyText(prefix='course-run-id/', suffix='/fake')
    external_key = None
    course = factory.SubFactory(CourseFactory)
    title_override = None
    short_description_override = None
    full_description_override = None
    language = factory.Iterator(LanguageTag.objects.all())
    start = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    end = FuzzyDateTime(datetime.datetime.now(tz=UTC), datetime.datetime(2030, 1, 1, tzinfo=UTC))
    go_live_date = None
    enrollment_start = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    enrollment_end = FuzzyDateTime(datetime.datetime.now(tz=UTC), datetime.datetime(2029, 1, 1, tzinfo=UTC))
    announcement = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    card_image_url = FuzzyURL()
    video = factory.SubFactory(VideoFactory)
    min_effort = FuzzyInteger(1, 9)
    max_effort = FuzzyInteger(10, 20)
    pacing_type = FuzzyChoice([name for name, __ in CourseRunPacing.choices])
    reporting_type = FuzzyChoice([name for name, __ in ReportingType.choices])
    hidden = False
    weeks_to_complete = FuzzyInteger(1)
    license = 'all-rights-reserved'
    has_ofac_restrictions = True
    type = factory.SubFactory(CourseRunTypeFactory)

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


@factory.django.mute_signals(post_save)
class CourseRunFactoryNoSignals(CourseRunFactory):
    pass


class SeatFactory(factory.django.DjangoModelFactory):
    type = factory.SubFactory(SeatTypeFactory)
    price = FuzzyDecimal(0.0, 650.0)
    currency = factory.Iterator(Currency.objects.all())
    upgrade_deadline = FuzzyDateTime(datetime.datetime(2014, 1, 1, tzinfo=UTC))
    sku = FuzzyText(length=8)
    bulk_sku = FuzzyText(length=8)
    course_run = factory.SubFactory(CourseRunFactory)

    class Meta:
        model = Seat


class CourseEntitlementFactory(factory.django.DjangoModelFactory):
    mode = factory.SubFactory(SeatTypeFactory)
    price = FuzzyDecimal(0.0, 650.0)
    currency = factory.Iterator(Currency.objects.all())
    sku = FuzzyText(length=8)
    course = factory.SubFactory(CourseFactory)

    class Meta:
        model = CourseEntitlement


class OrganizationFactory(SalesforceRecordFactory):
    uuid = factory.LazyFunction(uuid4)
    key = FuzzyText()
    name = FuzzyText()
    description = FuzzyText()
    homepage_url = FuzzyURL()
    logo_image = FuzzyText()
    banner_image = FuzzyText()
    certificate_logo_image = FuzzyText()
    partner = factory.SubFactory(PartnerFactory)

    class Meta:
        model = Organization


@factory.django.mute_signals(post_save)
class OrganizationFactoryNoSignals(OrganizationFactory):
    pass


class PersonFactory(factory.django.DjangoModelFactory):
    uuid = factory.LazyFunction(uuid4)
    partner = factory.SubFactory(PartnerFactory)
    given_name = factory.Faker('first_name')
    family_name = factory.Faker('last_name')
    bio = FuzzyText()
    profile_image = FuzzyText(prefix='person/profile_image')
    major_works = FuzzyText()
    published = True

    class Meta:
        model = Person


class PositionFactory(factory.django.DjangoModelFactory):
    person = factory.SubFactory(PersonFactory)
    title = FuzzyText()
    organization = factory.SubFactory(OrganizationFactory)

    class Meta:
        model = Position


class ProgramTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProgramType

    uuid = factory.LazyFunction(uuid4)
    name = FuzzyText()
    name_t = FuzzyText()
    logo_image = FuzzyText(prefix='https://example.com/program/logo')
    slug = FuzzyText()

    @factory.post_generation
    def applicable_seat_types(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.applicable_seat_types, extracted)


class EndorsementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Endorsement

    endorser = factory.SubFactory(PersonFactory)
    quote = FuzzyText()


class CorporateEndorsementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CorporateEndorsement

    corporation_name = FuzzyText()
    statement = FuzzyText()
    image = factory.SubFactory(ImageFactory)

    @factory.post_generation
    def individual_endorsements(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.individual_endorsements, extracted)


class JobOutlookItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = JobOutlookItem

    value = FuzzyText()


class FAQFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FAQ

    question = FuzzyText()
    answer = FuzzyText()


class ExpectedLearningItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ExpectedLearningItem

    value = FuzzyText()


class RankingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Ranking

    rank = FuzzyText(length=9)
    description = FuzzyText(length=255)
    source = FuzzyText(length=99)


class ProgramFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Program

    title = factory.Sequence(lambda n: 'test-program-{}'.format(n))  # pylint: disable=unnecessary-lambda
    uuid = factory.LazyFunction(uuid4)
    subtitle = FuzzyText()
    marketing_hook = FuzzyText()
    type = factory.SubFactory(ProgramTypeFactory)
    status = ProgramStatus.Active
    marketing_slug = factory.Sequence(lambda n: 'test-slug-{}'.format(n))  # pylint: disable=unnecessary-lambda
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

    @factory.post_generation
    def curricula(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.curricula, extracted)


class DegreeFactory(ProgramFactory):
    class Meta:
        model = Degree

    apply_url = FuzzyURL()
    overall_ranking = FuzzyText()
    lead_capture_list_name = FuzzyText()
    application_requirements = FuzzyText()
    prerequisite_coursework = FuzzyText()
    micromasters_url = FuzzyText()
    micromasters_long_title = FuzzyText()
    micromasters_long_description = FuzzyText()
    micromasters_org_name_override = FuzzyText()
    search_card_ranking = FuzzyText()
    search_card_cost = FuzzyText()
    search_card_courses = FuzzyText()
    banner_border_color = FuzzyText(length=6)

    @factory.post_generation
    def rankings(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.rankings, extracted)


class IconTextPairingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IconTextPairing

    degree = factory.SubFactory(DegreeFactory)
    icon = FuzzyText(length=25)
    text = FuzzyText(length=255)


class CurriculumFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Curriculum

    name = FuzzyText()
    uuid = factory.LazyFunction(uuid4)
    marketing_text_brief = FuzzyText()
    marketing_text = FuzzyText()
    program = factory.SubFactory(ProgramFactory)

    @factory.post_generation
    def program_curriculum(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.program_curriculum, extracted)

    @factory.post_generation
    def course_curriculum(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.course_curriculum, extracted)


class DegreeDeadlineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DegreeDeadline

    degree = factory.SubFactory(DegreeFactory)
    semester = FuzzyText()
    name = FuzzyText()
    date = FuzzyText()
    time = FuzzyText()


class DegreeCostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DegreeCost

    degree = factory.SubFactory(DegreeFactory)
    description = FuzzyText()
    amount = FuzzyText()


class CurriculumProgramMembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CurriculumProgramMembership

    program = factory.SubFactory(ProgramFactory)
    curriculum = factory.SubFactory(CurriculumFactory)


class CurriculumCourseMembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CurriculumCourseMembership

    course = factory.SubFactory(CourseFactory)
    curriculum = factory.SubFactory(CurriculumFactory)

    @factory.post_generation
    def course_curriculum(self, create, extracted, **kwargs):
        if create:  # pragma: no cover
            add_m2m_data(self.course_run_exclusions, extracted)


class CurriculumCourseRunExclusionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CurriculumCourseRunExclusion

    course_membership = factory.SubFactory(CurriculumCourseMembershipFactory)
    course_run = factory.SubFactory(CourseRunFactory)


class PathwayFactory(factory.django.DjangoModelFactory):
    uuid = factory.LazyFunction(uuid4)
    partner = factory.SubFactory(PartnerFactory)
    name = FuzzyText()
    org_name = FuzzyText()
    email = factory.Sequence(lambda n: 'test-email-{}@test.com'.format(n))  # pylint: disable=unnecessary-lambda
    description = FuzzyText()
    destination_url = FuzzyURL()
    pathway_type = FuzzyChoice((path_type.value for path_type in PathwayType))

    class Meta:
        model = Pathway


class PersonSocialNetworkFactory(factory.django.DjangoModelFactory):
    type = FuzzyChoice(PersonSocialNetwork.SOCIAL_NETWORK_CHOICES.keys())
    url = FuzzyText()
    title = FuzzyText()
    person = factory.SubFactory(PersonFactory)

    class Meta:
        model = PersonSocialNetwork


class PersonAreaOfExpertiseFactory(factory.django.DjangoModelFactory):
    value = FuzzyText()
    person = factory.SubFactory(PersonFactory)

    class Meta:
        model = PersonAreaOfExpertise


class SyllabusItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SyllabusItem


class DrupalPublishUuidConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DrupalPublishUuidConfig


class ProfileImageDownloadConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProfileImageDownloadConfig


class MigratePublisherToCourseMetadataConfigFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MigratePublisherToCourseMetadataConfig


class MigrateCommentsToSalesforceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MigrateCommentsToSalesforce


class CollaboratorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Collaborator

    name = FuzzyText()
    image = factory.django.ImageField()
    uuid = factory.LazyFunction(uuid4)
