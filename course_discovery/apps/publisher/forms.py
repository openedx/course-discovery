import datetime
import html

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
from course_discovery.apps.publisher.mixins import LanguageModelSelect2Multiple, get_user_organizations
from course_discovery.apps.publisher.models import (Course, CourseRun, CourseUserRole, OrganizationExtension,
                                                    OrganizationUserRole, PublisherUser, Seat, User)
from course_discovery.apps.publisher.utils import is_internal_user
from course_discovery.apps.publisher.validators import validate_text_count


class UserModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.username


class PersonModelMultipleChoice(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        context = {
            'profile_image': obj.get_profile_image_url,
            'full_name': obj.full_name,
            'uuid': obj.uuid if not obj.profile_image_url else None
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


class BaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label_suffix', '')
        super(BaseForm, self).__init__(*args, **kwargs)
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
            if isinstance(field, forms.ModelMultipleChoiceField):
                field_classes = 'field-input'

            if field_name in self.errors:
                field_classes = '{} has-error'.format(field_classes)

            field.widget.attrs['class'] = field_classes


class CourseForm(BaseForm):
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.filter(
            organization_extension__organization_id__isnull=False
        ).order_by(Lower('key')),
        label=_('Organization Name'),
        required=True
    )
    title = forms.CharField(label=_('Course Title'), required=True)
    number = forms.CharField(
        label=_('Course Number'), required=True,
        validators=[validate_text_count(max_length=50)]
    )
    short_description = forms.CharField(
        label=_('Short Description'),
        widget=forms.Textarea, required=False, validators=[validate_text_count(max_length=255)]
    )
    full_description = forms.CharField(
        label=_('Long Description'), widget=forms.Textarea, required=False,
        validators=[validate_text_count(max_length=2500)]
    )
    prerequisites = forms.CharField(
        label=_('Prerequisites'), widget=forms.Textarea, required=False,
        validators=[validate_text_count(max_length=200)]
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
        label=_('Additional Subject (optional)'),
        required=False
    )
    tertiary_subject = forms.ModelChoiceField(
        queryset=subjects,
        label=_('Additional Subject (optional)'),
        required=False
    )

    level_type = forms.ModelChoiceField(
        queryset=LevelType.objects.all().order_by('-name'),
        label=_('Level'),
        required=False
    )

    expected_learnings = forms.CharField(
        label=_('What You Will Learn'), widget=forms.Textarea, required=False,
        validators=[validate_text_count(max_length=2500)]
    )

    learner_testimonial = forms.CharField(
        label=_('Learner Testimonial'), widget=forms.Textarea, required=False,
        validators=[validate_text_count(max_length=500)]
    )

    faq = forms.CharField(
        label=_('FAQ'), widget=forms.Textarea, required=False,
        validators=[validate_text_count(max_length=2500)]
    )

    syllabus = forms.CharField(
        label=_('Syllabus'), widget=forms.Textarea, required=False,
        validators=[validate_text_count(max_length=2500)]
    )

    add_new_run = forms.BooleanField(required=False)

    class Meta:
        model = Course
        widgets = {
            'image': ClearableImageInput(attrs={'accept': 'image/*'})
        }
        fields = (
            'title', 'number', 'short_description', 'full_description',
            'expected_learnings', 'primary_subject', 'secondary_subject',
            'tertiary_subject', 'prerequisites', 'image', 'team_admin',
            'level_type', 'organization', 'is_seo_review', 'syllabus',
            'learner_testimonial', 'faq', 'video_link',
        )

    def __init__(self, *args, **kwargs):
        # In case of edit mode pre-populate the drop-downs
        user = kwargs.pop('user', None)
        organization = kwargs.pop('organization', None)
        if organization:
            org_extension = OrganizationExtension.objects.get(organization=organization)
            self.declared_fields['team_admin'].queryset = User.objects.filter(
                groups__name=org_extension.group
            ).order_by('full_name', 'username')

        if user:
            self.declared_fields['organization'].queryset = get_user_organizations(user)
            self.declared_fields['team_admin'].widget.attrs = {'data-user': user.id}

        super(CourseForm, self).__init__(*args, **kwargs)

        if user and not is_internal_user(user):
            self.fields['video_link'].widget = forms.HiddenInput()

    def clean_title(self):
        """
        Convert all named and numeric character references in the string
        to the corresponding unicode characters
        """
        return html.unescape(self.cleaned_data.get("title"))

    def clean(self):
        cleaned_data = self.cleaned_data
        organization = cleaned_data.get("organization")
        title = cleaned_data.get("title")
        number = cleaned_data.get("number")
        instance = getattr(self, 'instance', None)
        if not instance.pk:
            if Course.objects.filter(title=title, organizations__in=[organization]).exists():
                raise ValidationError({'title': _('This course title already exists')})
            if Course.objects.filter(number=number, organizations__in=[organization]).exists():
                raise ValidationError({'number': _('This course number already exists')})
        return cleaned_data


class CourseSearchForm(forms.Form):
    """ Course Type ahead Search Form. """
    course = forms.ModelChoiceField(
        label=_('Find Course'),
        queryset=Course.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='publisher:api:course-autocomplete',
            attrs={
                'data-minimum-input-length': 3,
            }
        ),
        required=True,
    )


