import urllib.parse

import pytest
from django.test import RequestFactory
from django.urls import reverse

from course_discovery.apps.api.serializers import MinimalProgramSerializer
from course_discovery.apps.api.v1.tests.test_views.mixins import FuzzyInt, SerializationMixin
from course_discovery.apps.api.v1.views.programs import ProgramViewSet
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.tests.factories import (
    CorporateEndorsementFactory, CourseFactory, CourseRunFactory, CurriculumCourseMembershipFactory, CurriculumFactory,
    CurriculumProgramMembershipFactory, EndorsementFactory, ExpectedLearningItemFactory, JobOutlookItemFactory,
    OrganizationFactory, PersonFactory, ProgramFactory, VideoFactory
)


@pytest.mark.django_db
@pytest.mark.usefixtures('django_cache')
class TestProgramViewSet(SerializationMixin):
    client = None
    django_assert_num_queries = None
    list_path = reverse('api:v1:program-list')
    partner = None
    request = None

    @pytest.fixture(autouse=True)
    def setup(self, client, django_assert_num_queries, partner):
        user = UserFactory(is_staff=True, is_superuser=True)

        client.login(username=user.username, password=USER_PASSWORD)

        site = partner.site
        request = RequestFactory(SERVER_NAME=site.domain).get('')
        request.site = site
        request.user = user

        self.client = client
        self.django_assert_num_queries = django_assert_num_queries
        self.partner = partner
        self.request = request

    def create_program(self, courses=None):
        organizations = [OrganizationFactory(partner=self.partner)]
        person = PersonFactory()

        if courses is None:
            courses = [CourseFactory(partner=self.partner)]
            CourseRunFactory(course=courses[0], staff=[person])

        program = ProgramFactory(
            courses=courses,
            authoring_organizations=organizations,
            credit_backing_organizations=organizations,
            corporate_endorsements=CorporateEndorsementFactory.create_batch(1),
            individual_endorsements=EndorsementFactory.create_batch(1),
            expected_learning_items=ExpectedLearningItemFactory.create_batch(1),
            job_outlook_items=JobOutlookItemFactory.create_batch(1),
            instructor_ordering=PersonFactory.create_batch(1),
            banner_image=make_image_file('test_banner.jpg'),
            video=VideoFactory(),
            partner=self.partner
        )
        return program

    def create_curriculum(self, parent_program):
        person = PersonFactory()
        course = CourseFactory(partner=self.partner)
        CourseRunFactory(course=course, staff=[person])
        CourseRunFactory(course=course, staff=[person])

        curriculum = CurriculumFactory(
            program=parent_program
        )
        CurriculumCourseMembershipFactory(
            course=course,
            curriculum=curriculum
        )
        return curriculum

    def assert_retrieve_success(self, program, querystring=None):
        """ Verify the retrieve endpoint succesfully returns a serialized program. """
        url = reverse('api:v1:program-detail', kwargs={'uuid': program.uuid})

        if querystring:
            url += '?' + urllib.parse.urlencode(querystring)

        response = self.client.get(url)
        assert response.status_code == 200
        return response

    def test_authentication(self):
        """ Verify the endpoint requires the user to be authenticated. """
        response = self.client.get(self.list_path)
        assert response.status_code == 200

        self.client.logout()
        response = self.client.get(self.list_path)
        assert response.status_code == 401

    def test_retrieve(self, django_assert_num_queries):
        """ Verify the endpoint returns the details for a single program. """
        program = self.create_program()

        with django_assert_num_queries(FuzzyInt(57, 2)):
            response = self.assert_retrieve_success(program)
        # property does not have the right values while being indexed
        del program._course_run_weeks_to_complete
        assert response.data == self.serialize_program(program)

        # Verify that requests including querystring parameters are cached separately.
        response = self.assert_retrieve_success(program, querystring={'use_full_course_serializer': 1})
        assert response.data == self.serialize_program(program, extra_context={'use_full_course_serializer': 1})

    def test_retrieve_basic_curriculum(self, django_assert_num_queries):
        program = self.create_program(courses=[])
        self.create_curriculum(program)

        # Notes on this query count:
        # 37 queries to get program without a curriculum and no courses
        # +2 for curriculum details (related courses, related programs)
        # +8 for course details on 1 or more courses across all sibling curricula
        with django_assert_num_queries(47):
            response = self.assert_retrieve_success(program)
        assert response.data == self.serialize_program(program)

    def test_retrieve_curriculum_with_child_programs(self, django_assert_num_queries):
        parent_program = self.create_program(courses=[])
        curriculum = self.create_curriculum(parent_program)

        child_program1 = self.create_program()
        child_program2 = self.create_program()
        CurriculumProgramMembershipFactory(
            program=child_program1,
            curriculum=curriculum
        )
        CurriculumProgramMembershipFactory(
            program=child_program2,
            curriculum=curriculum
        )

        with django_assert_num_queries(FuzzyInt(63, 2)):
            response = self.assert_retrieve_success(parent_program)
        assert response.data == self.serialize_program(parent_program)

    @pytest.mark.parametrize('order_courses_by_start_date', (True, False,))
    def test_retrieve_with_sorting_flag(self, order_courses_by_start_date, django_assert_num_queries):
        """ Verify the number of queries is the same with sorting flag set to true. """
        course_list = CourseFactory.create_batch(3, partner=self.partner)
        for course in course_list:
            CourseRunFactory(course=course)
        program = ProgramFactory(
            courses=course_list,
            order_courses_by_start_date=order_courses_by_start_date,
            partner=self.partner)
        # property does not have the right values while being indexed
        del program._course_run_weeks_to_complete
        with django_assert_num_queries(FuzzyInt(40, 1)):  # CI is often 41
            response = self.assert_retrieve_success(program)
        assert response.data == self.serialize_program(program)
        assert course_list == list(program.courses.all())

    def test_retrieve_without_course_runs(self, django_assert_num_queries):
        """ Verify the endpoint returns data for a program even if the program's courses have no course runs. """
        course = CourseFactory(partner=self.partner)
        program = ProgramFactory(courses=[course], partner=self.partner)
        with django_assert_num_queries(FuzzyInt(32, 2)):
            response = self.assert_retrieve_success(program)
        assert response.data == self.serialize_program(program)

    def assert_list_results(self, url, expected, expected_query_count, extra_context=None):
        """
        Asserts the results serialized/returned at the URL matches those that are expected.
        Args:
            url (str): URL from which data should be retrieved
            expected (list[Program]): Expected programs

        Notes:
            The API usually returns items in reverse order of creation (e.g. newest first). You may need to reverse
            the values of `expected` if you encounter issues. This method will NOT do that reversal for you.

        Returns:
            None
        """
        with self.django_assert_num_queries(FuzzyInt(expected_query_count, 2)):
            response = self.client.get(url)

        assert response.data['results'] == self.serialize_program(expected, many=True, extra_context=extra_context)

    def test_list(self):
        """ Verify the endpoint returns a list of all programs. """
        expected = [self.create_program() for __ in range(3)]

        self.assert_list_results(self.list_path, expected, 19)

    def test_uuids_only(self):
        """
        Verify that the list view returns a simply list of UUIDs when the
        uuids_only query parameter is passed.
        """
        active = ProgramFactory.create_batch(3, partner=self.partner)
        retired = [ProgramFactory(status=ProgramStatus.Retired, partner=self.partner)]
        programs = active + retired

        querystring = {'uuids_only': 1}
        url = '{base}?{query}'.format(base=self.list_path, query=urllib.parse.urlencode(querystring))
        response = self.client.get(url)

        assert set(response.data) == {program.uuid for program in programs}

        # Verify that filtering (e.g., by status) is still supported.
        querystring['status'] = ProgramStatus.Retired
        url = '{base}?{query}'.format(base=self.list_path, query=urllib.parse.urlencode(querystring))
        response = self.client.get(url)

        assert set(response.data) == {program.uuid for program in retired}

    def test_filter_by_type(self):
        """ Verify that the endpoint filters programs to those of a given type. """
        program_type_name = 'foo'
        program = ProgramFactory(type__name_t=program_type_name, partner=self.partner)
        url = self.list_path + '?type=' + program_type_name
        self.assert_list_results(url, [program], 12)

        url = self.list_path + '?type=bar'
        self.assert_list_results(url, [], 5)

    def test_filter_by_types(self):
        """ Verify that the endpoint filters programs to those matching the provided ProgramType slugs. """
        expected = ProgramFactory.create_batch(2, partner=self.partner)
        type_slugs = [p.type.slug for p in expected]
        url = self.list_path + '?types=' + ','.join(type_slugs)

        # Create a third program, which should be filtered out.
        ProgramFactory(partner=self.partner)

        self.assert_list_results(url, expected, 14)

    def test_filter_by_uuids(self):
        """ Verify that the endpoint filters programs to those matching the provided UUIDs. """
        expected = ProgramFactory.create_batch(2, partner=self.partner)
        uuids = [str(p.uuid) for p in expected]
        url = self.list_path + '?uuids=' + ','.join(uuids)

        # Create a third program, which should be filtered out.
        ProgramFactory(partner=self.partner)

        self.assert_list_results(url, expected, 14)

    @pytest.mark.parametrize(
        'status,is_marketable,expected_query_count',
        (
            (ProgramStatus.Unpublished, False, 5),
            (ProgramStatus.Active, True, 14),
        )
    )
    def test_filter_by_marketable(self, status, is_marketable, expected_query_count):
        """ Verify the endpoint filters programs to those that are marketable. """
        url = self.list_path + '?marketable=1'
        ProgramFactory(marketing_slug='', partner=self.partner)
        programs = ProgramFactory.create_batch(3, status=status, partner=self.partner)

        expected = programs if is_marketable else []
        assert list(Program.objects.marketable()) == expected
        self.assert_list_results(url, expected, expected_query_count)

    def test_filter_by_status(self):
        """ Verify the endpoint allows programs to filtered by one, or more, statuses. """
        active = ProgramFactory(status=ProgramStatus.Active, partner=self.partner)
        retired = ProgramFactory(status=ProgramStatus.Retired, partner=self.partner)

        url = self.list_path + '?status=active'
        self.assert_list_results(url, [active], 12)

        url = self.list_path + '?status=retired'
        self.assert_list_results(url, [retired], 12)

        url = self.list_path + '?status=active&status=retired'
        self.assert_list_results(url, [active, retired], 14)

    def test_filter_by_hidden(self):
        """ Endpoint should filter programs by their hidden attribute value. """
        hidden = ProgramFactory(hidden=True, partner=self.partner)
        not_hidden = ProgramFactory(hidden=False, partner=self.partner)

        url = self.list_path + '?hidden=True'
        self.assert_list_results(url, [hidden], 12)

        url = self.list_path + '?hidden=False'
        self.assert_list_results(url, [not_hidden], 12)

        url = self.list_path + '?hidden=1'
        self.assert_list_results(url, [hidden], 12)

        url = self.list_path + '?hidden=0'
        self.assert_list_results(url, [not_hidden], 12)

    def test_filter_by_marketing_slug(self):
        """ The endpoint should support filtering programs by marketing slug. """
        SLUG = 'test-program'

        # This program should not be included in the results below because it never matches the filter.
        self.create_program()

        url = f'{self.list_path}?marketing_slug={SLUG}'
        self.assert_list_results(url, [], 5)

        program = self.create_program()
        program.marketing_slug = SLUG
        program.save()

        self.assert_list_results(url, [program], 19)

    def test_list_exclude_utm(self):
        """ Verify the endpoint returns marketing URLs without UTM parameters. """
        url = self.list_path + '?exclude_utm=1'
        program = self.create_program()
        self.assert_list_results(url, [program], 18, extra_context={'exclude_utm': 1})

    def test_minimal_serializer_use(self):
        """ Verify that the list view uses the minimal serializer. """
        assert ProgramViewSet(action='list').get_serializer_class() == MinimalProgramSerializer

    def test_update_card_image(self):
        program = self.create_program()
        image_dict = {
            'image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY'
                     '42YAAAAASUVORK5CYII=',
        }
        update_url = reverse('api:v1:program-update-card-image', kwargs={'uuid': program.uuid})
        response = self.client.post(update_url, image_dict, format='json')
        assert response.status_code == 200

    def test_update_card_image_authentication(self):
        program = self.create_program()
        self.client.logout()
        image_dict = {
            'image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY'
                     '42YAAAAASUVORK5CYII=',
        }
        update_url = reverse('api:v1:program-update-card-image', kwargs={'uuid': program.uuid})
        response = self.client.post(update_url, image_dict, format='json')
        assert response.status_code == 401

    def test_update_card_image_authentication_notstaff(self):
        program = self.create_program()
        self.client.logout()
        user = UserFactory(is_staff=False)
        self.client.login(username=user.username, password=USER_PASSWORD)
        image_dict = {
            'image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY'
                     '42YAAAAASUVORK5CYII=',
        }
        update_url = reverse('api:v1:program-update-card-image', kwargs={'uuid': program.uuid})
        response = self.client.post(update_url, image_dict, format='json')
        assert response.status_code == 403

    def test_update_card_malformed_image(self):
        program = self.create_program()
        image_dict = {
            'image': 'ARandomString',
        }
        update_url = reverse('api:v1:program-update-card-image', kwargs={'uuid': program.uuid})
        response = self.client.post(update_url, image_dict, format='json')
        assert response.status_code == 400
