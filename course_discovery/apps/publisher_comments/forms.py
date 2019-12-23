from django import forms
from django.contrib.contenttypes.models import ContentType

from course_discovery.apps.publisher_comments.models import Comments


class CommentsAdminForm(forms.ModelForm):
    """ Comment form for admin. It will load only required content types models in drop down. """

    class Meta:
        model = Comments
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(CommentsAdminForm, self).__init__(*args, **kwargs)
        self.fields['content_type'].queryset = ContentType.objects.filter(
            model__in=['course', 'courserun', 'seat'],
            app_label='publisher'
        )
