from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import ugettext as _


def api_docs_permission_denied_handler(request):
    """
    Permission denied handler for calls to the API documentation.

    Args:
        request (Request): Original request to the view the documentation

    Raises:
        PermissionDenied: The user is not authorized to view the API documentation.

    Returns:
        HttpResponseRedirect: Redirect to the login page if the user is not logged in. After a
            successful login, the user will be redirected back to the original path.
    """
    if request.user and request.user.is_authenticated():
        raise PermissionDenied(_('You are not permitted to access the API documentation.'))

    login_url = '{path}?next={next}'.format(path=reverse('login'), next=request.path)
    return redirect(login_url, permanent=False)
