import factory

from course_discovery.apps.base.models import User

USER_PASSWORD = 'password'


class UserFactory(factory.DjangoModelFactory):
    username = factory.Sequence(lambda n: 'user_%d' % n)
    password = factory.PostGenerationMethodCall('set_password', USER_PASSWORD)
    is_active = True
    is_superuser = False
    is_staff = False

    class Meta:
        model = User
