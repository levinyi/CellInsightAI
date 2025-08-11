from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import OrganizationViewSet, UserViewSet, UserProfileViewSet, MembershipViewSet
from .views import login_view, logout_view, demo_login_view

try:
    from rest_framework_simplejwt.views import (
        TokenObtainPairView,
        TokenRefreshView,
    )
    has_jwt = True
except Exception:
    has_jwt = False

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet)
router.register(r'users', UserViewSet)
router.register(r'profiles', UserProfileViewSet)
router.register(r'memberships', MembershipViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('demo-login/', demo_login_view, name='demo_login'),
]

if has_jwt:
    urlpatterns += [
        path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    ]