from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Organization, UserProfile, Membership, APIToken, LoginHistory

class OrganizationSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    current_user_role = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = ['id', 'name', 'description', 'created_at', 'plan', 'seats', 'billing_email', 'current_period_end', 'is_active', 'members_count', 'current_user_role']
        read_only_fields = ['id', 'created_at', 'members_count', 'current_user_role']

    def get_members_count(self, obj):
        return obj.memberships.filter(organization=obj).count()
    
    def get_current_user_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            membership = Membership.objects.filter(user=request.user, organization=obj).first()
            return membership.role if membership else None
        return None

    def validate(self, attrs):
        request = self.context.get('request')
        if request and hasattr(request, 'method') and request.method in ['PUT', 'PATCH']:
            # Check if user has permission to modify organization settings
            user = request.user
            org = self.instance
            if org:
                membership = Membership.objects.filter(user=user, organization=org).first()
                if not membership or membership.role not in ['owner', 'admin']:
                    # Remove sensitive fields for non-admin users
                    protected_fields = ['plan', 'seats', 'billing_email', 'current_period_end', 'is_active']
                    for field in protected_fields:
                        attrs.pop(field, None)
        return attrs

class MembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=False, required=False, write_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)

    class Meta:
        model = Membership
        fields = ['id', 'user', 'user_email', 'user_name', 'organization', 'organization_name', 'role', 'created_at']
        read_only_fields = ['id', 'created_at', 'user_name', 'organization_name']

    def validate_role(self, value):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Get the organization being modified
            org = None
            if self.instance:
                org = self.instance.organization
            elif 'organization' in self.initial_data:
                try:
                    org = Organization.objects.get(id=self.initial_data['organization'])
                except Organization.DoesNotExist:
                    pass
            else:
                # fallback to active org on request
                org = getattr(request, 'org', None)
            
            if org:
                user_membership = Membership.objects.filter(user=request.user, organization=org).first()
                if not user_membership or user_membership.role not in ['owner', 'admin']:
                    raise serializers.ValidationError("Only owners and admins can assign roles.")
                
                # Prevent self-demotion for owners
                if (self.instance and self.instance.user == request.user and 
                    user_membership.role == 'owner' and value != 'owner'):
                    raise serializers.ValidationError("Owners cannot demote themselves.")
        
        return value

    def create(self, validated_data):
        # Resolve user by email if provided and user not set
        user = validated_data.get('user')
        if not user:
            # user_email may come via write-only source mapping; get from initial_data for safety
            user_email = None
            if 'user_email' in self.initial_data and self.initial_data['user_email']:
                user_email = self.initial_data['user_email']
            elif 'user' in validated_data and isinstance(validated_data['user'], str):
                user_email = validated_data['user']
            if user_email:
                user = get_user_model().objects.filter(email__iexact=user_email).first()
                if not user:
                    raise serializers.ValidationError({'user_email': 'User not found for given email'})
                validated_data['user'] = user
        return super().create(validated_data)

class UserProfileSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), source='organization', write_only=True, required=False
    )

    class Meta:
        model = UserProfile
        fields = [
            'id', 'role', 'title', 'organization', 'organization_id',
            'avatar', 'phone', 'bio', 'user_timezone', 'language', 'email_notifications',
            'profile_created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'profile_created_at', 'updated_at']

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']

class APITokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIToken
        fields = ['id', 'name', 'token', 'is_active', 'scopes', 'created_at', 'last_used_at', 'expires_at']
        read_only_fields = ['id', 'created_at', 'last_used_at']

class LoginHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginHistory
        fields = ['id', 'ip_address', 'user_agent', 'location', 'login_at', 'logout_at', 'session_duration', 'is_successful', 'failure_reason']
        read_only_fields = ['id', 'login_at', 'logout_at', 'session_duration']