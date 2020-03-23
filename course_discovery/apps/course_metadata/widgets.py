from itertools import chain

from dal import autocomplete


class SortedModelSelect2Multiple(autocomplete.ModelSelect2Multiple):
    def optgroups(self, name, value, attrs=None):
        """
        Return a sorted list of optgroups for this widget.

        This is a simplified version of Django's version. The big difference is that we keep the results sorted and
        only support one main group (because that's all we need right now).
        """
        selected = []
        unselected = []
        for index, (option_value, option_label) in enumerate(chain(self.choices)):
            is_selected = str(option_value) in value
            subgroup = [self.create_option(name, option_value, option_label, is_selected, index, attrs=attrs)]
            item = (None, subgroup, index)
            if is_selected:
                selected.append(item)
            else:
                unselected.append(item)

        ordered = []
        for value_id in value:
            for item in selected:
                if value_id == str(item[1][0]['value']):
                    ordered.append(item)
                    break

        return ordered + unselected
