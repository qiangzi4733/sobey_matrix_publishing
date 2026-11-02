"""各平台自带定时发布的规则。不依赖浏览器，backend 提交前校验也用它。"""

from datetime import UTC, datetime, timedelta

from app.models import Platform

# 平台 → (最早提前量, 最远可定时范围)。在列表里的平台由平台自己到点发布，
# 我们提交时就把定时时间交给平台；不在列表里的平台由我们的 beat 到点再发。
NATIVE_SCHEDULE: dict[Platform, tuple[timedelta, timedelta]] = {
    # 2026-11 实测视频号可选今天起 30 天内
    Platform.channels: (timedelta(minutes=10), timedelta(days=30)),
    # 抖音：2 小时后～14 天内（2026-11 发布页提示「支持2小时后及14天内的定时发布」）
    Platform.douyin: (timedelta(hours=2), timedelta(days=14)),
}


def validate_native_schedule(platform: Platform, when: datetime) -> None:
    min_lead, max_ahead = NATIVE_SCHEDULE[platform]
    now = datetime.now(UTC)
    if when < now + min_lead:
        minutes = int(min_lead.total_seconds() // 60)
        lead = f"{minutes // 60} 小时" if minutes % 60 == 0 else f"{minutes} 分钟"
        raise ValueError(f"定时发布时间至少要在 {lead}之后")
    if when > now + max_ahead:
        raise ValueError(f"定时发布最多只能设置 {max_ahead.days} 天内")
