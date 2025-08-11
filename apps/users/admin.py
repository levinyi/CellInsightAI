from django.contrib import admin
from .models import Organization, UserProfile

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'title']
    list_filter = ['role', 'organization']
    search_fields = ['user__username', 'user__email', 'title']
    readonly_fields = ['id']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'organization')