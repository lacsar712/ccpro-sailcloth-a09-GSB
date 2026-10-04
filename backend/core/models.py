from django.conf import settings
from django.db import models


class Loft(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=200, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class ClothRoll(models.Model):
    STATUS_RAW = "raw"
    STATUS_DIPPING = "dipping"
    STATUS_CURED = "cured"
    STATUS_CHOICES = [
        (STATUS_RAW, "原布"),
        (STATUS_DIPPING, "浸渍中"),
        (STATUS_CURED, "已固化"),
    ]

    loft = models.ForeignKey(Loft, on_delete=models.CASCADE, related_name="rolls")
    roll_code = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RAW)
    fabric_weight_gsm = models.PositiveIntegerField(default=380)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["loft_id", "roll_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["loft", "roll_code"],
                name="uniq_roll_code_per_loft",
            )
        ]

    def __str__(self):
        return f"{self.loft.name}/{self.roll_code}"


class DipRun(models.Model):
    roll = models.ForeignKey(ClothRoll, on_delete=models.CASCADE, related_name="dip_runs")
    started_at = models.DateTimeField()
    resin_pct = models.DecimalField(max_digits=5, decimal_places=2)
    cure_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Dip@{self.roll_id} {self.started_at}"


class PassTokenQuerySet(models.QuerySet):
    def active(self):
        """未作废（作废时刻为空）。"""
        return self.filter(revoked_at__isnull=True)

    def covering(self, moment):
        """未作废且时段覆盖 moment（左闭右开）。"""
        return self.active().filter(valid_from__lte=moment, valid_until__gt=moment)

    def overlapping(self, valid_from, valid_until):
        """未作废且与 [valid_from, valid_until) 时段重叠（端点相接不算重叠）。"""
        return self.active().filter(
            valid_from__lt=valid_until,
            valid_until__gt=valid_from,
        )


class PassToken(models.Model):
    """帆布间口令牌：改成「浸渍中」必须持有覆盖当前时刻的未作废口令。"""

    loft = models.ForeignKey(Loft, on_delete=models.CASCADE, related_name="pass_tokens")
    passphrase = models.CharField(max_length=128)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="issued_pass_tokens",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PassTokenQuerySet.as_manager()

    class Meta:
        ordering = ["loft_id", "-valid_from", "-id"]
        indexes = [
            models.Index(fields=["loft", "revoked_at", "valid_from", "valid_until"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_until__gt=models.F("valid_from")),
                name="passtoken_until_after_from",
            ),
        ]

    def __str__(self):
        return f"PassToken@{self.loft_id} {self.valid_from:%Y-%m-%d %H:%M}"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def covers(self, moment) -> bool:
        return self.is_active and self.valid_from <= moment < self.valid_until
