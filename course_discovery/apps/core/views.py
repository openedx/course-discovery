""" Core views. """
import logging
import uuid

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login
from django.db import DatabaseError, connection, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.views.generic import View

from course_discovery.apps.core.constants import Status

try:
    import newrelic.agent
except ImportError:  # pragma: no cover
    newrelic = None  # pylint: disable=invalid-name

logger = logging.getLogger(__name__)
User = get_user_model()


@transaction.non_atomic_requests
def health(_):
    """Allows a load balancer to verify this service is up.

    Checks the status of the database connection on which this service relies.

    Returns:
        HttpResponse: 200 if the service is available, with JSON data indicating the health of each required service
        HttpResponse: 503 if the service is unavailable, with JSON data indicating the health of each required service

    Example:
        >>> response = requests.get('https://course-discovery.edx.org/health')
        >>> response.status_code
        200
        >>> response.content
        '{"overall_status": "OK", "detailed_status": {"database_status": "OK"}}'
    """
    if newrelic:  # pragma: no cover
        newrelic.agent.ignore_transaction()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        database_status = Status.OK
    except DatabaseError:
        database_status = Status.UNAVAILABLE

    overall_status = Status.OK if (database_status == Status.OK) else Status.UNAVAILABLE

    data = {
        'overall_status': overall_status,
        'detailed_status': {
            'database_status': database_status,
        },
    }

    if overall_status == Status.OK:
        return JsonResponse(data)
    else:
        return JsonResponse(data, status=503)


class AutoAuth(View):
    """Creates and authenticates a new User with superuser permissions.

    If the ENABLE_AUTO_AUTH setting is not True, returns a 404.
    """

    def get(self, request):
        """
        Create a new User.

        Raises Http404 if auto auth is not enabled.
        """
        if not getattr(settings, 'ENABLE_AUTO_AUTH', None):
            raise Http404

        username_prefix = getattr(settings, 'AUTO_AUTH_USERNAME_PREFIX', 'auto_auth_')

        # Create a new user with staff permissions
        username = password = username_prefix + uuid.uuid4().hex[0:20]
        User.objects.create_superuser(username, email=None, password=password)

        # Log in the new user
        user = authenticate(username=username, password=password)
        login(request, user)

        return redirect('/')
