"""
Course publisher forms.
"""
from django import forms
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.models import Person
from course_discovery.apps.publisher.models import Course, CourseRun, Seat, User, GroupOrganization


class BaseCourseForm(forms.ModelForm):
    """ Base Course Form. """

    def __init__(self, *args, **kwargs):
        super(BaseCourseForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field_classes = 'field-input input-text'
            if isinstance(field, forms.Textarea):
                field_classes = 'field-textarea input-textarea'
            if isinstance(field, (forms.ModelChoiceField, forms.TypedChoiceField,)):
                field_classes = 'field-input input-select'
            if isinstance(field, forms.BooleanField):
                field_classes = 'field-input input-checkbox'
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

    organization = forms.ModelChoiceField(queryset=GroupOrganization.objects.all(), required=True)
    title = forms.CharField(label=_('Course Title'), required=True)
    number = forms.CharField(label=_('Course Number'), required=True)
    team_admin = forms.ModelChoiceField(queryset=User.objects.filter(is_staff=True), required=True)

    class Meta(CourseForm.Meta):
        model = Course
        fields = (
            'title', 'number', 'short_description', 'full_description',
            'expected_learnings', 'level_type', 'primary_subject', 'secondary_subject',
            'tertiary_subject', 'prerequisites', 'level_type', 'image', 'team_admin',
            'level_type', 'organization', 'is_seo_review', 'keywords',
        )


class UpdateCourseForm(BaseCourseForm):
    """ Course form to update specific fields for already created course. """

    number = forms.CharField(label=_('Course Number'), required=True)
    team_admin = forms.ModelChoiceField(queryset=User.objects.filter(is_staff=True), required=True)

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

    contacted_partner_manager = forms.BooleanField(
        widget=forms.RadioSelect(choices=((1, _("Yes")), (0, _("No")))), initial=0, required=False
    )
    start = forms.DateTimeField(label=_('Course start date'), required=True)
    end = forms.DateTimeField(label=_('Course end date'), required=False)
    staff = forms.ModelMultipleChoiceField(
        queryset=Person.objects.all(), widget=forms.SelectMultiple, required=False
    )
    target_content = forms.BooleanField(
        widget=forms.RadioSelect(
            choices=((1, _("Yes")), (0, _("No")))), initial=0, required=False
    )
    is_self_paced = forms.BooleanField(label=_('Yes, course will be Self-Paced'), required=False)

    class Meta(CourseRunForm.Meta):
        fields = (
            'length', 'transcript_languages', 'language', 'min_effort', 'max_effort',
            'contacted_partner_manager', 'target_content', 'pacing_type',
            'video_language', 'staff', 'start', 'end', 'is_self_paced',
        )

    def clean(self):
        super(CustomCourseRunForm, self).clean()
        self.cleaned_data['pacing_type'] = CourseRunPacing.Self if self.cleaned_data['is_self_paced']\
            else CourseRunPacing.Instructor

        return self.cleaned_data

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

        if seat_type in [Seat.PROFESSIONAL, Seat.NO_ID_PROFESSIONAL, Seat.VERIFIED, Seat.CREDIT] \
                and not price:
            self.add_error('price', _('Only honor/audit seats can be without price.'))

        return self.cleaned_data


class CustomSeatForm(SeatForm):
    """ Course Seat Form. """

    class Meta(SeatForm.Meta):
        fields = ('price', 'type')
