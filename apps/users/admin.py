from django.contrib import admin
from .models import Organization, UserProfile, Membership, APIToken, LoginHistory

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'title']

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'created_at']
    list_filter = ['role']
    search_fields = ['user__username', 'user__email', 'organization__name']

@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'is_active', 'created_at', 'last_used_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__username', 'name']
    readonly_fields = ['id', 'token', 'created_at', 'last_used_at']

@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip_address', 'login_at', 'is_successful']
    list_filter = ['is_successful', 'login_at']
    search_fields = ['user__username', 'ip_address']
    readonly_fields = ['id', 'login_at', 'logout_at', 'session_duration']