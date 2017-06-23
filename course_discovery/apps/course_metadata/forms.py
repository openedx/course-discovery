from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from django.forms.utils import ErrorList
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program


def filter_choices_to_render_with_order_preserved(self, selected_choices):
    """
    Preserves ordering of selected_choices when creating the choices queryset.

    See https://codybonney.com/creating-a-queryset-from-a-list-while-preserving-order-using-django.

    django-autocomplete's definition of this method on QuerySetSelectMixin loads selected choices in
    order of primary key instead of the order in which the choices are actually stored.
    """
    clauses = ' '.join(['WHEN id={} THEN {}'.format(pk, i) for i, pk in enumerate(selected_choices)])
    ordering = 'CASE {} END'.format(clauses)
    self.choices.queryset = self.choices.queryset.filter(
        pk__in=[c for c in selected_choices if c]
    ).extra(select={'ordering': ordering}, order_by=('ordering',))


class ProgramAdminForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = '__all__'

        # Monkey patch filter_choices_to_render with our own definition which preserves ordering.
        autocomplete.ModelSelect2Multiple.filter_choices_to_render = filter_choices_to_render_with_order_preserved

        widgets = {
            'courses': autocomplete.ModelSelect2Multiple(
                url='admin_metadata:course-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                },
            ),
            'authoring_organizations': autocomplete.ModelSelect2Multiple(
                url='admin_metadata:organisation-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                }
            ),
            'credit_backing_organizations': autocomplete.ModelSelect2Multiple(
                url='admin_metadata:organisation-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super(ProgramAdminForm, self).__init__(*args, **kwargs)
        self.fields['type'].required = True
        self.fields['marketing_slug'].required = True
        self.fields['courses'].required = False

    def clean(self):
        status = self.cleaned_data.get('status')
        banner_image = self.cleaned_data.get('banner_image')

        if status == ProgramStatus.Active and not banner_image:
            raise ValidationError(_(
                'Programs can only be activated if they have a banner image.'
            ))

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
        self.fields['excluded_course_runs'].widget = forms.widgets.CheckboxSelectMultiple()
        self.fields['excluded_course_runs'].help_text = ''
        self.fields['excluded_course_runs'].queryset = CourseRun.objects.filter(
            course__id__in=query_set
        )


class CourseAdminForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = '__all__'
        widgets = {
            'canonical_course_run': autocomplete.ModelSelect2(
                url='admin_metadata:course-run-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                }
            ),
        }
