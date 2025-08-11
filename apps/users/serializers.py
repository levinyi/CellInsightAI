from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Organization, UserProfile, Membership

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'description', 'created_at', 'plan', 'seats', 'billing_email', 'current_period_end', 'is_active']
        read_only_fields = ['id', 'created_at']

class MembershipSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all())

    class Meta:
        model = Membership
        fields = ['id', 'user', 'organization', 'role', 'created_at']
        read_only_fields = ['id', 'created_at']

class UserProfileSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), source='organization', write_only=True, required=False
    )

    class Meta:
        model = UserProfile
        fields = ['id', 'role', 'title', 'organization', 'organization_id']
        read_only_fields = ['id']

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']