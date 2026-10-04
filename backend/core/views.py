from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from accounts.models import User

from .models import ClothRoll, DipRun, Loft, PassToken
from .serializers import (
    ClothRollSerializer,
    DipRunSerializer,
    LoftSerializer,
    PassTokenSerializer,
)


class IsAdminRole(BasePermission):
    """仅管理员（accounts.User.role == admin）。"""

    message = "仅管理员可签发或作废口令牌"

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_ADMIN
        )


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = ClothRoll.objects.select_related("loft").all()
        loft_id = self.request.query_params.get("loftId")
        status = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status:
            qs = qs.filter(status=status)
        return qs


class DipRunViewSet(viewsets.ModelViewSet):
    serializer_class = DipRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = DipRun.objects.select_related("roll", "roll__loft").all()
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs


class PassTokenViewSet(viewsets.ModelViewSet):
    serializer_class = PassTokenSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        # 查看：任何登录用户；签发与作废：仅管理员
        if self.action in ("create", "revoke"):
            return [IsAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = PassToken.objects.select_related("loft", "issued_by").all()
        loft_id = self.request.query_params.get("loftId")
        state = self.request.query_params.get("state")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if state == "active":
            qs = qs.covering(timezone.now())
        elif state == "valid":
            # 未作废（含未到生效时刻的）
            qs = qs.active()
        return qs

    def perform_create(self, serializer):
        loft = serializer.validated_data["loft"]
        valid_from = serializer.validated_data["valid_from"]
        valid_until = serializer.validated_data["valid_until"]
        with transaction.atomic():
            # 锁住帆布间行，把并发签发串行化，再复查时段重叠，
            # 保证两名管理员交叉签发时重叠口令只许一张入库。
            locked_loft = Loft.objects.select_for_update().get(pk=loft.pk)
            clash = (
                PassToken.objects.overlapping(valid_from, valid_until)
                .filter(loft=locked_loft)
                .exists()
            )
            if clash:
                raise serializers.ValidationError(
                    {"validFrom": "同一帆布间已存在未作废且时段重叠的口令牌"}
                )
            serializer.save(loft=locked_loft, issued_by=self.request.user)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        token = self.get_object()
        if token.revoked_at is not None:
            return Response(
                {"detail": "该口令牌已作废，不能重复作废"},
                status=400,
            )
        token.revoked_at = timezone.now()
        token.save(update_fields=["revoked_at"])
        return Response(PassTokenSerializer(token, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    data = {
        "loftCount": Loft.objects.count(),
        "rawRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_RAW).count(),
        "dippingRollCount": ClothRoll.objects.filter(
            status=ClothRoll.STATUS_DIPPING
        ).count(),
        "curedRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_CURED).count(),
        "dipRunCount": DipRun.objects.count(),
    }
    return Response(data)