class CourseRunForm(BaseForm):
    start = forms.DateTimeField(label=_('Course Start Date'), required=True)
    end = forms.DateTimeField(label=_('Course End Date'), required=True)
    staff = PersonModelMultipleChoice(
        label=_('Instructor'),
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
        label=_('Transcript Languages'),
        widget=LanguageModelSelect2Multiple(
            url='language_tags:language-tag-autocomplete',
            attrs={
                'data-minimum-input-length': 2
            }
        ),
        required=False,
    )

    is_xseries = forms.BooleanField(
        label=_('XSeries'),
        widget=forms.CheckboxInput,
        required=False,
    )

    is_micromasters = forms.BooleanField(
        label=_('MicroMasters'),
        widget=forms.CheckboxInput,
        required=False,
    )

    is_professional_certificate = forms.BooleanField(
        label=_('Professional Certificate'),
        widget=forms.CheckboxInput,
        required=False,
    )

    xseries_name = forms.CharField(label=_('XSeries Name'), required=False)
    professional_certificate_name = forms.CharField(label=_('Professional Certificate Name'), required=False)
    micromasters_name = forms.CharField(label=_('MicroMasters Name'), required=False)
    lms_course_id = forms.CharField(label=_('Studio URL'), required=False)
    video_language = forms.ModelChoiceField(
        queryset=LanguageTag.objects.all(),
        label=_('Video Language'),
        required=False
    )

    class Meta:
        model = CourseRun
        fields = (
            'length', 'transcript_languages', 'language', 'min_effort', 'max_effort', 'target_content', 'pacing_type',
            'video_language', 'staff', 'start', 'end', 'is_xseries', 'xseries_name', 'is_professional_certificate',
            'professional_certificate_name', 'is_micromasters', 'micromasters_name', 'lms_course_id',
            'enrollment_start', 'enrollment_end',
        )

    def save(self, commit=True, course=None, changed_by=None):  # pylint: disable=arguments-differ
        course_run = super(CourseRunForm, self).save(commit=False)

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

        instance = getattr(self, 'instance', None)
        # If `lms_course_id` is none in `cleaned_data` and user is not project coordinator
        # return actual value of the instance, it will prevent `lms_course_id` from getting blanked.
        if instance and instance.pk and hasattr(self, 'is_project_coordinator') and not self.is_project_coordinator:
            return instance.lms_course_id

        return None

    def clean(self):
        cleaned_data = self.cleaned_data
        min_effort = cleaned_data.get('min_effort')
        max_effort = cleaned_data.get('max_effort')
        start = cleaned_data.get('start')
        end = cleaned_data.get('end')
        is_xseries = cleaned_data.get('is_xseries')
        xseries_name = cleaned_data.get('xseries_name')
        is_micromasters = cleaned_data.get('is_micromasters')
        micromasters_name = cleaned_data.get('micromasters_name')
        is_professional_certificate = cleaned_data.get('is_professional_certificate')
        professional_certificate_name = cleaned_data.get('professional_certificate_name')

        if start and end and start >= end:
            self.add_error('start', _('The start date must occur before the end date.'))

        if min_effort and max_effort and min_effort >= max_effort:
            self.add_error('min_effort', _('Minimum effort must be less than maximum effort.'))

        if is_xseries and not xseries_name:
            self.add_error('xseries_name', _('Please provide the name of the associated XSeries.'))

        if is_micromasters and not micromasters_name:
            self.add_error('micromasters_name', _('Please provide the name of the associated MicroMasters.'))

        if is_professional_certificate and not professional_certificate_name:
            self.add_error('professional_certificate_name',
                           _('Please provide the name of the associated Professional Certificate program.'))

        enrollment_start = cleaned_data.get('enrollment_start')
        if enrollment_start:
            if start and enrollment_start > start:
                self.add_error('enrollment_start',
                               _('The enrollment start date must occur on or before the course start date.'))
        else:
            cleaned_data['enrollment_start'] = start

        enrollment_end = cleaned_data.get('enrollment_end')
        if enrollment_end:
            if end and enrollment_end > end:
                self.add_error('enrollment_end',
                               _('The enrollment end date must occur on or after the course end date.'))
        else:
            cleaned_data['enrollment_end'] = end

        return cleaned_data

    def __init__(self, *args, **kwargs):
        self.is_project_coordinator = kwargs.pop('is_project_coordinator', None)
        super(CourseRunForm, self).__init__(*args, **kwargs)
        if not self.is_project_coordinator:
            self.fields['lms_course_id'].widget = forms.HiddenInput()


