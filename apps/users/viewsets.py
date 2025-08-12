import secrets
import hashlib
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from .models import Organization, UserProfile, Membership, APIToken, LoginHistory
from .serializers import (
    OrganizationSerializer, UserSerializer, UserProfileSerializer, 
    MembershipSerializer, APITokenSerializer, LoginHistorySerializer
)
from apps.common.permissions import IsOrgAdminOrOwner, RBACByRole
from apps.projects.models import AuditLog

def log_audit(user, action_type, object_type, object_id, changes=None, metadata=None, request=None):
    """Helper function to create audit log entries"""
    ip_address = None
    user_agent = ''
    if request:
        # Extract IP from request
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    AuditLog.objects.create(
        user=user,
        action_type=action_type,
        object_type=object_type,
        object_id=object_id,
        changes=changes or {},
        metadata=metadata or {},
        ip_address=ip_address,
        user_agent=user_agent
    )

class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.filter(is_active=True)
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Organization.objects.none()
        # Organizations where user has a membership, and only active ones
        org_ids = Membership.objects.filter(user=user).values_list('organization_id', flat=True)
        return Organization.objects.filter(id__in=org_ids, is_active=True)

    def get_permissions(self):
        """Dynamic permissions based on action"""
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsOrgAdminOrOwner()]
        return [IsAuthenticated()]

    @transaction.atomic
    def perform_create(self, serializer):
        """Create organization and set creator as owner"""
        organization = serializer.save()
        
        # Create owner membership for creator
        Membership.objects.create(
            user=self.request.user,
            organization=organization,
            role='owner'
        )
        
        # Update user's profile to this new organization
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        profile.organization = organization
        profile.role = 'owner'
        profile.save(update_fields=['organization', 'role'])
        
        # Log audit
        log_audit(
            user=self.request.user,
            action_type='create',
            object_type='Organization',
            object_id=organization.id,
            metadata={'name': organization.name},
            request=self.request
        )

    def perform_update(self, serializer):
        """Log organization updates"""
        old_data = {}
        if self.get_object():
            old_data = OrganizationSerializer(self.get_object()).data
        
        updated_org = serializer.save()
        
        # Log changes
        new_data = OrganizationSerializer(updated_org).data
        changes = {}
        for key in new_data:
            if old_data.get(key) != new_data.get(key):
                changes[key] = {'old': old_data.get(key), 'new': new_data.get(key)}
        
        log_audit(
            user=self.request.user,
            action_type='update',
            object_type='Organization',
            object_id=updated_org.id,
            changes=changes,
            request=self.request
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        """Soft delete organization (deactivate)"""
        # Check if this is the only organization for some users
        sole_members = []
        for membership in instance.memberships.all():
            user_org_count = Membership.objects.filter(user=membership.user).count()
            if user_org_count == 1:
                sole_members.append(membership.user.username)
        
        if sole_members:
            return Response({
                'detail': f'Cannot delete organization. Users would be left without organization: {", ".join(sole_members)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Soft delete
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        
        log_audit(
            user=self.request.user,
            action_type='delete',
            object_type='Organization',
            object_id=instance.id,
            metadata={'name': instance.name, 'soft_delete': True},
            request=self.request
        )

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        """Reactivate a soft-deleted organization (owner only)"""
        org = self.get_object()
        membership = Membership.objects.filter(user=request.user, organization=org).first()
        
        if not membership or membership.role != 'owner':
            return Response({'detail': 'Only owners can reactivate organizations'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        org.is_active = True
        org.save(update_fields=['is_active'])
        
        log_audit(
            user=request.user,
            action_type='update',
            object_type='Organization',
            object_id=org.id,
            metadata={'action': 'reactivate'},
            request=request
        )
        
        return Response({'message': 'Organization reactivated successfully'})

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
        org = getattr(self.request, 'org', None)
        if org:
            return qs.filter(organization=org)
        return qs

    def perform_update(self, serializer):
        # Only allow user to update own profile unless admin
        profile = self.get_object()
        user_membership = None
        if hasattr(self.request, 'org') and self.request.org:
            user_membership = Membership.objects.filter(
                user=self.request.user, 
                organization=self.request.org
            ).first()
        
        is_admin = user_membership and user_membership.role in ['owner', 'admin']
        if profile.user != self.request.user and not is_admin:
            return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer.save()

    @action(detail=False, methods=['get', 'patch'])
    def my_profile(self, request):
        """Get or update current user's profile"""
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'GET':
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        
        elif request.method == 'PATCH':
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                
                # Log profile update
                log_audit(
                    user=request.user,
                    action_type='update',
                    object_type='UserProfile',
                    object_id=profile.id,
                    changes=request.data,
                    request=request
                )
                
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def switch_organization(self, request):
        """Switch user's active organization"""
        org_id = request.data.get('organization_id')
        if not org_id:
            return Response({'detail': 'organization_id required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            organization = Organization.objects.get(id=org_id, is_active=True)
        except Organization.DoesNotExist:
            return Response({'detail': 'Organization not found or inactive'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user has membership in this organization
        membership = Membership.objects.filter(user=request.user, organization=organization).first()
        if not membership:
            return Response({'detail': 'No membership in this organization'}, status=status.HTTP_403_FORBIDDEN)
        
        # Update user's profile organization
        profile = request.user.profile
        old_org = profile.organization
        profile.organization = organization
        profile.role = membership.role  # Sync role from membership
        profile.save(update_fields=['organization', 'role'])
        
        # Log organization switch
        log_audit(
            user=request.user,
            action_type='update',
            object_type='UserProfile',
            object_id=profile.id,
            metadata={
                'action': 'switch_organization',
                'old_org': old_org.name if old_org else None,
                'new_org': organization.name
            },
            request=request
        )
        
        return Response({
            'message': 'Organization switched successfully',
            'organization': OrganizationSerializer(organization, context={'request': request}).data,
            'role': membership.role
        })

class MembershipViewSet(viewsets.ModelViewSet):
    queryset = Membership.objects.select_related('user', 'organization').all()
    serializer_class = MembershipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        org = getattr(self.request, 'org', None)
        if org:
            qs = qs.filter(organization=org)
        # 支持搜索与角色筛选
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)
        return qs

    def get_permissions(self):
        """Only admins/owners can modify memberships"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsOrgAdminOrOwner()]
        return [IsAuthenticated()]

    @transaction.atomic
    def perform_create(self, serializer):
        """Create membership with seat limit check"""
        org = getattr(self.request, 'org', None) or serializer.validated_data.get('organization')
        
        if not org:
            return Response({'detail': 'Organization not specified'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check seat limit
        current_members = Membership.objects.filter(organization=org).count()
        if current_members >= org.seats:
            return Response({
                'detail': f'Organization has reached maximum seats ({org.seats}). Upgrade plan to add more members.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        membership = serializer.save(organization=org)
        
        # Log membership creation
        log_audit(
            user=self.request.user,
            action_type='create',
            object_type='Membership',
            object_id=membership.id,
            metadata={
                'user_email': membership.user.email,
                'role': membership.role,
                'organization': org.name
            },
            request=self.request
        )

    @transaction.atomic
    def perform_update(self, serializer):
        """Update membership with role change validation"""
        membership = self.get_object()
        old_role = membership.role
        
        updated_membership = serializer.save()
        
        # If role changed, sync with UserProfile if this is user's active org
        if old_role != updated_membership.role:
            try:
                profile = updated_membership.user.profile
                if profile.organization == updated_membership.organization:
                    profile.role = updated_membership.role
                    profile.save(update_fields=['role'])
            except UserProfile.DoesNotExist:
                pass
        
        # Log role change
        log_audit(
            user=self.request.user,
            action_type='update',
            object_type='Membership',
            object_id=membership.id,
            changes={'role': {'old': old_role, 'new': updated_membership.role}},
            metadata={'user_email': membership.user.email},
            request=self.request
        )

    @transaction.atomic
    def perform_destroy(self, instance):
        """Remove membership with owner protection"""
        org = instance.organization
        
        # Prevent removing the last owner
        if instance.role == 'owner':
            other_owners = Membership.objects.filter(organization=org, role='owner').exclude(id=instance.id)
            if not other_owners.exists():
                return Response({
                    'detail': 'Cannot remove the last owner. Assign another owner first.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        user_email = instance.user.email
        instance.delete()
        
        # Log membership removal
        log_audit(
            user=self.request.user,
            action_type='delete',
            object_type='Membership',
            object_id=instance.id,
            metadata={
                'user_email': user_email,
                'role': instance.role,
                'organization': org.name
            },
            request=self.request
        )

    @action(detail=False, methods=['post'])
    def bulk_invite(self, request):
        """Bulk invite users by email"""
        emails = request.data.get('emails', [])
        role = request.data.get('role', 'viewer')
        org = getattr(request, 'org', None)
        
        if not org:
            return Response({'detail': 'Organization not specified'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check permissions
        user_membership = Membership.objects.filter(user=request.user, organization=org).first()
        if not user_membership or user_membership.role not in ['owner', 'admin']:
            return Response({'detail': 'Only owners and admins can invite members'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        # Check seat limits
        current_members = Membership.objects.filter(organization=org).count()
        available_seats = org.seats - current_members
        if len(emails) > available_seats:
            return Response({
                'detail': f'Cannot invite {len(emails)} users. Only {available_seats} seats available.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process invitations (simplified - in production you'd send email invites)
        results = []
        for email in emails:
            try:
                user = get_user_model().objects.get(email=email)
                membership, created = Membership.objects.get_or_create(
                    user=user,
                    organization=org,
                    defaults={'role': role}
                )
                if created:
                    results.append({'email': email, 'status': 'invited', 'role': role})
                    log_audit(
                        user=request.user,
                        action_type='create',
                        object_type='Membership',
                        object_id=membership.id,
                        metadata={'user_email': email, 'role': role, 'bulk_invite': True},
                        request=request
                    )
                else:
                    results.append({'email': email, 'status': 'already_member', 'role': membership.role})
            except get_user_model().DoesNotExist:
                results.append({'email': email, 'status': 'user_not_found'})
        
        return Response({'results': results})

# Rest of the ViewSets remain the same
class APITokenViewSet(viewsets.ModelViewSet):
    queryset = APIToken.objects.all()
    serializer_class = APITokenSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own tokens
        return APIToken.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Generate a random token
        raw_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()
        
        token_instance = serializer.save(user=self.request.user, token=hashed_token)
        
        # Return the raw token once (it won't be stored)
        return Response({
            'id': token_instance.id,
            'name': token_instance.name,
            'raw_token': raw_token,  # Only shown once!
            'scopes': token_instance.scopes,
            'created_at': token_instance.created_at,
            'message': 'Token created successfully. Save this token as it will not be shown again.'
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        """Regenerate a token"""
        token = self.get_object()
        raw_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()
        
        token.token = hashed_token
        token.save(update_fields=['token'])
        
        return Response({
            'raw_token': raw_token,
            'message': 'Token regenerated successfully. Save this token as it will not be shown again.'
        })

class LoginHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LoginHistory.objects.all()
    serializer_class = LoginHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own login history
        return LoginHistory.objects.filter(user=self.request.user)