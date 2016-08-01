"""Publisher Wrapper Classes"""


class BaseWrapper(object):
    def __init__(self, wrapped_obj):
        self.wrapped_obj = wrapped_obj

    def __getattr__(self, attr):
        return self.wrapped_obj.__getattribute__(attr)


class CourseRunWrapper(BaseWrapper):
    """Decorator for the ``CourseRun`` model."""
    @property
    def title(self):
        return self.wrapped_obj.course.title

    @property
    def partner(self):
        return '/'.join([org.key for org in self.wrapped_obj.course.owners.all()])
