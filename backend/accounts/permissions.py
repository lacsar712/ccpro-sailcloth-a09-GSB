from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import User


class IsAdminRole(BasePermission):
    """仅 role=admin 的用户可写；任何人（已登录）可读。"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role == User.ROLE_ADMIN
