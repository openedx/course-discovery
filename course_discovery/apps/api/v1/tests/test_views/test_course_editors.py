import ddt
from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.models import CourseEditor
from course_discovery.apps.course_metadata.tests.factories import CourseEditorFactory, CourseFactory
from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory


@ddt.ddt
class CourseEditorsViewSetTests(SerializationMixin, APITestCase):
    list_path = reverse('api:v1:course_editor-list')

    def setUp(self):
        super().setUp()
        self.staff_user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.staff_user.username, password=USER_PASSWORD)
        self.user = UserFactory()
        partner = Partner.objects.first()
        self.course = CourseFactory(draft=True, partner=partner)
        self.org_ext = OrganizationExtensionFactory()
        self.course.authoring_organizations.add(self.org_ext.organization)

    def test_list(self):
        """Verify GET endpoint returns list of editors"""
        CourseEditorFactory()
        response = self.client.get(self.list_path)

        assert len(response.data['results']) == 1

        # Test for non staff user
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        response = self.client.get(self.list_path)

        self.assertFalse(response.data['results'])

    def test_course_query_param(self):
        """Verify GET endpoint with course query param returns editors relative to that course"""
        CourseEditorFactory(course=self.course)
        CourseEditorFactory()

        response = self.client.get(self.list_path)

        assert len(response.data['results']) == 2

        response = self.client.get(self.list_path, {'course': self.course.uuid})

        assert len(response.data['results']) == 1
        assert response.data['results'][0]['course'] == self.course.uuid

    @ddt.data(
        (True, True),  # Staff User on Draft Course
        (True, False),  # Staff User on Official Course
        (False, True),  # Non-staff User on Draft Course
        (False, False),  # Non-staff User on Official Course
    )
    @ddt.unpack
    def test_create_for_self_and_draft_course(self, is_staff, is_draft):
        """Verify can make self an editor. Test cases: as staff and non-staff, on official and draft course"""

        self.user.is_staff = is_staff
        self.user.save()
        partner = Partner.objects.first()
        course = CourseFactory(draft=is_draft, partner=partner)
        self.user.groups.add(self.org_ext.group)
        course.authoring_organizations.add(self.org_ext.organization)

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.client.post(self.list_path, {'course': course.uuid}, format='json')
        course_editor = CourseEditor.objects.first()

        assert course_editor.course == course
        assert course_editor.user == self.user

    def test_create_for_self_as_non_staff_with_invalid_course(self):
        """Verify non staff user cannot make them self an editor of a course they dont belong to"""

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        response = self.client.post(self.list_path, {'course': self.course.uuid}, format='json')

        assert response.status_code == 403

    def test_create_for_other_user_as_staff(self):
        """Verify staff user can make another user an editor"""

        self.user.groups.add(self.org_ext.group)
        self.client.post(self.list_path, {'course': self.course.uuid, 'user_id': self.user.id}, format='json')
        course_editor = CourseEditor.objects.first()

        assert course_editor.course == self.course
        assert course_editor.user == self.user

    def test_create_for_other_user_as_non_staff(self):
        """Verify non staff can make another user an editor"""

        user2 = UserFactory()

        self.user.groups.add(self.org_ext.group)
        user2.groups.add(self.org_ext.group)

        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.client.post(self.list_path, {'course': self.course.uuid, 'user_id': user2.id}, format='json')
        course_editor = CourseEditor.objects.first()

        assert course_editor.course == self.course
        assert course_editor.user == user2

    def test_create_for_invalid_other_user(self):
        """Verify a user can't be made an editor of a course if both are not under the same organization"""

        response = self.client.post(
            self.list_path, {'course': self.course.uuid, 'user_id': self.user.id}, format='json'
        )

        assert response.status_code == 403
