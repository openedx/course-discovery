from unittest import mock

import responses

from course_discovery.apps.api.v1.tests.test_views.mixins import OAuth2Mixin
from course_discovery.apps.course_metadata.models import (
    CourseEntitlement, CourseRunStatus, CourseRunType, CourseType, ProgramType, Seat
)
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunTypeFactory, CourseTypeFactory, LevelTypeFactory, ModeFactory, OrganizationFactory,
    PartnerFactory, ProgramFactory, SeatTypeFactory, SubjectFactory, TrackFactory
)


# pylint: disable=not-callable
class DataLoaderTestMixin(OAuth2Mixin):
    loader_class = None
    partner = None

    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory(lms_url='http://127.0.0.1:8000')
        self.mock_access_token()
        with mock.patch(
            'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
            return_value={'preferred_username': 'test_username'},
        ):
            self.loader = self.loader_class(self.partner, self.api_url)

    @property
    def api_url(self):  # pragma: no cover
        raise NotImplementedError

    def assert_api_called(self, expected_num_calls, check_auth=True):
        """ Asserts the API was called with the correct number of calls, and the appropriate Authorization header. """
        assert len(responses.calls) == expected_num_calls
        if check_auth:
            # 'JWT abcd' is the default value that comes from the mock_access_token function called in setUp
            assert responses.calls[1].request.headers['Authorization'] == 'JWT abcd'

    def test_init(self):
        """ Verify the constructor sets the appropriate attributes. """
        assert self.loader.partner.short_code == self.partner.short_code


