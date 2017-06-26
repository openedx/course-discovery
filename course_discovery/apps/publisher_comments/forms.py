from django import forms
from django.contrib.contenttypes.models import ContentType
from django_comments.forms import CommentForm

from course_discovery.apps.publisher_comments.models import Comments, CommentTypeChoices


# pylint: disable=no-member
class CommentsForm(CommentForm):
    modified = forms.DateTimeField(required=False, widget=forms.HiddenInput)
    comment_type = forms.ChoiceField(
        required=False, choices=CommentTypeChoices.choices, initial=CommentTypeChoices.Default
    )

    def get_comment_model(self):
        return Comments

    def get_comment_create_data(self, site_id=None):
        # Use the data of the superclass, and add in the title field
        data = super(CommentsForm, self).get_comment_create_data(site_id=site_id)
        data['modified'] = self.cleaned_data['modified']
        data['comment_type'] = self.cleaned_data['comment_type']
        return data

    def __init__(self, *args, **kwargs):
        super(CommentsForm, self).__init__(*args, **kwargs)
        self.fields['comment'].widget.attrs['rows'] = 4


class CommentEditForm(forms.ModelForm):
    """ Comment edit form. """
    submit_date = forms.CharField(widget=forms.TextInput(attrs={'readonly': 'readonly'}))

    class Meta:
        model = Comments
        fields = ('comment', 'submit_date', )


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
