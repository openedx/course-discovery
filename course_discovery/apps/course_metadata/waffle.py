"""
This module contains configuration settings via
waffle switches for the course_metadata app.
"""
import waffle

# Switches
MASTERS_COURSE_MODE_ENABLED = u'masters_course_mode_enabled'


def masters_course_mode_enabled():
    """
    Returns true if the masters_course_mode_enabled waffle flag is on,
    false if it is off.
    """
    return waffle.switch_is_active(MASTERS_COURSE_MODE_ENABLED)
