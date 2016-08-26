from django import forms
from django.core.exceptions import ValidationError
from django.forms.util import ErrorList
from django.utils.translation import ugettext_lazy as _

from dal import autocomplete
from course_discovery.apps.course_metadata.models import Program, CourseRun


class ProgramAdminForm(forms.ModelForm):

    class Meta:
        model = Program
        exclude = (
            'subtitle', 'category', 'marketing_slug', 'weeks_to_complete',
            'min_hours_effort_per_week', 'max_hours_effort_per_week',
        )
        widgets = {
            'courses': autocomplete.ModelSelect2Multiple(
                url='admin_metadata:course-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                },
            ),
            'authoring_organizations': autocomplete.ModelSelect2Multiple(
                url='admin_metadata:organisation-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                }
            ),
            'credit_backing_organizations': autocomplete.ModelSelect2Multiple(
                url='admin_metadata:organisation-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                }
            ),
            'video': autocomplete.ModelSelect2(
                url='admin_metadata:video-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super(ProgramAdminForm, self).__init__(*args, **kwargs)
        self.fields['type'].required = True
        self.fields['courses'].required = False

    def clean(self):
        status = self.cleaned_data.get('status')
        banner_image = self.cleaned_data.get('banner_image')
        if status == Program.ProgramStatus.Active and not banner_image:
            raise ValidationError(_('Status cannot be change to active without banner image.'))
        return self.cleaned_data


class CourseRunSelectionForm(forms.ModelForm):

    class Meta:
        model = Program
        fields = ('excluded_course_runs',)

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None, initial=None, error_class=ErrorList,
                 label_suffix=':', empty_permitted=False, instance=None):
        super(CourseRunSelectionForm, self).__init__(
            data, files, auto_id, prefix,
            initial, error_class, label_suffix,
            empty_permitted, instance
        )

        query_set = [course.pk for course in instance.courses.all()]
        self.fields["excluded_course_runs"].widget = forms.widgets.CheckboxSelectMultiple()
        self.fields["excluded_course_runs"].help_text = ""
        self.fields['excluded_course_runs'].queryset = CourseRun.objects.filter(
            course__id__in=query_set
        )
