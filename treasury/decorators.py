from functools import wraps
from django.shortcuts import redirect
from django.urls import reverse
import urllib.parse


def treasury_admin_required(view_func):
    """
    Decorator for views that require the Treasury Admin PIN / password.
    Checks if request.session has 'treasury_admin_authenticated' == True or request.user.is_authenticated.
    If not authenticated, redirects to the /treasury/unlock/ page with next URL.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated or request.session.get('treasury_admin_authenticated'):
            return view_func(request, *args, **kwargs)

        next_url = request.get_full_path()
        unlock_url = reverse('treasury_unlock')
        return redirect(f"{unlock_url}?next={urllib.parse.quote(next_url)}")

    return _wrapped_view
