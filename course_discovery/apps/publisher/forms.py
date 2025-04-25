import html
import logging

import waffle
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
from course_discovery.apps.publisher.choices import CourseRunStateChoices, PublisherUserRole
from course_discovery.apps.publisher.constants import PUBLISHER_CREATE_AUDIT_SEATS_FOR_VERIFIED_COURSE_RUNS
from course_discovery.apps.publisher.mixins import LanguageModelSelect2Multiple, get_user_organizations
from course_discovery.apps.publisher.models import (
    Course, CourseEntitlement, CourseRun, CourseRunState, CourseState, CourseUserRole, OrganizationExtension,
    OrganizationUserRole, PublisherUser, Seat, User
)
from course_discovery.apps.publisher.utils import VALID_CHARS_IN_COURSE_NUM_AND_ORG_KEY, is_internal_user
from course_discovery.apps.publisher.validators import validate_text_count

logger = logging.getLogger(__name__)


class UserModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.username


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
    title = forms.CharField(label=_('Course Title'), required=True)
    number = forms.CharField(
        label=_('Course Number'), required=True,
        validators=[validate_text_count(max_length=50)]
    )

    class Meta:
        model = Course
        fields = (
            'title',
        )

    def __init__(self, *args, **kwargs):
        # In case of edit mode pre-populate the drop-downs
        user = kwargs.pop('user', None)
        super(CourseForm, self).__init__(*args, **kwargs)

    def clean_title(self):
        """
        Convert all named and numeric character references in the string
        to the corresponding unicode characters
        """
        return html.unescape(self.cleaned_data.get('title'))

    def clean_number(self):
        """
        Validate that number doesn't consist of any special characters other than period, underscore or hyphen
        """
        number = self.cleaned_data.get('number')
        if not VALID_CHARS_IN_COURSE_NUM_AND_ORG_KEY.match(number):
            raise ValidationError(_('Please do not use any spaces or special characters other than period, '
                                    'underscore or hyphen.'))
        return number

    def clean(self):
        cleaned_data = self.cleaned_data
        title = cleaned_data.get('title')
        number = cleaned_data.get('number')
        instance = getattr(self, 'instance', None)
        if not instance.pk:
            if Course.objects.filter(title=title).exists():
                raise ValidationError({'title': _('This course title already exists')})
            if Course.objects.filter(number=number).exists():
                raise ValidationError({'number': _('This course number already exists')})
        return cleaned_data


