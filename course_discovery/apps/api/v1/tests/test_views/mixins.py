# pylint: disable=redefined-builtin

import json

import responses
from haystack.query import SearchQuerySet
from rest_framework.test import APIRequestFactory
from rest_framework.test import APITestCase as RestAPITestCase

from course_discovery.apps.api import serializers
from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program
from course_discovery.apps.course_metadata.tests import factories


class SerializationMixin:
    def _get_request(self, format=None):
        if getattr(self, 'request', None):
            return self.request

        query_data = {}
        if format:
            query_data['format'] = format
        request = APIRequestFactory().get('/', query_data)
        request.user = self.user
        return request

    def _serialize_object(self, serializer, obj, many=False, format=None, extra_context=None):
        context = {'request': self._get_request(format)}
        if extra_context:
            context.update(extra_context)
        return serializer(obj, many=many, context=context).data

    def _get_search_result(self, model, **kwargs):
        return SearchQuerySet().models(model).filter(**kwargs)[0]

    def serialize_catalog(self, catalog, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.CatalogSerializer, catalog, many, format, extra_context)

    def serialize_course(self, course, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.CourseWithProgramsSerializer, course, many, format, extra_context)

    def serialize_course_search(self, course, serializer=None):
        obj = self._get_search_result(Course, key=course.key)
        return self._serialize_object(serializer or serializers.CourseSearchSerializer, obj)

    def serialize_course_run(self, run, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.CourseRunWithProgramsSerializer, run, many, format, extra_context)

    def serialize_minimal_course_run(self, run, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.MinimalCourseRunSerializer, run, many, format, extra_context)

    def serialize_course_run_search(self, run, serializer=None):
        obj = self._get_search_result(CourseRun, key=run.key)
        return self._serialize_object(serializer or serializers.CourseRunSearchSerializer, obj)

    def serialize_person(self, person, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.PersonSerializer, person, many, format, extra_context)

    def serialize_program(self, program, many=False, format=None, extra_context=None):
        return self._serialize_object(
            serializers.MinimalProgramSerializer if many else serializers.ProgramSerializer,
            program,
            many,
            format,
            extra_context
        )

    def serialize_program_search(self, program, serializer=None):
        obj = self._get_search_result(Program, uuid=program.uuid)
        return self._serialize_object(serializer or serializers.ProgramSearchSerializer, obj)

    def serialize_program_type(self, program_type, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.ProgramTypeSerializer, program_type, many, format, extra_context)

    def serialize_catalog_course(self, course, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.CatalogCourseSerializer, course, many, format, extra_context)

    def serialize_catalog_flat_course_run(self, course_run, many=False, format=None, extra_context=None):
        return self._serialize_object(
            serializers.FlattenedCourseRunWithCourseSerializer, course_run, many, format, extra_context
        )

    def serialize_level_type(self, level_type, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.LevelTypeSerializer, level_type, many, format, extra_context)

    def serialize_organization(self, organization, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.OrganizationSerializer, organization, many, format, extra_context)

    def serialize_subject(self, subject, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.SubjectSerializer, subject, many, format, extra_context)

    def serialize_topic(self, topic, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.TopicSerializer, topic, many, format, extra_context)

    def serialize_pathway(self, pathway, many=False, format=None, extra_context=None):
        return self._serialize_object(serializers.PathwaySerializer, pathway, many, format, extra_context)


class TypeaheadSerializationMixin:
    def serialize_course_run_search(self, run):
        obj = SearchQuerySet().models(CourseRun).filter(key=run.key)[0]
        return serializers.TypeaheadCourseRunSearchSerializer(obj).data

    def serialize_program_search(self, program):
        obj = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        return serializers.TypeaheadProgramSearchSerializer(obj).data


class OAuth2Mixin:
    def mock_access_token(self):
        responses.add(
            responses.POST,
            self.partner.lms_url + '/oauth2/access_token',
            body=json.dumps({'access_token': 'abcd', 'expires_in': 60}),
            status=200,
        )


class SynonymTestMixin:

    def test_org_synonyms(self):
        """ Test that synonyms work for organization names """
        title = 'UniversityX'
        authoring_organizations = [factories.OrganizationFactory(name='University')]
        factories.CourseRunFactory(
            title=title,
            course__partner=self.partner,
            authoring_organizations=authoring_organizations
        )
        factories.ProgramFactory(title=title, partner=self.partner, authoring_organizations=authoring_organizations)
        response1 = self.process_response({'q': title})
        response2 = self.process_response({'q': 'University'})
        assert response1 == response2

    def test_title_synonyms(self):
        """ Test that synonyms work for terms in the title """
        factories.CourseRunFactory(title='HTML', course__partner=self.partner)
        factories.ProgramFactory(title='HTML', partner=self.partner)
        response1 = self.process_response({'q': 'HTML5'})
        response2 = self.process_response({'q': 'HTML'})
        assert response1 == response2

    def test_special_character_synonyms(self):
        """ Test that synonyms work with special characters (non ascii) """
        factories.ProgramFactory(title='spanish', partner=self.partner)
        response1 = self.process_response({'q': 'spanish'})
        response2 = self.process_response({'q': 'español'})
        assert response1 == response2

    def test_stemmed_synonyms(self):
        """ Test that synonyms work with stemming from the snowball analyzer """
        title = 'Running'
        factories.ProgramFactory(title=title, partner=self.partner)
        response1 = self.process_response({'q': 'running'})
        response2 = self.process_response({'q': 'jogging'})
        assert response1 == response2


class LoginMixin:
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        if hasattr(self, 'request'):
            self.request.user = self.user


class FuzzyInt(int):
    """
    An integer that is equal to another number as long as it is within some threshold.

    See: https://lukeplant.me.uk/blog/posts/fuzzy-testing-with-assertnumqueries/
    """
    def __new__(cls, value, threshold):
        obj = super().__new__(cls, value)
        obj.value = value
        obj.threshold = threshold
        return obj

    def __eq__(self, other):
        return (self.value - self.threshold) <= other <= (self.value + self.threshold)  # pylint: disable=no-member

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return f'FuzzyInt(value={self.value}, threshold={self.threshold})'  # pylint: disable=no-member


class APITestCase(SiteMixin, RestAPITestCase):
    # pylint: disable=keyword-arg-before-vararg, arguments-differ
    def assertNumQueries(self, num, func=None, *args, **kwargs):
        """
        Overridden method to allow a number of queries within a constant range, rather than
        an exact amount of queries.  This allows us to make changes to views and models that
        may slightly modify the query count without having to update expected counts in tests,
        while still ensuring that we don't inflate the number of queries by an order of magnitude.
        """
        return super().assertNumQueries(FuzzyInt(num, kwargs.pop('threshold', 2)), func=func, *args, **kwargs)
