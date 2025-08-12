import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
import secrets
import hashlib

class Organization(models.Model):
    PLAN_CHOICES = (
        ('free', 'Free'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Subscription/billing
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    seats = models.PositiveIntegerField(default=5)
    billing_email = models.EmailField(blank=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    @property
    def members_count(self):
        """Return count of active memberships"""
        return self.memberships.count()
    
    @property
    def available_seats(self):
        """Return available seats"""
        return max(0, self.seats - self.members_count)
    
    def get_owners(self):
        """Return users with owner role"""
        return get_user_model().objects.filter(
            memberships__organization=self, 
            memberships__role='owner'
        )
    
    def can_delete(self):
        """Check if organization can be safely deleted"""
        sole_members = []
        for membership in self.memberships.all():
            user_org_count = membership.user.memberships.count()
            if user_org_count == 1:
                sole_members.append(membership.user.username)
        return len(sole_members) == 0, sole_members

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('scientist', 'Scientist'),
        ('viewer', 'Viewer'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='profile')
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    title = models.CharField(max_length=255, blank=True)
    
    avatar = models.URLField(blank=True, null=True, help_text="头像图片 URL")
    phone = models.CharField(max_length=20, blank=True, validators=[RegexValidator(r'^\+?\d{10,15}$')])
    bio = models.TextField(blank=True, help_text="个人简介")
    user_timezone = models.CharField(max_length=50, default='UTC', help_text="时区")
    language = models.CharField(max_length=10, default='en', choices=[('en', 'English'), ('zh-cn', '简体中文'), ('zh-tw', '繁體中文')])
    email_notifications = models.BooleanField(default=True, help_text="是否接收邮件通知")
    profile_created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
    
    def get_membership(self, organization=None):
        org = organization or self.organization
        if not org:
            return None
        return self.user.memberships.filter(organization=org).first()
    
    def is_org_admin_or_owner(self, organization=None):
        membership = self.get_membership(organization)
        return membership and membership.role in ['owner', 'admin']

class Membership(models.Model):
    ROLE_CHOICES = (
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('scientist', 'Scientist'),
        ('viewer', 'Viewer'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='memberships')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    invited_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_invitations')
    invited_at = models.DateTimeField(null=True, blank=True, default=None)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "organization")

    def __str__(self):
        return f"{self.user.username} in {self.organization.name} as {self.role}"
    
    def can_manage_members(self):
        return self.role in ['owner', 'admin']
    
    def can_assign_role(self, target_role):
        if self.role == 'owner':
            return True
        elif self.role == 'admin':
            return target_role in ['scientist', 'viewer']
        return False

class APIToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='api_tokens')
    name = models.CharField(max_length=100, help_text="Token name for identification")
    token = models.CharField(max_length=128, unique=True, help_text="Hashed token value")
    
    is_active = models.BooleanField(default=True)
    scopes = models.JSONField(default=list, blank=True, help_text="API scopes (e.g., ['read', 'write'])")
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username}: {self.name}"

class LoginHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='login_history')
    
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True, help_text="Approximate location (city, country)")
    
    login_at = models.DateTimeField(auto_now_add=True)
    logout_at = models.DateTimeField(blank=True, null=True)
    session_duration = models.DurationField(blank=True, null=True)
    
    is_successful = models.BooleanField(default=True)
    failure_reason = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-login_at']
    
    def __str__(self):
        return f"{self.user.username} @ {self.ip_address} on {self.login_at.strftime('%Y-%m-%d %H:%M')}"

@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        try:
            org_name = f"{instance.username}'s Organization"
            org, _ = Organization.objects.get_or_create(
                name=org_name,
                defaults={'description': f'Personal organization for {instance.username}'}
            )
            UserProfile.objects.create(user=instance, organization=org, role='owner')
            Membership.objects.create(user=instance, organization=org, role='owner')
        except Exception:
            pass