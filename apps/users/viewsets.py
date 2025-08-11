from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from .models import Organization, UserProfile
from .serializers import OrganizationSerializer, UserSerializer, UserProfileSerializer

class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.select_related('user', 'organization').all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        # Filter by current user's org if set (basic multi-tenant isolation)
        org = getattr(self.request.user, 'profile', None) and self.request.user.profile.organization
        if org:
            return qs.filter(organization=org)
        return qs

    def perform_update(self, serializer):
        # Only allow user to update own profile unless admin
        profile = self.get_object()
        is_admin = getattr(self.request.user.profile, 'role', '') == 'admin'
        if profile.user != self.request.user and not is_admin:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        serializer.save()