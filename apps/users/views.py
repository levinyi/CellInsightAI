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
from apps.projects.models import AuditLog

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    data = request.data or {}
    username_or_email = data.get('username') or data.get('email')
    password = data.get('password')
    user = None
    # Try username first, then email fallback
    user = authenticate(request, username=username_or_email, password=password)
    if user is None and username_or_email:
        try:
            User = get_user_model()
            u = User.objects.filter(email__iexact=username_or_email).first()
            if u:
                user = authenticate(request, username=u.username or u.email, password=password)
        except Exception:
            user = None
    if user is None:
        return Response({'detail': 'Invalid credentials'}, status=401)
    login(request, user)
    # Audit
    try:
        AuditLog.objects.create(
            user=user,
            action_type='execute',
            object_type='Auth',
            object_id=user.id,
            changes={'event': 'login'},
            metadata={'ip': request.META.get('REMOTE_ADDR')},
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
    except Exception:
        pass
    return Response(UserSerializer(user).data)

@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    user = request.user if request.user.is_authenticated else None
    logout(request)
    try:
        AuditLog.objects.create(
            user=user,
            action_type='execute',
            object_type='Auth',
            object_id=user.id if user else None,
            changes={'event': 'logout'},
            metadata={'ip': request.META.get('REMOTE_ADDR')},
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
    except Exception:
        pass
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