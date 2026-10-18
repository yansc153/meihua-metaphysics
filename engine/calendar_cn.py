"""农历与十二节气。起卦用农历，年支在正月初一换；旺衰月建用节气。四柱不进起卦。"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
NEW_YORK = ZoneInfo("America/New_York")

# 1900–2100。低 4 位是闰月；0x10000 表示闰月 30 天；0x8000 起向低位是正月到十二月的大小。
_LUNAR_INFO = [
    0x04BD8, 0x04AE0, 0x0A570, 0x054D5, 0x0D260, 0x0D950, 0x16554, 0x056A0, 0x09AD0, 0x055D2,
    0x04AE0, 0x0A5B6, 0x0A4D0, 0x0D250, 0x1D255, 0x0B540, 0x0D6A0, 0x0ADA2, 0x095B0, 0x14977,
    0x04970, 0x0A4B0, 0x0B4B5, 0x06A50, 0x06D40, 0x1AB54, 0x02B60, 0x09570, 0x052F2, 0x04970,
    0x06566, 0x0D4A0, 0x0EA50, 0x06E95, 0x05AD0, 0x02B60, 0x186E3, 0x092E0, 0x1C8D7, 0x0C950,
    0x0D4A0, 0x1D8A6, 0x0B550, 0x056A0, 0x1A5B4, 0x025D0, 0x092D0, 0x0D2B2, 0x0A950, 0x0B557,
    0x06CA0, 0x0B550, 0x15355, 0x04DA0, 0x0A5B0, 0x14573, 0x052B0, 0x0A9A8, 0x0E950, 0x06AA0,
    0x0AEA6, 0x0AB50, 0x04B60, 0x0AAE4, 0x0A570, 0x05260, 0x0F263, 0x0D950, 0x05B57, 0x056A0,
    0x096D0, 0x04DD5, 0x04AD0, 0x0A4D0, 0x0D4D4, 0x0D250, 0x0D558, 0x0B540, 0x0B6A0, 0x195A6,
    0x095B0, 0x049B0, 0x0A974, 0x0A4B0, 0x0B27A, 0x06A50, 0x06D40, 0x0AF46, 0x0AB60, 0x09570,
    0x04AF5, 0x04970, 0x064B0, 0x074A3, 0x0EA50, 0x06B58, 0x055C0, 0x0AB60, 0x096D5, 0x092E0,
    0x0C960, 0x0D954, 0x0D4A0, 0x0DA50, 0x07552, 0x056A0, 0x0ABB7, 0x025D0, 0x092D0, 0x0CAB5,
    0x0A950, 0x0B4A0, 0x0BAA4, 0x0AD50, 0x055D9, 0x04BA0, 0x0A5B0, 0x15176, 0x052B0, 0x0A930,
    0x07954, 0x06AA0, 0x0AD50, 0x05B52, 0x04B60, 0x0A6E6, 0x0A4E0, 0x0D260, 0x0EA65, 0x0D530,
    0x05AA0, 0x076A3, 0x096D0, 0x04AFB, 0x04AD0, 0x0A4D0, 0x1D0B6, 0x0D250, 0x0D520, 0x0DD45,
    0x0B5A0, 0x056D0, 0x055B2, 0x049B0, 0x0A577, 0x0A4B0, 0x0AA50, 0x1B255, 0x06D20, 0x0ADA0,
    0x14B63, 0x09370, 0x049F8, 0x04970, 0x064B0, 0x168A6, 0x0EA50, 0x06B20, 0x1A6C4, 0x0AAE0,
    0x0A2E0, 0x0D2E3, 0x0C960, 0x0D557, 0x0D4A0, 0x0DA50, 0x05D55, 0x056A0, 0x0A6D0, 0x055D4,
    0x052D0, 0x0A9B8, 0x0A950, 0x0B4A0, 0x0B6A6, 0x0AD50, 0x055A0, 0x0ABA4, 0x0A5B0, 0x052B0,
    0x0B273, 0x06930, 0x07337, 0x06AA0, 0x0AD50, 0x14B55, 0x04B60, 0x0A570, 0x054E4, 0x0D160,
    0x0E968, 0x0D520, 0x0DAA0, 0x16AA6, 0x056D0, 0x04AE0, 0x0A9D4, 0x0A2D0, 0x0D150, 0x0F252,
    0x0D520,
]
_LUNAR_EPOCH = date(1900, 1, 31)
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def _info(lunar_year: int) -> int:
    if not 1900 <= lunar_year <= 2100:
        raise ValueError(f"农历年超出 1900–2100：{lunar_year}")
    return _LUNAR_INFO[lunar_year - 1900]


def leap_month(lunar_year: int) -> int:
    return _info(lunar_year) & 0xF


def leap_days(lunar_year: int) -> int:
    if leap_month(lunar_year):
        return 30 if _info(lunar_year) & 0x10000 else 29
    return 0


def month_days(lunar_year: int, month: int) -> int:
    return 30 if _info(lunar_year) & (0x10000 >> month) else 29


def year_days(lunar_year: int) -> int:
    total = 348
    bits = _info(lunar_year)
    mask = 0x8000
    while mask > 0x8:
        if bits & mask:
            total += 1
        mask >>= 1
    return total + leap_days(lunar_year)


def year_branch_number(lunar_year: int) -> int:
    """子=1 … 亥=12。取农历年，不取立春后的四柱年支。"""
    return ((lunar_year - 4) % 12) + 1


def year_branch_name(lunar_year: int) -> str:
    return BRANCHES[year_branch_number(lunar_year) - 1]


class LunarDate:
    def __init__(self, year: int, month: int, day: int, leap: bool):
        self.year = year
        self.month = month
        self.day = day
        self.leap = leap

    @property
    def branch(self) -> int:
        return year_branch_number(self.year)

    @property
    def branch_name(self) -> str:
        return year_branch_name(self.year)


def gregorian_to_lunar(day: date) -> LunarDate:
    if day < _LUNAR_EPOCH:
        raise ValueError(f"早于农历换算起点：{day}")
    offset = (day - _LUNAR_EPOCH).days
    year = 1900
    length = 0
    while year < 2101 and offset > 0:
        length = year_days(year)
        offset -= length
        year += 1
    if offset < 0:
        offset += length
        year -= 1
    leap = leap_month(year)
    is_leap = False
    month = 1
    while month < 13 and offset > 0:
        if leap > 0 and month == leap + 1 and not is_leap:
            month -= 1
            is_leap = True
            length = leap_days(year)
        else:
            length = month_days(year, month)
        if is_leap and month == leap + 1:
            is_leap = False
        offset -= length
        month += 1
    if offset == 0 and leap > 0 and month == leap + 1:
        if is_leap:
            is_leap = False
        else:
            is_leap = True
            month -= 1
    if offset < 0:
        offset += length
        month -= 1
    return LunarDate(year, month, offset + 1, is_leap)


def _julian_day(moment: datetime) -> float:
    utc = moment.astimezone(ZoneInfo("UTC"))
    year, month = utc.year, utc.month
    day = utc.day + (utc.hour + utc.minute / 60 + utc.second / 3600) / 24
    if month <= 2:
        year -= 1
        month += 12
    century = year // 100
    gregorian = 2 - century + century // 4
    return (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day
        + gregorian
        - 1524.5
    )


def sun_longitude(moment: datetime) -> float:
    """视黄经（度）。只用来判断节气落到哪一天。"""
    time = (_julian_day(moment) - 2451545.0) / 36525.0
    mean = 280.46646 + 36000.76983 * time + 0.0003032 * time * time
    anomaly = 357.52911 + 35999.05029 * time - 0.0001537 * time * time
    rad = math.radians(anomaly % 360)
    center = (
        (1.914602 - 0.004817 * time - 0.000014 * time * time) * math.sin(rad)
        + (0.019993 - 0.000101 * time) * math.sin(2 * rad)
        + 0.000289 * math.sin(3 * rad)
    )
    omega = 125.04 - 1934.136 * time
    apparent = mean + center - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    return apparent % 360.0


# 十二节，不是中气。月建从该节当天起，到下一节前一天止。
JIE = (
    (285, "丑", "小寒"),
    (315, "寅", "立春"),
    (345, "卯", "惊蛰"),
    (15, "辰", "清明"),
    (45, "巳", "立夏"),
    (75, "午", "芒种"),
    (105, "未", "小暑"),
    (135, "申", "立秋"),
    (165, "酉", "白露"),
    (195, "戌", "寒露"),
    (225, "亥", "立冬"),
    (255, "子", "大雪"),
)
_JIE_GUESS = {
    "小寒": (1, 5),
    "立春": (2, 4),
    "惊蛰": (3, 6),
    "清明": (4, 5),
    "立夏": (5, 6),
    "芒种": (6, 6),
    "小暑": (7, 7),
    "立秋": (8, 7),
    "白露": (9, 8),
    "寒露": (10, 8),
    "立冬": (11, 7),
    "大雪": (12, 7),
}


def _crossed(previous: float, current: float, target: float) -> bool:
    previous %= 360
    current %= 360
    if previous <= current:
        return previous < target <= current
    return target > previous or target <= current


@lru_cache(maxsize=32)
def jie_dates(year: int) -> tuple[tuple[date, str, str], ...]:
    found = []
    for longitude, branch, name in JIE:
        month, day = _JIE_GUESS[name]
        start = datetime(year, month, day, tzinfo=SHANGHAI) - timedelta(days=5)
        previous = sun_longitude(start)
        hit = None
        moment = start
        for _ in range(24 * 16):
            moment += timedelta(hours=1)
            current = sun_longitude(moment)
            if _crossed(previous, current, longitude):
                hit = moment.astimezone(SHANGHAI).date()
                break
            previous = current
        if hit is None:
            raise RuntimeError(f"找不到 {year} 年{name}")
        found.append((hit, branch, name))
    return tuple(found)


def solar_month(day: date) -> tuple[str, str]:
    """返回 (月建, 节名)。起卦不用这个月建。"""
    candidates = []
    for year in (day.year - 1, day.year, day.year + 1):
        candidates.extend(jie_dates(year))
    landed = [item for item in candidates if item[0] <= day]
    if not landed:
        raise ValueError(f"没有落到节气：{day}")
    start, branch, name = max(landed, key=lambda item: item[0])
    return branch, name


def easter(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = (h + ell - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    shift = (weekday - first.weekday()) % 7
    return first + timedelta(days=shift + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        cursor = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        cursor = date(year, month + 1, 1) - timedelta(days=1)
    while cursor.weekday() != weekday:
        cursor -= timedelta(days=1)
    return cursor


def _observe(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


@lru_cache(maxsize=64)
def nyse_holidays(year: int) -> frozenset[date]:
    days = {
        _observe(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        easter(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observe(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observe(date(year, 12, 25)),
    }
    if year >= 2022:
        days.add(_observe(date(year, 6, 19)))
    if date(year, 1, 1).weekday() == 5:
        days.add(date(year - 1, 12, 31))
    return frozenset(days)


def is_nyse_session(day: date) -> bool:
    return day.weekday() < 5 and day not in nyse_holidays(day.year) and day not in nyse_holidays(day.year + 1)


def next_session(day: date, *, inclusive: bool = True) -> date:
    cursor = day if inclusive else day + timedelta(days=1)
    while not is_nyse_session(cursor):
        cursor += timedelta(days=1)
    return cursor


def session_for_clock(now: datetime | None = None) -> tuple[date, bool]:
    """开盘前给出当天会话；周末给下一场。巳时卦不依赖跑到 9:30。"""
    moment = now or datetime.now(NEW_YORK)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=NEW_YORK)
    else:
        moment = moment.astimezone(NEW_YORK)
    local_day = moment.date()
    open_passed = is_nyse_session(local_day) and (moment.hour, moment.minute) >= (9, 30)
    if is_nyse_session(local_day):
        return local_day, open_passed
    return next_session(local_day, inclusive=False), False
