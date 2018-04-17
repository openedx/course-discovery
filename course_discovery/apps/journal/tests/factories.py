import uuid

import factory
from factory.fuzzy import FuzzyDecimal, FuzzyText

from course_discovery.apps.core.tests.factories import CurrencyFactory, PartnerFactory, add_m2m_data
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.journal.models import Journal, JournalBundle


class JournalFactory(factory.DjangoModelFactory):
    uuid = uuid.uuid4()
    title = FuzzyText()
    price = FuzzyDecimal(0.0, 650.0)
    short_description = FuzzyText()
    full_description = FuzzyText()
    status = "active"
    currency = factory.SubFactory(CurrencyFactory)
    partner = factory.SubFactory(PartnerFactory)
    organization = factory.SubFactory(OrganizationFactory)

    class Meta:
        model = Journal


class JournalBundleFactory(factory.DjangoModelFactory):
    uuid = uuid.uuid4()
    title = FuzzyText()
    partner = factory.SubFactory(PartnerFactory)

    class Meta:
        model = JournalBundle

    @factory.post_generation
    def journals(self, create, extracted, **kwargs):
        # pylint: disable=unused-argument
        if create:  # pragma: no cover
            add_m2m_data(self.journals, extracted)

    @factory.post_generation
    def courses(self, create, extracted, **kwargs):
        # pylint: disable=unused-argument
        if create:  # pragma: no cover
            add_m2m_data(self.courses, extracted)

    @factory.post_generation
    def applicable_seat_types(self, create, extracted, **kwargs):
        # pylint: disable=unused-argument
        if create:  # pragma: no cover
            add_m2m_data(self.applicable_seat_types, extracted)
