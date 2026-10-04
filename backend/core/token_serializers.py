from rest_framework import serializers

from .models import Loft, PassphraseToken


class PassphraseTokenSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    loftName = serializers.CharField(source="loft.name", read_only=True)
    plaintext = serializers.CharField(max_length=120, allow_blank=False)
    validFrom = serializers.DateTimeField(source="valid_from")
    validUntil = serializers.DateTimeField(source="valid_until")
    issuedById = serializers.IntegerField(source="issued_by_id", read_only=True)
    issuedByName = serializers.CharField(source="issued_by.username", read_only=True)
    revokedAt = serializers.DateTimeField(source="revoked_at", read_only=True)
    revoked = serializers.SerializerMethodField()
    activeNow = serializers.SerializerMethodField()

    class Meta:
        model = PassphraseToken
        fields = (
            "id",
            "loftId",
            "loftName",
            "plaintext",
            "validFrom",
            "validUntil",
            "issuedById",
            "issuedByName",
            "revokedAt",
            "revoked",
            "activeNow",
            "created_at",
        )
        read_only_fields = (
            "id",
            "loftName",
            "issuedById",
            "issuedByName",
            "revokedAt",
            "revoked",
            "activeNow",
            "created_at",
        )

    def get_revoked(self, obj):
        return obj.revoked_at is not None

    def get_activeNow(self, obj):
        return obj.is_active_at()

    def validate(self, attrs):
        valid_from = attrs.get("valid_from")
        valid_until = attrs.get("valid_until")
        loft = attrs.get("loft")

        if valid_from and valid_until and valid_until <= valid_from:
            raise serializers.ValidationError(
                {"validUntil": "失效时刻必须晚于生效时刻"}
            )

        # 应用层先拦一道重叠；并发下另有数据库排他约束兜底
        if loft and valid_from and valid_until:
            overlap = PassphraseToken.objects.filter(
                loft=loft,
                revoked_at__isnull=True,
                valid_from__lt=valid_until,
                valid_until__gt=valid_from,
            )
            if self.instance:
                overlap = overlap.exclude(pk=self.instance.pk)
            if overlap.exists():
                raise serializers.ValidationError(
                    {"non_field_errors": ["同一帆布间未作废口令时段不得重叠"]}
                )
        return attrs

    def create(self, validated_data):
        validated_data["issued_by"] = self.context["request"].user
        return super().create(validated_data)
