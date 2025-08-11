import json
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Organization, UserProfile
from .serializers import UserSerializer

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    data = request.data or {}
    username = data.get('username')
    password = data.get('password')
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({'detail': 'Invalid credentials'}, status=401)
    login(request, user)
    return Response(UserSerializer(user).data)

@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    logout(request)
    return Response({'ok': True})

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def demo_login_view(request):
    User = get_user_model()
    user, _ = User.objects.get_or_create(username='demo', defaults={'email': 'demo@example.com'})
    # Ensure profile and organization assignment
    org, _ = Organization.objects.get_or_create(name='Demo Org', defaults={'description': 'Default demo organization'})
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user, organization=org, role='viewer')
    else:
        if not profile.organization:
            profile.organization = org
            profile.save(update_fields=['organization'])
    # Log in without password (demo only)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return Response(UserSerializer(user).data)