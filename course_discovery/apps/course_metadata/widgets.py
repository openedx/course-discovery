from dal import autocomplete
from django import forms


class AdminSelect2MediaMixin:
    """
    Load admin jQuery into the global namespace before DAL Select2 assets.

    Django 5.x keeps admin jQuery under ``django.jQuery``. DAL's Select2 assets and
    some of our legacy admin scripts still expect a global ``window.jQuery``/``$``.
    """

    @property
    def media(self):
        return forms.Media(js=(
            'admin/js/jquery.init.js',
            'js/admin_jquery_ui_bridge.js',
        )) + super().media


class AdminModelSelect2(AdminSelect2MediaMixin, autocomplete.ModelSelect2):
    pass


class SortedModelSelect2Multiple(AdminSelect2MediaMixin, autocomplete.ModelSelect2Multiple):
    def optgroups(self, name, value, attrs=None):
        """
        Return a sorted list of optgroups for this widget.

        This is a simplified version of Django's version. The big difference is that we keep the results sorted.
        """
        selected = super().optgroups(name, value, attrs)

        ordered = []
        for value_id in value:
            for item in selected:
                if value_id == str(item[1][0]['value']):
                    ordered.append(item)
                    break
        return ordered
