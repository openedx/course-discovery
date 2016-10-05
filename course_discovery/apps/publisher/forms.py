"""
Course publisher forms.
"""
from django.contrib.auth.models import Group
from django import forms
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.course_metadata.models import Person
from course_discovery.apps.publisher.models import Course, CourseRun, Seat, User


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

    class Meta:
        model = Course
        fields = '__all__'
        exclude = ('changed_by',)


class CustomCourseForm(CourseForm):
    """ Course Form. """

    title = forms.CharField(label='Course Title', required=True, max_length=255)
    number = forms.CharField(label='Course Number', required=True, max_length=255)
    institution = forms.ModelChoiceField(queryset=Group.objects.all(), required=True)
    team_admin = forms.ModelChoiceField(queryset=User.objects.filter(is_staff=True), required=True)

    class Meta:
        model = Course
        fields = (
            'title', 'number', 'short_description', 'full_description',
            'expected_learnings', 'level_type', 'primary_subject', 'secondary_subject',
            'tertiary_subject', 'prerequisites', 'level_type', 'image', 'team_admin',
            'level_type', 'institution',
        )
        exclude = ('changed_by',)


class CourseRunForm(BaseCourseForm):
    """ Course Run Form. """

    class Meta:
        model = CourseRun
        fields = '__all__'
        exclude = ('state', 'changed_by',)


class CustomCourseRunForm(CourseRunForm):
    """ Course Run Form. """

    contacted_partner_manager = forms.BooleanField(
        widget=forms.RadioSelect(choices=((1, "Yes"), (0, "No"))), initial=0, required=False
    )
    start = forms.DateTimeField(required=True)
    staff = forms.ModelMultipleChoiceField(
        queryset=Person.objects.all(), widget=forms.SelectMultiple, required=False
    )
    target_content = forms.BooleanField(
        widget=forms.RadioSelect(choices=((1, "Yes"), (0, "No"))), initial=0, required=False
    )

    class Meta:
        model = CourseRun
        fields = (
            'keywords', 'start', 'end', 'length',
            'transcript_languages', 'language', 'min_effort', 'max_effort', 'keywords',
            'contacted_partner_manager', 'target_content', 'pacing_type', 'is_seo_review',
            'video_language', 'staff',
        )


class SeatForm(BaseCourseForm):
    """ Course Seat Form. """

    class Meta:
        model = Seat
        fields = '__all__'
        exclude = ('currency', 'changed_by',)

    def save(self, commit=True):
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

        if commit:
            seat.save()

        return seat


class CustomSeatForm(SeatForm):
    """ Course Seat Form. """

    class Meta:
        model = Seat
        fields = ('price', 'type')

    def clean(self):
        price = self.cleaned_data.get('price')
        seat_type = self.cleaned_data.get('type')

        if seat_type in [Seat.PROFESSIONAL, Seat.NO_ID_PROFESSIONAL, Seat.VERIFIED, Seat.CREDIT] \
                and not price:
            self.add_error('price', _('Only honor/audit seats can be without price.'))

        return self.cleaned_data
