"""
Course publisher forms.
"""
from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.models import LevelType, Organization, Person, Subject
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.mixins import LanguageModelSelect2Multiple, check_roles_access
from course_discovery.apps.publisher.models import (Course, CourseRun, CourseUserRole, OrganizationExtension,
                                                    OrganizationUserRole, PublisherUser, Seat, User)


class UserModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.username


class PersonModelMultipleChoice(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        context = {
            'profile_image': obj.get_profile_image_url,
            'full_name': obj.full_name
        }
        return str(render_to_string('publisher/_personFieldLabel.html', context=context))


class ClearableImageInput(forms.ClearableFileInput):
    """
    ClearableFileInput render the saved image as link.

    Render img tag instead of link and add some classes for JS and CSS, also
    remove image link and clear checkbox.
    """
    clear_checkbox_label = _('Remove Image')
    template_with_initial = render_to_string('publisher/_clearableImageInput.html')
    template_with_clear = render_to_string('publisher/_clearImageLink.html')


class BaseCourseForm(forms.ModelForm):
    """ Base Course Form. """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label_suffix', '')
        super(BaseCourseForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field_classes = 'field-input input-text'
            if isinstance(field, forms.Textarea):
                field_classes = 'field-textarea input-textarea'
            if isinstance(field, (forms.BooleanField, forms.ChoiceField,)):
                field_classes = 'field-input input-checkbox'
            if isinstance(field, (forms.ModelChoiceField, forms.TypedChoiceField,)):
                field_classes = 'field-input input-select'
            if isinstance(field, forms.DateTimeField):
                field_classes = '{} add-pikaday'.format(field_classes)
                field.input_formats = ['YYYY-MM-DDTHH:mm:ss']
            if isinstance(field, forms.ModelMultipleChoiceField):
                field_classes = 'field-input'

            if field_name in self.errors:
                field_classes = '{} has-error'.format(field_classes)

            field.widget.attrs['class'] = field_classes


class CourseForm(BaseCourseForm):
    """ Course Form. """

    short_description = forms.CharField(widget=forms.Textarea, max_length=255, required=False)

    class Meta:
        model = Course
        fields = '__all__'
        exclude = ('changed_by',)


class CustomCourseForm(CourseForm):
    """ Course Form. """
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.filter(
            organization_extension__organization_id__isnull=False
        ).order_by(Lower('key')),
        label=_('Organization Name'),
        required=True
    )
    title = forms.CharField(label=_('Course Title'), required=True)
    number = forms.CharField(label=_('Course Number'), required=True)
    short_description = forms.CharField(
        label=_('Brief Description'), max_length=140, widget=forms.Textarea, required=False
    )
    full_description = forms.CharField(
        label=_('Full Description'), max_length=2500, widget=forms.Textarea, required=False
    )
    prerequisites = forms.CharField(
        label=_('Prerequisites'), max_length=200, widget=forms.Textarea, required=False
    )

    # users will be loaded through AJAX call based on organization
    team_admin = UserModelChoiceField(
        queryset=User.objects.none(), required=True,
        label=_('Organization Course Admin'),
    )

    subjects = Subject.objects.all().order_by('name')
    primary_subject = forms.ModelChoiceField(
        queryset=subjects,
        label=_('Primary'),
        required=False
    )
    secondary_subject = forms.ModelChoiceField(
        queryset=subjects,
        label=_('Secondary (optional)'),
        required=False
    )
    tertiary_subject = forms.ModelChoiceField(
        queryset=subjects,
        label=_('Tertiary (optional)'),
        required=False
    )

    level_type = forms.ModelChoiceField(
        queryset=LevelType.objects.all().order_by('-name'),
        required=False
    )

    class Meta(CourseForm.Meta):
        model = Course
        widgets = {
            'image': ClearableImageInput()
        }
        fields = (
            'title', 'number', 'short_description', 'full_description',
            'expected_learnings', 'primary_subject', 'secondary_subject',
            'tertiary_subject', 'prerequisites', 'image', 'team_admin',
            'level_type', 'organization', 'is_seo_review', 'syllabus',
        )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        edit_mode = kwargs.pop('edit_mode', None)
        organization = kwargs.pop('organization', None)
        if organization:
            org_extension = OrganizationExtension.objects.get(organization=organization)
            self.declared_fields['team_admin'].queryset = User.objects.filter(
                groups__name=org_extension.group
            ).order_by('full_name', 'username')

        if user:
            organizations = Organization.objects.filter(
                organization_extension__organization_id__isnull=False
            ).order_by(Lower('key'))

            if not check_roles_access(user):
                # If not internal user return only those organizations which belongs to user.
                organizations = organizations.filter(
                    organization_extension__group__in=user.groups.all()
                ).order_by(Lower('key'))

            self.declared_fields['organization'].queryset = organizations

        super(CustomCourseForm, self).__init__(*args, **kwargs)
        if edit_mode:
            self.fields['title'].widget = forms.HiddenInput()
            self.fields['number'].widget = forms.HiddenInput()
            self.fields['team_admin'].widget = forms.HiddenInput()
            self.fields['organization'].widget = forms.HiddenInput()


class CourseRunForm(BaseCourseForm):
    """ Course Run Form. """

    class Meta:
        model = CourseRun
        fields = '__all__'
        exclude = ('state', 'changed_by',)


class CustomCourseRunForm(CourseRunForm):
    """ Course Run Form. """
    start = forms.DateTimeField(label=_('Course Start Date'), required=True)
    end = forms.DateTimeField(label=_('Course End Date'), required=True)
    staff = PersonModelMultipleChoice(
        label=_('instructor'),
        queryset=Person.objects.all(),
        widget=autocomplete.ModelSelect2Multiple(
            url='admin_metadata:person-autocomplete',
            attrs={
                'data-minimum-input-length': 2,
                'data-html': 'true',
            }
        ),
        required=False,
    )
    target_content = forms.BooleanField(
        widget=forms.RadioSelect(
            choices=((1, _("Yes")), (0, _("No")))), initial=0, required=False
    )
    pacing_type = forms.ChoiceField(
        label=_('Pacing'),
        widget=forms.RadioSelect,
        choices=CourseRunPacing.choices,
        required=True
    )

    transcript_languages = forms.ModelMultipleChoiceField(
        queryset=LanguageTag.objects.all(),
        widget=LanguageModelSelect2Multiple(
            url='language_tags:language-tag-autocomplete',
            attrs={
                'data-minimum-input-length': 2
            }
        ),
        required=False,
    )

    is_xseries = forms.BooleanField(
        label=_('Is XSeries?'),
        widget=forms.CheckboxInput,
        required=False,
    )

    is_micromasters = forms.BooleanField(
        label=_('Is MicroMasters?'),
        widget=forms.CheckboxInput,
        required=False,
    )

    xseries_name = forms.CharField(label=_('XSeries Name'), required=False)
    micromasters_name = forms.CharField(label=_('MicroMasters Name'), required=False)
    lms_course_id = forms.CharField(label=_('Course Run Key'), required=False)

    class Meta(CourseRunForm.Meta):
        fields = (
            'length', 'transcript_languages', 'language', 'min_effort', 'max_effort',
            'target_content', 'pacing_type', 'video_language',
            'staff', 'start', 'end', 'is_xseries', 'xseries_name', 'is_micromasters',
            'micromasters_name', 'lms_course_id',
        )

    def save(self, commit=True, course=None, changed_by=None):  # pylint: disable=arguments-differ
        course_run = super(CustomCourseRunForm, self).save(commit=False)

        if course:
            course_run.course = course

        if changed_by:
            course_run.changed_by = changed_by

        if commit:
            course_run.save()

        return course_run

    def clean_lms_course_id(self):
        lms_course_id = self.cleaned_data['lms_course_id']

        if lms_course_id:
            try:
                CourseKey.from_string(lms_course_id)
            except InvalidKeyError:
                raise ValidationError("Invalid course key.")

            return lms_course_id

        return None

    def __init__(self, *args, **kwargs):
        is_project_coordinator = kwargs.pop('is_project_coordinator', None)
        super(CustomCourseRunForm, self).__init__(*args, **kwargs)
        if not is_project_coordinator:
            self.fields['lms_course_id'].widget = forms.HiddenInput()


class SeatForm(BaseCourseForm):
    """ Course Seat Form. """

    class Meta:
        model = Seat
        fields = '__all__'
        exclude = ('currency', 'changed_by',)

    def save(self, commit=True, course_run=None, changed_by=None):  # pylint: disable=arguments-differ
        seat = super(SeatForm, self).save(commit=False)
        if seat.type in [Seat.HONOR, Seat.AUDIT]:
            seat.price = 0.00
            seat.upgrade_deadline = None
            seat.credit_provider = ''
            seat.credit_hours = None
        if seat.type == Seat.VERIFIED:
            seat.credit_provider = ''
            seat.credit_hours = None
        if seat.type in [Seat.PROFESSIONAL, Seat.NO_ID_PROFESSIONAL]:
            seat.upgrade_deadline = None
            seat.credit_provider = ''
            seat.credit_hours = None

        if course_run:
            seat.course_run = course_run

        if changed_by:
            seat.changed_by = changed_by

        if commit:
            seat.save()

        return seat

    def clean(self):
        price = self.cleaned_data.get('price')
        seat_type = self.cleaned_data.get('type')

        if seat_type in [Seat.PROFESSIONAL, Seat.VERIFIED] and not price:
            self.add_error('price', _('Only audit seat can be without price.'))

        return self.cleaned_data


class CustomSeatForm(SeatForm):
    """ Course Seat Form. """

    def __init__(self, *args, **kwargs):
        super(CustomSeatForm, self).__init__(*args, **kwargs)

        field_classes = 'field-input input-select'

        if 'type' in self.errors:
            field_classes = '{} has-error'.format(field_classes)

        self.fields['type'].widget.attrs = {'class': field_classes}

    TYPE_CHOICES = [
        ('', _('Choose course type')),
        (Seat.AUDIT, _('Audit Only')),
        (Seat.VERIFIED, _('Verified Certificate')),
        (Seat.PROFESSIONAL, _('Professional Education')),
    ]

    type = forms.ChoiceField(choices=TYPE_CHOICES, required=False, label=_('Seat Type'))
    price = forms.DecimalField(max_digits=6, decimal_places=2, required=False, initial=0.00)

    class Meta(SeatForm.Meta):
        fields = ('price', 'type')


class BaseUserAdminForm(forms.ModelForm):
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


class CourseUserRoleForm(BaseUserAdminForm):
    class Meta(BaseUserAdminForm.Meta):
        model = CourseUserRole


class PublisherUserCreationForm(forms.ModelForm):
    class Meta:
        model = PublisherUser
        fields = ('username', 'groups',)

    def clean(self):
        groups = self.cleaned_data.get('groups')
        if not groups:
            raise forms.ValidationError(
                {'groups': _('This field is required.')}
            )

        return self.cleaned_data


class CourseRunAdminForm(forms.ModelForm):

    class Meta:
        model = CourseRun
        fields = '__all__'

    def clean_lms_course_id(self):
        lms_course_id = self.cleaned_data['lms_course_id']

        if lms_course_id:
            try:
                CourseKey.from_string(lms_course_id)
            except InvalidKeyError:
                raise ValidationError(_("Invalid course key."))

            return lms_course_id

        return None
