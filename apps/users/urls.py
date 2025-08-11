from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import OrganizationViewSet, UserViewSet, UserProfileViewSet
from .views import login_view, logout_view, demo_login_view

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet)
router.register(r'users', UserViewSet)
router.register(r'profiles', UserProfileViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('demo-login/', demo_login_view, name='demo_login'),
]