class CourseSearchForm(forms.Form):
    """ Course Type ahead Search Form. """
    course = forms.ModelChoiceField(
        label=_('Find Course'),
        queryset=Course.objects.none(),
        widget=autocomplete.ModelSelect2(
            url='publisher:api:course-autocomplete',
            attrs={
                'data-minimum-input-length': 3,
            }
        ),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['course'].queryset = PublisherUser.get_courses(user)


class CourseRunForm(BaseForm):
    start = forms.DateTimeField(label=_('Course Start Date'), required=True)
    end = forms.DateTimeField(label=_('Course End Date'), required=True)
    pacing_type = forms.ChoiceField(
        label=_('Pacing'),
        widget=forms.RadioSelect,
        choices=CourseRunPacing.choices,
        required=True
    )
    lms_course_id = forms.CharField(label=_('Studio URL'), required=False)

    class Meta:
        model = CourseRun
        fields = (
            'pacing_type',
            'start', 'end',
            'lms_course_id',
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
                raise ValidationError('Invalid course key.')

            return lms_course_id

        instance = getattr(self, 'instance', None)
        # If `lms_course_id` is none in `cleaned_data` and user is not project coordinator
        # return actual value of the instance, it will prevent `lms_course_id` from getting blanked.
        if instance and instance.pk and hasattr(self, 'is_project_coordinator') and not self.is_project_coordinator:
            return instance.lms_course_id

        return None

    def clean(self):
        cleaned_data = self.cleaned_data
        start = cleaned_data.get('start')
        end = cleaned_data.get('end')
        if start and end and start > end:
            raise ValidationError({'start': _('Start date cannot be after the End date')})

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

    type = forms.ChoiceField(choices=TYPE_CHOICES, required=True, label=_('Enrollment Track'))
    price = forms.DecimalField(max_digits=6, decimal_places=2, required=False, initial=0.00)
    credit_price = forms.DecimalField(max_digits=6, decimal_places=2, required=False, initial=0.00)

    class Meta:
        fields = ('price', 'type', 'credit_price')
        model = Seat

    def save(self, commit=True, course_run=None, changed_by=None):  # pylint: disable=arguments-differ
        """Saves the seat for a particular course run."""
        # Background -- EDUCATOR-2337 (Should be removed once the data is consistent)
        self.validate_and_remove_seats(course_run)

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

        if course_run:
            seat.course_run = course_run

        if changed_by:
            seat.changed_by = changed_by

        if commit:
            seat.save()

            if waffle.switch_is_active(PUBLISHER_CREATE_AUDIT_SEATS_FOR_VERIFIED_COURSE_RUNS):
                course_run = seat.course_run
                audit_seats = course_run.seats.filter(type=Seat.AUDIT)

                # Ensure that course runs with a verified seat always have an audit seat
                if seat.type in Seat.PAID_AND_AUDIT_APPLICABLE_SEATS:
                    if not audit_seats.exists():
                        course_run.seats.create(type=Seat.AUDIT, price=0, upgrade_deadline=None)
                        logger.info('Created audit seat for course run [%d]', course_run.id)
                elif seat.type != Seat.AUDIT:
                    # Ensure that professional course runs do NOT have an audit seat
                    count = audit_seats.count()
                    audit_seats.delete()
                    logger.info('Removed [%d] audit seat for course run [%d]', count, course_run.id)

        return seat

    def clean(self):
        price = self.cleaned_data.get('price')
        credit_price = self.cleaned_data.get('credit_price')
        seat_type = self.cleaned_data.get('type')

        if seat_type != Seat.AUDIT and price and price < 0.01:
            self.add_error('price', _('Price must be greater than or equal to 0.01'))

        if seat_type in [Seat.PROFESSIONAL, Seat.VERIFIED, Seat.CREDIT] and not price:
            self.add_error('price', _('Only audit seat can be without price.'))

        if seat_type == Seat.CREDIT and not credit_price:
            self.add_error('credit_price', _('Only audit seat can be without price.'))

        return self.cleaned_data

    def reset_credit_to_default(self, seat):
        seat.credit_provider = ''
        seat.credit_hours = None
        seat.credit_price = 0.00

    def validate_and_remove_seats(self, course_run):
        """
        Remove course run seats if the data is bogus

        Temporary call to remove the duplicate course run seats -- EDUCATOR-2337
        Background: There was a bug in the system, where course run seats being duplicated,
        in order to cleanup, remove all the existing seats.
        """
        if not course_run:
            return
        all_course_run_seats = course_run.seats.all()
        all_course_run_seats_count = all_course_run_seats.count()
        seats_data_is_bogus = all_course_run_seats_count > 2
        if seats_data_is_bogus:
            all_course_run_seats.delete()
            logger.info('Removed bogus course run [%d] seats [%d]', course_run.id, all_course_run_seats_count)


class CourseEntitlementForm(BaseForm):
    AUDIT_MODE = 'audit'
    VERIFIED_MODE = CourseEntitlement.VERIFIED
    PROFESSIONAL_MODE = CourseEntitlement.PROFESSIONAL
    CREDIT_MODE = 'credit'

    # Modes for which we should not create entitlements.
    NOOP_MODES = [AUDIT_MODE, CREDIT_MODE]

    # Modes for which we should create an entitlement.
    PAID_MODES = [VERIFIED_MODE, PROFESSIONAL_MODE]

    MODE_CHOICES = [
        (AUDIT_MODE, _('Audit only')),
        (VERIFIED_MODE, _('Verified')),
        (PROFESSIONAL_MODE, _('Professional education')),
        (CREDIT_MODE, _('Credit')),
    ]

    mode = forms.ChoiceField(choices=MODE_CHOICES, required=False, label=_('Enrollment Track'),
                             initial=VERIFIED_MODE)
    price = forms.DecimalField(max_digits=6, decimal_places=2, required=False, initial=0.00)

    class Meta:
        fields = ('mode', 'price')
        model = CourseEntitlement

    def __init__(self, *args, **kwargs):
        include_blank_mode = kwargs.pop('include_blank_mode', False)
        super(CourseEntitlementForm, self).__init__(*args, **kwargs)

        if include_blank_mode:
            self.fields['mode'].choices = [('', '')] + self.MODE_CHOICES

    def save(self, commit=True, course=None):  # pylint: disable=arguments-differ
        entitlement = super(CourseEntitlementForm, self).save(commit=False)

        if course:
            entitlement.course = course

        if commit:
            entitlement.save()

        return entitlement

    def clean_mode(self):
        mode = self.cleaned_data['mode']
        if mode in self.NOOP_MODES:
            # Allow 'audit'/'credit' to be submitted as valid modes, but don't save an entitlement for them.
            return None
        else:
            return mode

    def clean(self):
        cleaned_data = super().clean()
        mode = cleaned_data.get('mode')
        price = cleaned_data.get('price')

        # If there's no mode there should also be no price
        if not mode:
            cleaned_data['price'] = None

        if mode in self.PAID_MODES and price and price < 0.01:
            self.add_error('price', _('Price must be greater than or equal to 0.01'))
        if mode in self.PAID_MODES and not price:
            self.add_error('price', _('Price is required.'))

        return cleaned_data


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
                _('Please create {} course user role before assigning it owner role'.format(owner_role))
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
