from django.conf import settings
from django.contrib.sites.models import Site
from django.test import TestCase
from django.urls import reverse

from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.publisher.tests import factories
from course_discovery.apps.publisher_comments.forms import CommentsAdminForm
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


class AdminTests(TestCase):
    """ Tests Admin page and customize form."""
    def setUp(self):
        super(AdminTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.site = Site.objects.get(pk=settings.SITE_ID)
        self.course = factories.CourseFactory()
        self.comment = CommentFactory(content_object=self.course, user=self.user, site=self.site)

    def test_comment_detail_form(self):
        """ Verify in admin panel comment detail form contain the custom modified field. """
        # pylint: disable=no-member
        resp = self.client.get(reverse('admin:publisher_comments_comments_change', args=(self.comment.id,)))
        self.assertContains(resp, 'modified')

    def test_comment_admin_form(self):
        """ Verify in admin panel for comments loads only three models in content type drop down. """
        form = CommentsAdminForm(instance=self.comment)
        self.assertListEqual(
            sorted([con.model for con in form.fields['content_type']._queryset]),   # pylint: disable=protected-access
            sorted(['courserun', 'seat', 'course'])
        )
