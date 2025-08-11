"""
ASGI config for bioai_platform project.
"""
import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from django.urls import path
from apps.steps.consumers import TaskConsumer
from apps.common.ws_auth import JWTAuthMiddleware

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bioai_platform.settings')

django_asgi_app = get_asgi_application()

websocket_urlpatterns = [
    path('ws/tasks/<uuid:id>', TaskConsumer.as_asgi()),
    path('ws/tasks/<str:id>', TaskConsumer.as_asgi()),  # fallback
    path('ws/tasks/demo', TaskConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
