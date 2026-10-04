"""帆布浸渍防水台业务规则。"""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from .models import ClothRoll, DipRun, PassToken

MIN_CURE_HOURS_FOR_CURED = Decimal("12")


def latest_dip_run(roll: ClothRoll) -> DipRun | None:
    return roll.dip_runs.order_by("-started_at", "-id").first()


def can_enter_dipping(loft_id: int, moment=None) -> tuple[bool, str]:
    """
    布卷转为「浸渍中」(dipping) 的前提：
    该帆布间存在一张覆盖此刻、未作废的口令牌。
    """
    moment = moment or timezone.now()
    if PassToken.objects.covering(moment).filter(loft_id=loft_id).exists():
        return True, ""
    return False, "该帆布间没有覆盖当前时刻的未作废口令牌，不能改为浸渍中"


def can_mark_roll_cured(roll: ClothRoll) -> tuple[bool, str]:
    """
    布卷转为「已固化」(cured) 的前提：
    最近一条浸渍记录的固化时长已记录，且 >= 12 小时。
    口令牌不参与固化判定。
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
