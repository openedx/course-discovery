from waffle.models import Switch


def toggle_switch(name, active=True):
    """
    Activate or deactivate a feature switch. The switch is created if it does not exist.

    Arguments:
        name (str): name of the switch to be toggled.

    Keyword Arguments:
        active (bool): Whether the switch should be on or off.

    Returns:
        Switch: Waffle Switch
    """
    switch, __ = Switch.objects.get_or_create(name=name, defaults={'active': active})
    switch.active = active
    switch.save()

    return switch
