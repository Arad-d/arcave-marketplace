"""Bind custom seller sessions to the current seller password."""

from collections.abc import Callable
from functools import wraps

from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.crypto import constant_time_compare

from .models import ShopOwner


class ShopOwnerSessionMiddleware:
    """Reject deleted sellers, stale sessions, and mixed customer/seller identities."""

    def __init__(self, get_response: Callable) -> None:
        """Store the next request handler."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Validate the seller session before any protected view runs."""
        request.shop_owner = None
        owner_id = request.session.get("shop_owner_id")
        if owner_id:
            owner = ShopOwner.objects.filter(pk=owner_id).first()
            stored_hash = request.session.get("shop_owner_auth_hash", "")
            if (
                owner is None
                or request.user.is_authenticated
                or not constant_time_compare(stored_hash, owner.get_session_auth_hash())
            ):
                logout(request)
            else:
                request.shop_owner = owner
        return self.get_response(request)


def shop_owner_required(view: Callable) -> Callable:
    """Require a seller identity validated by the session middleware."""

    @wraps(view)
    def wrapped(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        """Redirect unauthenticated or stale seller sessions to login."""
        if request.shop_owner is None:
            return redirect("shop_owner_login")
        return view(request, *args, **kwargs)

    return wrapped
