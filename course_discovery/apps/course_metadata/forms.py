from django import forms
from django.core.exceptions import ValidationError
from django.forms.utils import ErrorList
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Pathway, Program
from course_discovery.apps.course_metadata.widgets import SortedModelSelect2Multiple


class ProgramAdminForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = '__all__'

        widgets = {
            'courses': SortedModelSelect2Multiple(
                url='admin_metadata:course-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                },
            ),
            'authoring_organizations': SortedModelSelect2Multiple(
                url='admin_metadata:organisation-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                }
            ),
            'credit_backing_organizations': SortedModelSelect2Multiple(
                url='admin_metadata:organisation-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                }
            ),
            'instructor_ordering': SortedModelSelect2Multiple(
                url='admin_metadata:person-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        super().__init__(
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
        exclude = ('slug', 'url_slug', )


class CourseRunAdminForm(forms.ModelForm):
    class Meta:
        model = CourseRun
        fields = '__all__'
        widgets = {
            'staff': SortedModelSelect2Multiple(
                url='admin_metadata:person-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                },
            ),
            'transcript_languages': SortedModelSelect2Multiple(
                url='language_tags:language-tag-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                },
            ),
            'video_translation_languages': SortedModelSelect2Multiple(
                url='language_tags:language-tag-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                },
            ),
        }


class PathwayAdminForm(forms.ModelForm):
    class Meta:
        model = Pathway
        fields = '__all__'

    def clean(self):
        partner = self.cleaned_data.get('partner')
        programs = self.cleaned_data.get('programs')

        # partner and programs are required. If they are missing, skip this check and just show the required error
        if partner and programs:
            Pathway.validate_partner_programs(partner, programs)

        return self.cleaned_data


class ExcludeSkillsForm(forms.Form):
    """
    Form to handle excluding skills from course.
    """
    exclude_skills = forms.MultipleChoiceField()
    include_skills = forms.MultipleChoiceField()

    def __init__(self, course_skills, excluded_skills, *args, **kwargs):
        """
        Initialize multi choice fields.
        """
        super().__init__(*args, **kwargs)
        self.fields['exclude_skills'] = forms.MultipleChoiceField(
            choices=((course_skill.skill.id, course_skill.skill.name) for course_skill in course_skills),
            required=False,
        )
        self.fields['include_skills'] = forms.MultipleChoiceField(
            choices=((course_skill.skill.id, course_skill.skill.name) for course_skill in excluded_skills),
            required=False,
        )
