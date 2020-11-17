from django.utils.translation import ugettext as _


class EditableAndQUnsupported(Exception):
    """
    This Exception exists because we were witnessing weird behavior when both editable=1 and
    a q parameter is defined (test passing locally, but consistently failing on CI. Also manual
    smoke testing giving incorrect results when both were defined). It is possible to dig into this
    and figure out how to support it, but it was decided that since we do not have a use case yet,
    we would disallow it for now.
    """
    def __init__(self):
        super().__init__(_('Specifying both editable=1 and a q parameter is not supported.'))
