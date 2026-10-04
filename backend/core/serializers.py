from django.utils import timezone
from rest_framework import serializers

from .models import ClothRoll, DipRun, Loft, PassToken
from .rules import can_enter_dipping, can_mark_roll_cured


class LoftSerializer(serializers.ModelSerializer):
    rollCount = serializers.SerializerMethodField()

    class Meta:
        model = Loft
        fields = ("id", "name", "location", "notes", "rollCount", "created_at")
        read_only_fields = ("id", "rollCount", "created_at")

    def get_rollCount(self, obj):
        if hasattr(obj, "roll_count"):
            return obj.roll_count
        return obj.rolls.count()


class ClothRollSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    rollCode = serializers.CharField(source="roll_code")
    fabricWeightGsm = serializers.IntegerField(source="fabric_weight_gsm", required=False)
    loftName = serializers.CharField(source="loft.name", read_only=True)

    class Meta:
        model = ClothRoll
        fields = (
            "id",
            "loftId",
            "loftName",
            "rollCode",
            "status",
            "fabricWeightGsm",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "loftName", "created_at", "updated_at")

    def validate(self, attrs):
        loft = attrs.get("loft") or getattr(self.instance, "loft", None)
        roll_code = attrs.get("roll_code") or getattr(self.instance, "roll_code", None)
        if loft and roll_code:
            qs = ClothRoll.objects.filter(loft=loft, roll_code=roll_code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"rollCode": "同一帆布间卷号必须唯一"})

        new_status = attrs.get("status")
        if new_status == ClothRoll.STATUS_CURED:
            roll = self.instance
            if roll is None:
                raise serializers.ValidationError(
                    {"status": "新建布卷不能直接设为已固化"}
                )
            # 固化只认最近浸渍固化时长满 12 小时，口令牌不参与固化判定
            ok, msg = can_mark_roll_cured(roll)
            if not ok:
                raise serializers.ValidationError({"status": msg})
        elif new_status == ClothRoll.STATUS_DIPPING:
            # 浸渍中：该帆布间须有覆盖此刻、未作废的口令牌
            if loft is None:
                raise serializers.ValidationError(
                    {"status": "缺少帆布间，无法核验口令牌"}
                )
            ok, msg = can_enter_dipping(loft.id)
            if not ok:
                raise serializers.ValidationError({"status": msg})
        return attrs


class DipRunSerializer(serializers.ModelSerializer):
    rollId = serializers.PrimaryKeyRelatedField(
        source="roll", queryset=ClothRoll.objects.all()
    )
    startedAt = serializers.DateTimeField(source="started_at")
    resinPct = serializers.DecimalField(source="resin_pct", max_digits=5, decimal_places=2)
    cureHours = serializers.DecimalField(
        source="cure_hours",
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    loftName = serializers.CharField(source="roll.loft.name", read_only=True)

    class Meta:
        model = DipRun
        fields = (
            "id",
            "rollId",
            "rollCode",
            "loftName",
            "startedAt",
            "resinPct",
            "cureHours",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "rollCode", "loftName", "created_at")


class PassTokenSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    loftName = serializers.CharField(source="loft.name", read_only=True)
    passphrase = serializers.CharField(max_length=120)
    validFrom = serializers.DateTimeField(source="valid_from")
    validUntil = serializers.DateTimeField(source="valid_until")
    issuedById = serializers.IntegerField(source="issued_by_id", read_only=True)
    issuedByName = serializers.CharField(source="issued_by.username", read_only=True)
    revokedAt = serializers.DateTimeField(source="revoked_at", read_only=True)
    state = serializers.SerializerMethodField()

    class Meta:
        model = PassToken
        fields = (
            "id",
            "loftId",
            "loftName",
            "passphrase",
            "validFrom",
            "validUntil",
            "issuedById",
            "issuedByName",
            "revokedAt",
            "state",
            "created_at",
        )
        read_only_fields = (
            "id",
            "loftName",
            "issuedById",
            "issuedByName",
            "revokedAt",
            "state",
            "created_at",
        )

    def get_state(self, obj):
        now = timezone.now()
        if obj.revoked_at is not None:
            return "revoked"
        if now < obj.valid_from:
            return "pending"
        if now >= obj.valid_until:
            return "expired"
        return "active"

    def validate(self, attrs):
        valid_from = attrs.get("valid_from")
        valid_until = attrs.get("valid_until")
        loft = attrs.get("loft")
        if valid_from and valid_until and valid_until <= valid_from:
            raise serializers.ValidationError(
                {"validUntil": "失效时刻必须晚于生效时刻"}
            )
        if loft and valid_from and valid_until:
            clash = (
                PassToken.objects.overlapping(valid_from, valid_until)
                .filter(loft=loft)
                .exists()
            )
            if clash:
                raise serializers.ValidationError(
                    {"validFrom": "同一帆布间已存在未作废且时段重叠的口令牌"}
                )
        return attrs
