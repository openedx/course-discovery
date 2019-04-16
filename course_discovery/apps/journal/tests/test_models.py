""" Tests for core models. """
from django.test import TestCase
from pytest import mark

from course_discovery.apps.journal.tests.factories import JournalBundleFactory, JournalFactory


@mark.django_db
class JournalTests(TestCase):
    """ Journal model tests. """

    def setUp(self):
        super(JournalTests, self).setUp()
        self.journal = JournalFactory()

    def test_str(self):
        self.assertTrue(self.journal, self.journal.title)


@mark.django_db
class JournalBundleTests(TestCase):
    """ JournalBundle model tests. """

    def setUp(self):
        super(JournalBundleTests, self).setUp()
        self.journal_bundle = JournalBundleFactory()

    def test_str(self):
        self.assertTrue(self.journal_bundle, self.journal_bundle.title)
