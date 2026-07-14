from dal import autocomplete
from django import forms

from course_discovery.apps.course_metadata.models import Course, Program


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
        }

    def __init__(self, *args, **kwargs):
        super(ProgramAdminForm, self).__init__(*args, **kwargs)
        self.fields['courses'].required = False

    def clean(self):
        return self.cleaned_data


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
