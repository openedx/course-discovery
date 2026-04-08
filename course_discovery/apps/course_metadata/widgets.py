from dal import autocomplete


class SortedModelSelect2Multiple(autocomplete.ModelSelect2Multiple):
    def optgroups(self, name, value, attrs=None):
        """
        Return a sorted list of optgroups for this widget.

        This is a simplified version of Django's version. The big difference is that we keep the results sorted.
        """
        selected = super().optgroups(name, value, attrs)

        # First, add selected items in the order they appear in value
        ordered = []
        added_ids = set()
        for value_id in value:
            for item in selected:
                # item is a tuple: (group_name, [{'value': ..., 'label': ..., ...}], index)
                if item[1] and len(item[1]) > 0:
                    if value_id == str(item[1][0]['value']):
                        ordered.append(item)
                        added_ids.add(value_id)
                        break
        # Then, add all non-selected items to show them when searching/browsing
        for item in selected:
            if item[1] and len(item[1]) > 0:
                item_value = str(item[1][0]['value'])
                if item_value not in added_ids:
                    ordered.append(item)
        return ordered

    @property
    def media(self):
        return super().media

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # Ensure the widget has the proper class for Select2 initialization
        if 'widget' in context:
            if 'attrs' not in context['widget']:
                context['widget']['attrs'] = {}
            # Add data-role attribute for django-autocomplete-light
            if 'data-role' not in context['widget']['attrs']:
                context['widget']['attrs']['data-role'] = 'autocomplete'
        return context
