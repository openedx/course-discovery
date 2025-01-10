from dal import autocomplete


class SortedModelSelect2Multiple(autocomplete.ModelSelect2Multiple):
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
