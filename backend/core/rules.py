"""帆布浸渍防水台业务规则。"""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from .models import ClothRoll, DipRun, Loft, PassphraseToken

MIN_CURE_HOURS_FOR_CURED = Decimal("12")


def latest_dip_run(roll: ClothRoll) -> DipRun | None:
    return roll.dip_runs.order_by("-started_at", "-id").first()


def active_token_for_loft(loft: Loft, moment=None) -> PassphraseToken | None:
    """该帆布间此刻存在的「未作废且时段覆盖此刻」的口令牌（左闭右开）。"""
    moment = moment or timezone.now()
    return (
        PassphraseToken.objects.filter(
            loft=loft,
            revoked_at__isnull=True,
            valid_from__lte=moment,
            valid_until__gt=moment,
        )
        .order_by("-valid_from", "-id")
        .first()
    )


def can_mark_roll_dipping(loft: Loft, moment=None) -> tuple[bool, str]:
    """
    布卷转为「浸渍中」(dipping) 的前提：
    所属帆布间必须有一张覆盖此刻、未作废的口令牌。
    """
    if active_token_for_loft(loft, moment) is None:
        return (
            False,
            "该帆布间当前没有覆盖此刻且未作废的口令牌，不能标为浸渍中",
        )
    return True, ""


def can_mark_roll_cured(roll: ClothRoll) -> tuple[bool, str]:
    """
    布卷转为「已固化」(cured) 的前提：
    最近一条浸渍记录的固化时长已记录，且 >= 12 小时。
    """
    latest = latest_dip_run(roll)
    if latest is None:
        return False, "该布卷尚无浸渍记录，不能标记为已固化"
    if latest.cure_hours is None:
        return False, "最近浸渍记录尚未填写固化时长，不能标记为已固化"
    if latest.cure_hours < MIN_CURE_HOURS_FOR_CURED:
        return (
            False,
            f"最近浸渍固化时长 {latest.cure_hours} 小时低于 {MIN_CURE_HOURS_FOR_CURED} 小时，不能标记为已固化",
        )
    return True, ""
