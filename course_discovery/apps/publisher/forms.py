"""
Course publisher forms.
"""
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.forms.utils import ErrorList
from django.utils.translation import ugettext_lazy as _
from guardian.shortcuts import get_perms

from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.models import Person, Organization
from course_discovery.apps.publisher.models import Course, CourseRun, Seat, User, OrganizationExtension


class UserModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name()


class BaseCourseForm(forms.ModelForm):
    """ Base Course Form. """

    def __init__(self, *args, **kwargs):
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
        queryset=Organization.objects.filter(organization_extension__organization_id__isnull=False),
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

    class Meta(CourseForm.Meta):
        model = Course
        fields = (
            'title', 'number', 'short_description', 'full_description',
            'expected_learnings', 'level_type', 'primary_subject', 'secondary_subject',
            'tertiary_subject', 'prerequisites', 'level_type', 'image', 'team_admin',
            'level_type', 'organization', 'is_seo_review', 'keywords',
        )

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        if organization:
            org_extension = OrganizationExtension.objects.get(organization=organization)
            self.declared_fields['team_admin'].queryset = User.objects.filter(groups__name=org_extension.group)

        super(CustomCourseForm, self).__init__(*args, **kwargs)


class UpdateCourseForm(BaseCourseForm):
    """ Course form to update specific fields for already created course. """

    number = forms.CharField(label=_('Course Number'), required=True)
    team_admin = forms.ModelChoiceField(queryset=User.objects.all(), required=True)

    class Meta:
        model = Course
        fields = ('number', 'team_admin',)

    def save(self, commit=True, changed_by=None):   # pylint: disable=arguments-differ
        course = super(UpdateCourseForm, self).save(commit=False)

        if changed_by:
            course.changed_by = changed_by

        if commit:
            course.save()

        return course


class CourseRunForm(BaseCourseForm):
    """ Course Run Form. """

    class Meta:
        model = CourseRun
        fields = '__all__'
        exclude = ('state', 'changed_by',)


class CustomCourseRunForm(CourseRunForm):
    """ Course Run Form. """

    contacted_partner_manager = forms.ChoiceField(
        label=_('Contacted PM'),
        widget=forms.RadioSelect,
        choices=((True, _("Yes")), (False, _("No"))),
        required=True
    )

    start = forms.DateTimeField(label=_('Course start date'), required=True)
    end = forms.DateTimeField(label=_('Course end date'), required=True)
    staff = forms.ModelMultipleChoiceField(
        queryset=Person.objects.all(), widget=forms.SelectMultiple, required=False
    )
    target_content = forms.BooleanField(
        widget=forms.RadioSelect(
            choices=((1, _("Yes")), (0, _("No")))), initial=0, required=False
    )
    pacing_type = forms.ChoiceField(
        label=_('Pace'),
        widget=forms.RadioSelect,
        choices=CourseRunPacing.choices,
        required=True
    )

    class Meta(CourseRunForm.Meta):
        fields = (
            'length', 'transcript_languages', 'language', 'min_effort', 'max_effort',
            'contacted_partner_manager', 'target_content', 'pacing_type', 'video_language',
            'staff', 'start', 'end',
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

    type = forms.ChoiceField(choices=TYPE_CHOICES, required=True, label=_('Seat Type'))

    class Meta(SeatForm.Meta):
        fields = ('price', 'type')


class OrganizationExtensionAdminForm(forms.ModelForm):
    permissions_list = [
        'publisher_view_course', 'publisher_edit_course',
        'publisher_edit_course_run', 'publisher_view_course_run'
    ]
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.filter(codename__in=permissions_list),
        widget=FilteredSelectMultiple(_('Permissions'), is_stacked=False),
        required=False
    )

    class Meta:
        model = OrganizationExtension
        fields = '__all__'

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None, initial=None, error_class=ErrorList,
                 label_suffix=':', empty_permitted=False, instance=None):
        super(OrganizationExtensionAdminForm, self).__init__(data, files, auto_id, prefix, initial,
                                                             error_class, label_suffix, empty_permitted, instance)

        # Content type check is critical to make sure only valid permissions appear.
        content_type = ContentType.objects.get_for_model(OrganizationExtension)
        self.fields['permissions'].queryset = Permission.objects.filter(
            content_type=content_type, codename__in=self.permissions_list
        )
        if instance:
            self.fields['permissions'].initial = Permission.objects.filter(
                content_type=content_type, codename__in=get_perms(instance.group, instance)
            ).values_list('id', flat=True)
