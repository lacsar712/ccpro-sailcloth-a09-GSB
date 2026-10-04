from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminRole

from .models import ClothRoll, DipRun, Loft, PassphraseToken
from .serializers import ClothRollSerializer, DipRunSerializer, LoftSerializer
from .token_serializers import PassphraseTokenSerializer


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


class PassphraseTokenViewSet(viewsets.ModelViewSet):
    """口令牌：任何登录用户可查；仅管理员可签发与作废。"""

    serializer_class = PassphraseTokenSerializer
    permission_classes = [IsAdminRole]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = PassphraseToken.objects.select_related("loft", "issued_by").all()
        loft_id = self.request.query_params.get("loftId")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if self.request.query_params.get("active") in ("1", "true", "True"):
            now = timezone.now()
            qs = qs.filter(
                revoked_at__isnull=True,
                valid_from__lte=now,
                valid_until__gt=now,
            )
        return qs

    def create(self, request, *args, **kwargs):
        # 锁住对应帆布间行，串行化同间并发签发；跨间不互斥
        loft_id = request.data.get("loftId")
        with transaction.atomic():
            if loft_id:
                list(
                    Loft.objects.select_for_update()
                    .filter(pk=loft_id)
                    .values_list("id", flat=True)
                )
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                serializer.save()
            except IntegrityError:
                # 数据库排他约束兜底：同间未作废时段重叠
                raise drf_serializers.ValidationError(
                    {"non_field_errors": ["同一帆布间未作废口令时段不得重叠"]}
                )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        token = self.get_object()
        if token.revoked_at is not None:
            return Response(
                {"detail": "该口令牌已作废，无需重复作废"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token.revoked_at = timezone.now()
        token.save(update_fields=["revoked_at"])
        return Response(self.get_serializer(token).data)


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