class DegreeCSVLoaderMixin:
    """
    Mixin to contain various variables and methods used for DegreeCSVDataLoader testing.
    """
    DEGREE_TITLE = 'Test Degree'
    DEGREE_SLUG = 'test-degree'

    CSV_DATA_KEYS_ORDER = [
        'identifier',
        'title',
        'card_image_url',
        'product_type',
        'organization_key',
        'slug',
        'paid_landing_page_url',
        'organic_url',
        'overview',
        'specializations',
        'courses',
        'course_level',
        'primary_subject',
        'content_language',
        'organization_logo_override',
        'organization_short_code_override',
    ]

    # TODO: update it
    MINIMAL_CSV_DATA_KEYS_ORDER = CSV_DATA_KEYS_ORDER

    BASE_EXPECTED_DEGREE_DATA = {
        'external_identifier': '123456',
        'title': 'Test Degree',
        'type': 'masters',
        'organization_key': 'edx',
        'marketing_slug': 'test-degree',
        'paid_landing_page_url': 'http://example.com/landing-page.html',
        'organic_url': 'http://example.com/organic-page.html',
        'overview': 'Test Degree Overview',
        'level_type_override': 'Intermediate',
        'primary_subject_override': 'computer-science',
        'language_override': 'English - United States',
        'organization_short_code_override': 'Org Override',
    }

    def setUp(self):
        super().setUp()
        self.program_type = ProgramType.objects.get(slug=ProgramType.MASTERS)
        self.marketing_text = "<ul><li>ABC</li><li>D&E</li><li>Harvard CS50</li></ul>"

    def _write_csv(self, csv, lines_dict_list, headers=None):
        """
        Helper method to write given list of data dictionaries to csv, including the csv header.
        """
        if headers is None:
            headers = self.CSV_DATA_KEYS_ORDER
        header = ''
        lines = ''
        for key in headers:
            title_case_key = key.replace('_', ' ').title()
            header = '{}{},'.format(header, title_case_key)
        header = f"{header[:-1]}\n"

        for line_dict in lines_dict_list:
            for key in headers:
                lines = '{}"{}",'.format(lines, line_dict[key])
            lines = f"{lines[:-1]}\n"

        csv.write(header.encode())
        csv.write(lines.encode())
        csv.seek(0)
        return csv

    def _setup_organization(self, partner):
        """
        setup test-only organization.
        """
        OrganizationFactory(name='edx', key='edx', partner=partner)

    def _setup_prerequisites(self, partner):
        """
        Setup pre-reqs for Degree Program.
        """
        self._setup_organization(partner)

        intermediate = LevelTypeFactory(name='Intermediate')
        intermediate.set_current_language('en')
        intermediate.name_t = 'Intermediate'
        intermediate.save()

        SubjectFactory(name='Computer Science')

    def _assert_degree_data(self, degree, expected_data):
        """
        Verify the degree's data fields have same values as the expected data dict.
        """

        assert degree.title == expected_data['title']
        assert degree.overview == expected_data['overview']
        assert degree.type == self.program_type
        assert degree.marketing_slug == expected_data['marketing_slug']
        assert degree.additional_metadata.external_url == expected_data['paid_landing_page_url']
        assert degree.additional_metadata.external_identifier == expected_data['external_identifier']
        assert degree.additional_metadata.organic_url == expected_data['organic_url']
        assert degree.level_type_override.name == expected_data['level_type_override']
        assert degree.primary_subject_override.slug == expected_data['primary_subject_override']
        assert degree.language_override.name == expected_data['language_override']
        assert degree.organization_short_code_override == expected_data['organization_short_code_override']

    def mock_image_response(self, status=200, body=None, content_type='image/jpeg'):
        """
        Mock the image download call to return a pre-defined image.
        """
        # PNG. Single black pixel
        body = body or b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00' \
                       b'\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00' \
                       b'IEND\xaeB`\x82'
        image_url = 'https://example.com/image.jpg'
        responses.add(
            responses.GET,
            image_url,
            body=body,
            status=status,
            content_type=content_type
        )
        return image_url, body


class GeotargetingCSVLoaderMixin:
    """
    Mixin to contain various variables and methods used for GeotargetingCSVDataLoader testing.
    """
    def _setup_course(self, course_uuid):
        """
        setup test-only course.
        """
        CourseFactory(uuid=course_uuid, location_restriction=None)

    def _setup_program(self, program_uuid):
        """
        setup test-only course.
        """
        ProgramFactory(uuid=program_uuid, location_restriction=None)

    CSV_DATA_KEYS_ORDER = [
        'UUID',
        'PRODUCT TYPE',
        'INCLUDE OR EXCLUDE',
        'Countries',
    ]

    def _write_csv(self, csv, lines_dict_list, headers=None):
        """
        Helper method to write given list of data dictionaries to csv, including the csv header.
        """
        if headers is None:
            headers = self.CSV_DATA_KEYS_ORDER
        header = ''
        lines = ''
        for key in headers:
            title_case_key = key.replace('_', ' ').title()
            header = '{}{},'.format(header, title_case_key)
        header = f"{header[:-1]}\n"

        for line_dict in lines_dict_list:
            for key in headers:
                lines = '{}"{}",'.format(lines, line_dict[key])
            lines = f"{lines[:-1]}\n"

        csv.write(header.encode())
        csv.write(lines.encode())
        csv.seek(0)
        return csv


class GeolocationCSVLoaderMixin(GeotargetingCSVLoaderMixin):
    """
    Mixin to contain various variables and methods used for GeolocationCSVDataLoader testing.
    """
    CSV_DATA_KEYS_ORDER = [
        'UUID',
        'PRODUCT TYPE',
        'LOCATION NAME',
        'LATITUDE',
        'LONGTITUDE',
    ]


class CSVLoaderMixin:
    """
    Mixin to contain various variables and methods used for CSVDataLoader testing.
    """
    COURSE_KEY = 'edx+csv_123'
    COURSE_RUN_KEY = 'course-v1:edx+csv_123+1T2020'

    # The list to define order of the header keys in csv. The order here is important to keep header->values in sync.
    CSV_DATA_KEYS_ORDER = [
        'organization', 'title', 'number', 'course_enrollment_track', 'image', 'short_description',
        'long_description', 'what_will_you_learn', 'course_level', 'primary_subject', 'verified_price', 'collaborators',
        'syllabus', 'prerequisites', 'learner_testimonials', 'frequently_asked_questions', 'additional_information',
        'about_video_link', 'secondary_subject', 'tertiary_subject',
        'course_embargo_(ofac)_restriction_text_added_to_the_faq_section', 'publish_date',
        'start_date', 'start_time', 'end_date', 'end_time', 'reg_close_date', 'reg_close_time',
        'course_run_enrollment_track', 'course_pacing', 'staff', 'minimum_effort', 'maximum_effort',
        'length', 'content_language', 'transcript_language', 'expected_program_type', 'expected_program_name',
        'upgrade_deadline_override_date', 'upgrade_deadline_override_time', 'redirect_url', 'external_identifier',
        'lead_capture_form_url', 'organic_url', 'certificate_header', 'certificate_text', 'stat1', 'stat1_text',
        'stat2', 'stat2_text', 'organization_logo_override', 'organization_short_code_override', 'variant_id',
        'meta_title', 'meta_description', 'meta_keywords', 'slug'
    ]
    # The list of minimal data headers
    MINIMAL_CSV_DATA_KEYS_ORDER = [
        'organization', 'title', 'number', 'course_enrollment_track', 'image', 'short_description',
        'long_description', 'what_will_you_learn', 'course_level', 'primary_subject', 'verified_price', 'publish_date',
        'start_date', 'start_time', 'end_date', 'end_time', 'reg_close_date', 'reg_close_time',
        'course_run_enrollment_track', 'course_pacing', 'minimum_effort', 'maximum_effort', 'length',
        'content_language', 'transcript_language', 'syllabus', 'frequently_asked_questions',
    ]
    BASE_EXPECTED_COURSE_DATA = {
        # Loader does not publish newly created course or a course that has not reached published status.
        # That's why only the draft version of the course exists.
        'draft': True,
        'verified_price': 150,
        'title': 'CSV Course',
        'level_type': 'beginner',
        'about_video_link': 'http://www.example.com',
        'faq': '<p>Is day 19 really that tough?</p>',
        'outcome': '<p>Outcomes</p>',
        'syllabus': '<p>Introduction to Algorithms</p>',
        'prerequisites_raw': '<p>Summer of Winter</p>',
        'learner_testimonials': '<p>Very challenging</p>',
        'subjects': ['computer-science', 'social-sciences'],
        'collaborators': ['collab_1', 'collab_2', 'collab_3'],
        'short_description': '<p>Very short description</p>',
        'full_description': '<p>Organization,Title,Number,Course Enrollment track,Image,Short Description,Long '
                            'Description,Organization,Title,Number,Course Enrollment track,Image,Short Description'
                            ',Long Description,</p>',
        'external_url': 'http://www.example.com',
        'external_identifier': '123456789',
        'lead_capture_form_url': 'http://www.interest-form.com?id=1234',
        'organic_url': 'http://www.example.com?id=1234',
        'organization_short_code_override': 'Org Override',
        'certificate_info': {
            'heading': 'About the certificate',
            'blurb': 'For special people'
        },
        'facts_data': ['90 million', '<p>Bacterias cottage cost</p>', 'Diamond mine', '<p>Worth it</p>'],
        'start_date': '2020-01-25T00:00:00+00:00',
        'end_date': '2020-02-25T00:00:00+00:00',
        'registration_deadline': '2020-01-25T00:00:00+00:00',
        'variant_id': "00000000-0000-0000-0000-000000000000",
        "meta_title": "SEO Title",
        "meta_description": "SEO Description",
        "meta_keywords": ["Keyword 1", "Keyword 2"],
    }

    BASE_EXPECTED_COURSE_RUN_DATA = {
        # Loader does not publish newly created course or a course that has not reached published status.
        # That's why only the draft version of the course run exists.
        'draft': True,
        'status': CourseRunStatus.Unpublished,
        'length': 10,
        'minimum_effort': 4,
        'maximum_effort': 10,
        'verified_price': 150,
        'staff': ['staff_2', 'staff_1'],
        'content_language': 'English - United States',
        'transcript_language': ['English - Great Britain'],
        'go_live_date': '2020-01-25T00:00:00+00:00',
        'expected_program_type': 'professional-certificate',
        'expected_program_name': 'New Program for all',
    }

    def setUp(self):
        super().setUp()
        paid_exec_ed_name = 'Paid Executive Education'
        self.paid_exec_ed_slug = CourseRunType.PAID_EXECUTIVE_EDUCATION

        seat_type = SeatTypeFactory(name=paid_exec_ed_name)
        mode = ModeFactory(name=paid_exec_ed_name, slug=self.paid_exec_ed_slug)
        track = TrackFactory(mode=mode, seat_type=seat_type)
        self.course_run_type = CourseRunTypeFactory(
            name=paid_exec_ed_name, slug=self.paid_exec_ed_slug, tracks=[track]
        )
        self.course_type = CourseTypeFactory(
            name='Executive Education(2U)', slug=CourseType.EXECUTIVE_EDUCATION_2U,
            course_run_types=[self.course_run_type],
            entitlement_types=[seat_type]
        )

    def _write_csv(self, csv, lines_dict_list, headers=None):
        """
        Helper method to write given list of data dictionaries to csv, including the csv header.
        """
        if headers is None:
            headers = self.CSV_DATA_KEYS_ORDER
        header = ''
        lines = ''
        for key in headers:
            title_case_key = key.replace('_', ' ').title()
            header = '{}{},'.format(header, title_case_key)
        header = f"{header[:-1]}\n"

        for line_dict in lines_dict_list:
            for key in headers:
                lines = '{}"{}",'.format(lines, line_dict[key])
            lines = f"{lines[:-1]}\n"

        csv.write(header.encode())
        csv.write(lines.encode())
        csv.seek(0)
        return csv

    def _setup_organization(self, partner):
        """
        setup test-only organization.
        """
        OrganizationFactory(name='edx', key='edx', partner=partner)

    def _setup_prerequisites(self, partner):
        """
        Setup pre-reqs for the course and course run api calls.
        """
        self._setup_organization(partner)

        beginner = LevelTypeFactory()
        beginner.set_current_language('en')
        beginner.name_t = 'beginner'
        beginner.save()

        SubjectFactory(name='Computer Science')
        SubjectFactory(name='Social Sciences')

    def mock_ecommerce_publication(self, partner):
        """
        Mock ecommerce api calls.
        """
        url = f'{partner.ecommerce_api_url}publication/'
        responses.add(responses.POST, url, json={}, status=200)

    def mock_studio_calls(self, partner, run_key='course-v1:edx+csv_123+1T2020'):
        """
        Mock the studio api calls.
        """
        studio_url = '{root}/api/v1/course_runs/'.format(root=partner.studio_url.strip('/'))
        responses.add(responses.POST, studio_url, status=200)
        responses.add(responses.PATCH, f'{studio_url}{run_key}/', status=200)
        responses.add(responses.POST, f'{studio_url}{run_key}/images/', status=200)

    def mock_image_response(self, status=200, body=None, content_type='image/jpeg'):
        """
        Mock the image download call to return a pre-defined image.
        """
        # PNG. Single black pixel
        body = body or b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00' \
                       b'\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00' \
                       b'IEND\xaeB`\x82'
        image_url = 'https://example.com/image.jpg'
        responses.add(
            responses.GET,
            image_url,
            body=body,
            status=status,
            content_type=content_type
        )
        return image_url, body

    def _assert_course_data(self, course, expected_data):
        """
        Verify the course's data fields have same values as the expected data dict.
        """
        course_entitlement = CourseEntitlement.everything.get(
            draft=expected_data['draft'], mode__slug=self.paid_exec_ed_slug, course=course
        )

        assert course.draft is expected_data['draft']
        assert course.title == expected_data['title']
        assert course.faq == expected_data['faq']
        assert course.outcome == expected_data['outcome']
        assert course.syllabus_raw == expected_data['syllabus']
        assert course.short_description == expected_data['short_description']
        assert course.full_description == expected_data['full_description']
        assert course.prerequisites_raw == expected_data['prerequisites_raw']
        assert course.learner_testimonials == expected_data['learner_testimonials']
        assert course.level_type.name_t == expected_data['level_type']
        assert course.video.src == expected_data['about_video_link']
        assert course.type == self.course_type
        assert course.organization_short_code_override == 'Org Override'
        assert course_entitlement.price == expected_data['verified_price']
        assert course.additional_metadata.external_url == expected_data['external_url']
        assert course.additional_metadata.external_identifier == expected_data['external_identifier']
        assert course.additional_metadata.lead_capture_form_url == expected_data['lead_capture_form_url']
        assert course.additional_metadata.organic_url == expected_data['organic_url']
        assert course.additional_metadata.start_date.isoformat() == expected_data['start_date']
        assert course.additional_metadata.end_date.isoformat() == expected_data['end_date']
        assert course.additional_metadata.product_meta.title == expected_data['meta_title']
        assert course.additional_metadata.product_meta.description == expected_data['meta_description']
        assert set(
            keyword.name for keyword in course.additional_metadata.product_meta.keywords.all()
        ) == set(expected_data['meta_keywords'])
        assert course.additional_metadata.registration_deadline.isoformat() == expected_data['registration_deadline']
        assert course.additional_metadata.certificate_info.heading == expected_data['certificate_info']['heading']
        assert expected_data['certificate_info']['blurb'] in course.additional_metadata.certificate_info.blurb
        assert sorted([subject.slug for subject in course.subjects.all()]) == sorted(expected_data['subjects'])
        assert sorted(
            [collaborator.name for collaborator in course.collaborators.all()]
        ) == sorted(expected_data['collaborators'])
        assert str(course.additional_metadata.variant_id) == expected_data['variant_id']

        for fact in course.additional_metadata.facts.all():
            assert fact.heading in expected_data['facts_data']
            assert fact.blurb in expected_data['facts_data']

    def _assert_course_run_data(self, course_run, expected_data):
        """
        Verify the course run's data fields have same values as the expected data dict.
        """
        # No need to add draft in the filter here. Based on the draft status of the course run,
        # the appropriate Seat object is returned.
        course_run_seat = Seat.everything.get(type__slug=self.paid_exec_ed_slug, course_run=course_run)

        assert course_run.draft is expected_data['draft']
        assert course_run_seat.draft is expected_data['draft']
        assert course_run.status == expected_data['status']
        assert course_run.weeks_to_complete == expected_data['length']
        assert course_run.min_effort == expected_data['minimum_effort']
        assert course_run.max_effort == expected_data['maximum_effort']
        assert course_run_seat.price == expected_data['verified_price']
        assert course_run.go_live_date.isoformat() == expected_data['go_live_date']
        assert course_run.expected_program_type.slug == expected_data['expected_program_type']
        assert course_run.expected_program_name == expected_data['expected_program_name']
        assert course_run.language.name == expected_data['content_language']
        assert course_run.type == self.course_run_type
        assert sorted(
            [staff.given_name for staff in course_run.staff.all()]
        ) == sorted(expected_data['staff'])
        assert sorted(
            [language.name for language in course_run.transcript_languages.all()]
        ) == sorted(expected_data['transcript_language'])
