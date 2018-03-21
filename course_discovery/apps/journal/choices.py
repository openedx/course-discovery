from django.utils.translation import ugettext_lazy as _
from djchoices import ChoiceItem, DjangoChoices


class JournalStatus(DjangoChoices):
    Active = ChoiceItem('active', _('Active'))
    Inactive = ChoiceItem('inactive', _('Inactive'))
    Retired = ChoiceItem('retired', _('Retired'))