class SeatForm(BaseForm):
    def __init__(self, *args, **kwargs):
        super(SeatForm, self).__init__(*args, **kwargs)

        field_classes = 'field-input input-select'

        if 'type' in self.errors:
            field_classes = '{} has-error'.format(field_classes)

        self.fields['type'].widget.attrs = {'class': field_classes}

    TYPE_CHOICES = [
        ('', _('Choose enrollment track')),
        (Seat.AUDIT, _('Audit only')),
        (Seat.VERIFIED, _('Verified')),
        (Seat.PROFESSIONAL, _('Professional education')),
        (Seat.CREDIT, _('Credit')),
    ]

    type = forms.ChoiceField(choices=TYPE_CHOICES, required=False, label=_('Enrollment Track'))
    credit_price = forms.DecimalField(max_digits=6, decimal_places=2, required=False, initial=0.00)

    class Meta:
        fields = ('price', 'type', 'credit_price', 'course_run', 'upgrade_deadline',)
        model = Seat
        widgets = {
            'course_run': forms.HiddenInput(),
        }

    def save(self, commit=True):
        # When seat is save make sure its prices and others fields updated accordingly.
        seat = super(SeatForm, self).save(commit=False)
        if seat.type in [Seat.HONOR, Seat.AUDIT]:
            seat.price = 0.00
            seat.upgrade_deadline = None
            self.reset_credit_to_default(seat)
        if seat.type == Seat.VERIFIED:
            self.reset_credit_to_default(seat)
        if seat.type in [Seat.PROFESSIONAL, Seat.NO_ID_PROFESSIONAL]:
            seat.upgrade_deadline = None
            self.reset_credit_to_default(seat)

        if commit:
            seat.save()

        return seat

    def clean(self):
        cleaned_data = super().clean()
        price = cleaned_data.get('price')
        credit_price = cleaned_data.get('credit_price')
        seat_type = cleaned_data.get('type')

        if seat_type and seat_type != Seat.AUDIT and not price:
            self.add_error('price', _('Please specify a price.'))

        if seat_type == Seat.CREDIT and not credit_price:
            self.add_error('credit_price', _('Please specify a price for credit.'))

        if not cleaned_data.get('upgrade_deadline'):
            course_run = cleaned_data.get('course_run')

            if course_run:
                cleaned_data['upgrade_deadline'] = course_run.end - datetime.timedelta(days=10)

        return cleaned_data

    def reset_credit_to_default(self, seat):
        seat.credit_provider = ''
        seat.credit_hours = None
        seat.credit_price = 0


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
                raise ValidationError(_("Invalid course key."))

            return lms_course_id

        return None


class AdminImportCourseForm(forms.Form):
    start_id = forms.IntegerField(min_value=1, label='This course id will import.')

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
