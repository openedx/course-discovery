from django.contrib import admin

from course_discovery.apps.publisher_comments.forms import CommentsAdminForm
from course_discovery.apps.publisher_comments.models import Comments


class CommentsAdmin(admin.ModelAdmin):
    form = CommentsAdminForm
    readonly_fields = ('modified',)

admin.site.register(Comments, CommentsAdmin)
