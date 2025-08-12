import json
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Organization, UserProfile, Membership, LoginHistory
from .serializers import UserSerializer
from apps.projects.models import AuditLog

def get_client_ip(request):
    """Get real client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

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
    
    # Get client info for login history
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    if user is None:
        # Record failed login attempt
        try:
            LoginHistory.objects.create(
                user=None,  # No user for failed attempts
                ip_address=ip_address,
                user_agent=user_agent,
                is_successful=False,
                failure_reason='Invalid credentials'
            )
        except Exception:
            pass
        return Response({'detail': 'Invalid credentials'}, status=401)
    
    login(request, user)
    
    # Record successful login
    try:
        LoginHistory.objects.create(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            is_successful=True
        )
    except Exception:
        pass
    
    # Audit
    try:
        AuditLog.objects.create(
            user=user,
            action_type='execute',
            object_type='Auth',
            object_id=user.id,
            changes={'event': 'login'},
            metadata={'ip': ip_address},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass
    return Response(UserSerializer(user).data)

@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    user = request.user if request.user.is_authenticated else None
    ip_address = get_client_ip(request)
    
    # Update login history with logout time
    if user:
        try:
            # Find the most recent login record for this user
            recent_login = LoginHistory.objects.filter(
                user=user, 
                is_successful=True, 
                logout_at__isnull=True
            ).order_by('-login_at').first()
            
            if recent_login:
                from django.utils import timezone
                recent_login.logout_at = timezone.now()
                recent_login.session_duration = recent_login.logout_at - recent_login.login_at
                recent_login.save(update_fields=['logout_at', 'session_duration'])
        except Exception:
            pass
    
    logout(request)
    try:
        AuditLog.objects.create(
            user=user,
            action_type='execute',
            object_type='Auth',
            object_id=user.id if user else None,
            changes={'event': 'logout'},
            metadata={'ip': ip_address},
            ip_address=ip_address,
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
        profile = UserProfile.objects.create(user=user, organization=org, role='scientist')
    else:
        if not profile.organization:
            profile.organization = org
            profile.save(update_fields=['organization'])
        # Update role to scientist if it's currently viewer
        if profile.role == 'viewer':
            profile.role = 'scientist'
            profile.save(update_fields=['role'])
    
    # Ensure membership so org appears in list - also upgrade to scientist
    membership, created = Membership.objects.get_or_create(
        user=user, organization=org, 
        defaults={'role': 'scientist'}
    )
    if not created and membership.role == 'viewer':
        membership.role = 'scientist'
        membership.save(update_fields=['role'])
    
    # Record demo login in history
    ip_address = get_client_ip(request)
    try:
        LoginHistory.objects.create(
            user=user,
            ip_address=ip_address,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            is_successful=True
        )
    except Exception:
        pass
    
    # Log in without password (demo only)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return Response(UserSerializer(user).data)