"""
Course publisher forms.
"""
from django import forms

from course_discovery.apps.publisher.models import Course, CourseRun, Seat


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


class CourseRunForm(BaseCourseForm):
    """ Course Run Form. """

    class Meta:
        model = CourseRun
        fields = '__all__'


class SeatForm(BaseCourseForm):
    """ Course Seat Form. """

    class Meta:
        model = Seat
        fields = '__all__'
        exclude = ('currency',)

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
