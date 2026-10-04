from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeBoundary, RangeOperators
from django.db import models
from django.utils import timezone


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


class PassphraseToken(models.Model):
    """帆布间浸渍口令牌：时段内允许把此间布卷标为「浸渍中」。"""

    loft = models.ForeignKey(Loft, on_delete=models.CASCADE, related_name="tokens")
    plaintext = models.CharField("口令明文", max_length=120)
    valid_from = models.DateTimeField("生效时刻")
    valid_until = models.DateTimeField("失效时刻")
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="issued_tokens",
        verbose_name="签发人",
    )
    revoked_at = models.DateTimeField("作废时刻", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["loft_id", "-valid_from", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_until__gt=models.F("valid_from")),
                name="token_window_ordered",
            ),
            ExclusionConstraint(
                name="uniq_active_token_no_overlap",
                expressions=[
                    (models.F("loft"), RangeOperators.EQUAL),
                    (
                        models.Func(
                            models.F("valid_from"),
                            models.F("valid_until"),
                            RangeBoundary(),
                            function="tstzrange",
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=models.Q(revoked_at__isnull=True),
                violation_error_message="同一帆布间未作废口令时段不得重叠",
            ),
        ]

    def __str__(self):
        return f"口令@{self.loft_id} {self.valid_from:%Y-%m-%d %H:%M}"

    def is_active_at(self, moment=None) -> bool:
        """未作废且时段覆盖指定时刻（左闭右开）。"""
        moment = moment or timezone.now()
        if self.revoked_at is not None:
            return False
        return self.valid_from <= moment < self.valid_until
