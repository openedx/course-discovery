from django import forms

from course_discovery.apps.publisher.models import Course, CourseRun


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
            if isinstance(field, forms.ModelMultipleChoiceField):
                field_classes = ''

            if field_name in self.errors:
                field_classes = '{} has-error'.format(field_classes)

            field.widget.attrs['class'] = field_classes


class CourseForm(BaseCourseForm):
    """ Course Form. """

    class Meta:
        model = Course
        fields = '__all__'
        widgets = {
            'organizations': forms.CheckboxSelectMultiple()
        }


class CourseRunForm(BaseCourseForm):
    """ Course Run Form. """

    class Meta:
        model = CourseRun
        fields = '__all__'
        exclude = ('course',)
        widgets = {
            'transcript_languages': forms.CheckboxSelectMultiple(),
            'sponsor': forms.CheckboxSelectMultiple()
        }
