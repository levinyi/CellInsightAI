from typing import Optional
from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin

from apps.users.models import Organization


class ActiveOrgMiddleware(MiddlewareMixin):
    """
    Resolve active organization for the request.
    Priority:
      1) X-Org header (slug or UUID)
      2) ?org= query param (slug or UUID)
      3) authenticated user's profile.organization
    Sets request.org to Organization or None.
    """

    def process_request(self, request: HttpRequest):
        org_hint: Optional[str] = request.headers.get("X-Org") or request.GET.get("org")
        org = None
        if org_hint:
            # Try UUID match first, then fallback by name or slug
            from uuid import UUID
            try:
                _ = UUID(org_hint)
                org = Organization.objects.filter(id=org_hint).first()
            except Exception:
                # Treat as name or slug-like; prefer exact name match, then icontains
                org = (
                    Organization.objects.filter(name=org_hint).first()
                    or Organization.objects.filter(name__iexact=org_hint).first()
                )
        if org is None and getattr(request, "user", None) and request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)
            if profile and profile.organization_id:
                org = profile.organization
        request.org = org
        return None 