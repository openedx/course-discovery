""" Core forms. """
from django import forms
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.core.models import UserThrottleRate


class UserThrottleRateForm(forms.ModelForm):
    """Form for the UserThrottleRate admin."""
    class Meta:
        model = UserThrottleRate
        fields = ('user', 'rate')

    def clean_rate(self):
        rate = self.cleaned_data.get('rate')
        if rate:
            try:
                num, period = rate.split('/')
                int(num)  # Only evaluated for the (possible) side effect of a ValueError
                period_choices = ('second', 'minute', 'hour', 'day')
                if period not in period_choices:
                    # Translators: 'period_choices' is a list of possible values, like ('second', 'minute', 'hour')
                    error_msg = _("period must be one of {period_choices}.").format(period_choices=period_choices)
                    raise forms.ValidationError(error_msg)
            except ValueError:
                error_msg = _("'rate' must be in the format defined by DRF, such as '100/hour'.")
                raise forms.ValidationError(error_msg)
        return rate
