import logging

from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import format_lazy
from django.utils.translation import ugettext_lazy as _
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.publisher.choices import CourseRunStateChoices, PublisherUserRole
from course_discovery.apps.publisher.models import (
    CourseRun, CourseRunState, CourseState, CourseUserRole, OrganizationExtension, OrganizationUserRole, PublisherUser,
    User
)

logger = logging.getLogger(__name__)


class BaseUserAdminForm(forms.ModelForm):
    """This form will be use for type ahead search in django-admin."""

    class Meta:
        fields = '__all__'
        widgets = {
            'user': autocomplete.ModelSelect2(
                url='admin_core:user-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                }
            ),
        }


class UserAttributesAdminForm(BaseUserAdminForm):
    class Meta(BaseUserAdminForm.Meta):
        model = User


class OrganizationUserRoleForm(BaseUserAdminForm):
    class Meta(BaseUserAdminForm.Meta):
        model = OrganizationUserRole
        widgets = {
            'organization': autocomplete.ModelSelect2(
                url='admin_metadata:organisation-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                }
            ),
            'user': autocomplete.ModelSelect2(
                url='admin_core:user-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                }
            ),
        }


class CourseUserRoleForm(BaseUserAdminForm):
    class Meta(BaseUserAdminForm.Meta):
        model = CourseUserRole


class PublisherUserCreationForm(forms.ModelForm):
    class Meta:
        model = PublisherUser
        fields = ('username', 'groups',)

    def clean(self):
        cleaned_data = super(PublisherUserCreationForm, self).clean()
        groups = cleaned_data.get('groups')
        if not groups:
            raise forms.ValidationError(
                {'groups': _('This field is required.')}
            )

        return cleaned_data


class CourseRunAdminForm(forms.ModelForm):
    class Meta:
        model = CourseRun
        fields = '__all__'
        widgets = {
            'staff': autocomplete.ModelSelect2Multiple(
                url='admin_metadata:person-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'data-html': 'false',
                }
            ),
        }

    def clean_lms_course_id(self):
        lms_course_id = self.cleaned_data['lms_course_id']

        if lms_course_id:
            try:
                CourseKey.from_string(lms_course_id)
            except InvalidKeyError:
                raise ValidationError(_('Invalid course key.'))

            return lms_course_id

        return None


class CourseRunStateAdminForm(forms.ModelForm):
    class Meta:
        model = CourseRunState
        fields = '__all__'

    def clean(self):
        cleaned_data = self.cleaned_data
        owner_role = cleaned_data.get('owner_role')
        course_run_state = cleaned_data.get('name')
        if owner_role == PublisherUserRole.Publisher and course_run_state in (CourseRunStateChoices.Draft,
                                                                              CourseRunStateChoices.Review):
            raise forms.ValidationError(_('Owner role can not be publisher if the state is draft or review'))
        return cleaned_data


class CourseStateAdminForm(forms.ModelForm):
    class Meta:
        model = CourseState
        fields = '__all__'

    def clean(self):
        cleaned_data = self.cleaned_data
        owner_role = cleaned_data.get('owner_role')
        course = cleaned_data.get('course')
        if not CourseUserRole.objects.filter(course=course, role=owner_role):
            raise forms.ValidationError(
                format_lazy(_('Please create {} course user role before assigning it owner role'), owner_role)
            )
        return cleaned_data


class AdminImportCourseForm(forms.Form):
    start_id = forms.IntegerField(min_value=1, label='This course id will import.')
    create_course_run = forms.BooleanField(
        label=_('Create initial run for the course'),
        widget=forms.CheckboxInput,
        required=False
    )

    class Meta:
        fields = ('start_id',)


class OrganizationExtensionForm(forms.ModelForm):
    class Meta:
        model = OrganizationExtension
        fields = '__all__'
        widgets = {
            'organization': autocomplete.ModelSelect2(
                url='admin_metadata:organisation-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                }
            ),
        }
