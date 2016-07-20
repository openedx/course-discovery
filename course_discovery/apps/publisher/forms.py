from django import forms

from course_discovery.apps.publisher.models import Course, CourseRun


class CourseForm(forms.ModelForm):
    """ Course form."""

    class Meta:
        model = Course
        fields = '__all__'
        exclude = ('organizations',)

    def __init__(self, *args, **kwargs):
        super(CourseForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field_classes = 'field-input input-text'
            if isinstance(field, forms.Textarea):
                field_classes = 'field-textarea input-textarea'
            if isinstance(field, forms.ModelChoiceField):
                field_classes = 'field-input input-select'
            if field_name in self.errors:
                field_classes = '{} has-error'.format(field_classes)
            field.widget.attrs['class'] = field_classes


class CourseRunForm(forms.ModelForm):
    """ Course form."""

    class Meta:
        model = CourseRun
        fields = '__all__'
        exclude = ('course', 'staff',)

    def __init__(self, *args, **kwargs):
        super(CourseRunForm, self).__init__(*args, **kwargs)
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
