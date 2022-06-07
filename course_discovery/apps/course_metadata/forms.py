import logging
from django import forms
from django.core.exceptions import ValidationError
from django.forms.utils import ErrorList
from django.utils.translation import gettext_lazy as _

from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Pathway, ProductTopic, Program
)
from course_discovery.apps.course_metadata.widgets import SortedModelSelect2Multiple

logger = logging.getLogger(__name__)


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

        super().clean()

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

    def clean(self):
        super().clean()

        # Course must have at least one subject in order to add topics
        subjects = self.cleaned_data.get('subjects')
        product_topics = self.cleaned_data.get('product_topics')
        if product_topics and not subjects:
            raise ValidationError('Course must have a subject to add topics.')

        # Added topics must share at least one subject with the course
        subject_ids = [subject.id for subject in subjects]
        failed_topics = []
        for topic in product_topics:
            qs = ProductTopic.objects.filter(id=topic.id, subjects__id__in=subject_ids)
            if not qs.exists():
                failed_topics.append(topic.name)
        if len(failed_topics) > 0:
            raise ValidationError(
                f'Topics must share at least one subject with course. Failed on: {*failed_topics,}'
            )

        return self.cleaned_data


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


class ProductTopicAdminForm(forms.ModelForm):
    class Meta:
        model = ProductTopic
        fields = '__all__'

    def clean(self):
        super().clean()

        if self.instance.id:
            parent_topics = self.cleaned_data.get('parent_topics')
            for parent_topic in parent_topics:
                if parent_topic.id == self.instance.id:
                    raise ValidationError('Cannot add self as a parent topic.')
                qs = ProductTopic.objects.filter(id=parent_topic.id, parent_topics__id=self.instance.id)
                if qs.exists():
                    raise ValidationError(
                        f'"{parent_topic.name}" is already a child topic of "{self.instance.name}". Please'
                        ' remove from parent topics.'
                    )
        
        return self.cleaned_data
