from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.users.models import UserProfile, Organization, Membership


class IsOrgMember(BasePermission):
    """Require that request.user is authenticated and has a membership in request.org."""

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        org = getattr(request, "org", None)
        if not (user and user.is_authenticated and org):
            return False
        return Membership.objects.filter(user=user, organization=org).exists()


class IsOrgAdminOrOwner(BasePermission):
    """Require that the user has admin or owner role in the active organization."""

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        org = getattr(request, "org", None)
        if not (user and user.is_authenticated and org):
            return False
        mem = Membership.objects.filter(user=user, organization=org).first()
        return mem and mem.role in ("owner", "admin")

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class RBACByRole(BasePermission):
    """
    Map HTTP method to required logical capability and permit by role.
    Roles: owner, admin, scientist, viewer
      - SAFE_METHODS -> view (all roles)
      - POST/PUT/PATCH -> edit (owner, admin, scientist)
      - DELETE -> admin (owner, admin)
    """

    method_to_capability = {
        "GET": "view",
        "HEAD": "view",
        "OPTIONS": "view",
        "POST": "edit",
        "PUT": "edit",
        "PATCH": "edit",
        "DELETE": "admin",
    }

    role_matrix = {
        "owner": {"admin", "edit", "view"},
        "admin": {"admin", "edit", "view"},
        "scientist": {"edit", "view"},
        "viewer": {"view"},
    }

    def _resolve_role(self, request):
        org = getattr(request, "org", None)
        user = getattr(request, "user", None)
        if org and user and user.is_authenticated:
            m = Membership.objects.filter(user=user, organization=org).first()
            if m:
                return m.role
        # Fallback to profile role (legacy)
        try:
            return request.user.profile.role
        except Exception:
            return None

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        role = self._resolve_role(request)
        if not role:
            return False
        need = self.method_to_capability.get(request.method, "view")
        allowed = self.role_matrix.get(role, set())
        return need in allowed 


class SessionRBAC(BasePermission):
    """RBAC tailored for Session resources: allow scientist to DELETE sessions.

    - SAFE methods: allowed for all roles
    - DELETE: treated as 'edit' capability so scientists are allowed
    - Other methods: same mapping as RBACByRole
    """

    def _resolve_role(self, request):
        # Reuse RBACByRole's role resolution
        return RBACByRole()._resolve_role(request)

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        role = self._resolve_role(request)
        if not role:
            return False
        # DELETE is mapped to 'edit' for sessions, other methods follow RBACByRole
        need = "edit" if request.method == "DELETE" else RBACByRole.method_to_capability.get(request.method, "view")
        allowed = RBACByRole.role_matrix.get(role, set())
        return need in allowed


class ProjectRBAC(BasePermission):
    """RBAC tailored for Project resources: allow scientist to DELETE projects.

    - SAFE methods: allowed for all roles
    - DELETE: treated as 'edit' capability so scientists are allowed
    - Other methods: same mapping as RBACByRole
    """

    def _resolve_role(self, request):
        # Reuse RBACByRole's role resolution
        return RBACByRole()._resolve_role(request)

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        role = self._resolve_role(request)
        if not role:
            return False
        # DELETE is mapped to 'edit' for projects, other methods follow RBACByRole
        need = "edit" if request.method == "DELETE" else RBACByRole.method_to_capability.get(request.method, "view")
        allowed = RBACByRole.role_matrix.get(role, set())
        return need in allowed