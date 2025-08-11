from urllib.parse import parse_qs
from typing import Callable, Awaitable
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

try:
    from rest_framework_simplejwt.authentication import JWTAuthentication
except Exception:
    JWTAuthentication = None


@database_sync_to_async
def get_user_from_jwt(token: str):
    if not JWTAuthentication:
        return AnonymousUser()
    authenticator = JWTAuthentication()
    try:
        validated = authenticator.get_validated_token(token)
        user = authenticator.get_user(validated)
        return user
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = None
        if "token" in query:
            token_vals = query.get("token")
            token = token_vals[0] if token_vals else None
        if token:
            user = await get_user_from_jwt(token)
            scope["user"] = user
        return await super().__call__(scope, receive, send) 