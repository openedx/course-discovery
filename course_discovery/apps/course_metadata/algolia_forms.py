
from django import forms

from course_discovery.apps.course_metadata.algolia_models import SearchDefaultResultsConfiguration
from course_discovery.apps.course_metadata.widgets import SortedModelSelect2Multiple


class SearchDefaultResultsConfigurationForm(forms.ModelForm):
    class Meta:
        model = SearchDefaultResultsConfiguration
        fields = '__all__'

        widgets = {
            # TODO: make this sortable as well (debug sortable-select)
            'courses': SortedModelSelect2Multiple(
                url='admin_metadata:course-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                },
            ),
            'programs': SortedModelSelect2Multiple(
                url='admin_metadata:program-autocomplete',
                attrs={
                    'data-minimum-input-length': 3,
                    'class': 'sortable-select',
                }
            ),
        }
