from dal import widgets
from django import forms
from django.core.exceptions import ValidationError
from django.forms.utils import ErrorList
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Program, CourseRun


class HackDjangoAutocompleteMixin(object):
    # It seems to me there is an issue with the select 2 widget in django autocomplete.
    # When the widget loads selected choices it loads them in order of django id, not the order
    # they are stored in in the database. This workaround works, but not sure what approach
    # would be less hacky. Perhaps opening a PR to the django autocomplete repo if this is
    # fact an issue?

    class QuerySetSelectMixin2(widgets.WidgetMixin):

        def filter_choices_to_render(self, selected_choices):
            # preserve ordering of selected_choices in queryset
            # https://codybonney.com/creating-a-queryset-from-a-list-while-preserving-order-using-django/
            clauses = ' '.join(['WHEN id={} THEN {}'.format(pk, i) for i, pk in enumerate(selected_choices)])
            ordering = 'CASE {} END'.format(clauses)
            self.choices.queryset = self.choices.queryset.filter(
                pk__in=[c for c in selected_choices if c]
            ).extra(select={'ordering': ordering}, order_by=('ordering',))

    widgets.QuerySetSelectMixin = QuerySetSelectMixin2


class ProgramAdminForm(HackDjangoAutocompleteMixin, forms.ModelForm):
    class Meta:
        model = Program
        fields = '__all__'
        from dal import autocomplete
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
        marketing_slug = self.cleaned_data.get('marketing_slug')
        banner_image = self.cleaned_data.get('banner_image')

        if status == ProgramStatus.Active and not (marketing_slug and banner_image):
            raise ValidationError(_(
                'Programs can only be activated if they have a marketing slug and a banner image.'
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
        self.fields["excluded_course_runs"].widget = forms.widgets.CheckboxSelectMultiple()
        self.fields["excluded_course_runs"].help_text = ""
        self.fields['excluded_course_runs'].queryset = CourseRun.objects.filter(
            course__id__in=query_set
        )
