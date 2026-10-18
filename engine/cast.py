"""起卦与断卦。时间卦只给指数；开收盘数字和只给板块和个股。"""

from __future__ import annotations

import math
from datetime import date

from engine.calendar_cn import BRANCHES, gregorian_to_lunar, solar_month

# 先天数。爻自下而上。
TRIGRAMS = {
    1: ("乾", "金", (1, 1, 1)),
    2: ("兑", "金", (1, 1, 0)),
    3: ("离", "火", (1, 0, 1)),
    4: ("震", "木", (1, 0, 0)),
    5: ("巽", "木", (0, 1, 1)),
    6: ("坎", "水", (0, 1, 0)),
    7: ("艮", "土", (0, 0, 1)),
    8: ("坤", "土", (0, 0, 0)),
}
_BITS = {bits: number for number, (_, _, bits) in TRIGRAMS.items()}
NAMES = {
    (1, 1): "乾为天", (1, 2): "天泽履", (1, 3): "天火同人", (1, 4): "天雷无妄",
    (1, 5): "天风姤", (1, 6): "天水讼", (1, 7): "天山遁", (1, 8): "天地否",
    (2, 1): "泽天夬", (2, 2): "兑为泽", (2, 3): "泽火革", (2, 4): "泽雷随",
    (2, 5): "泽风大过", (2, 6): "泽水困", (2, 7): "泽山咸", (2, 8): "泽地萃",
    (3, 1): "火天大有", (3, 2): "火泽睽", (3, 3): "离为火", (3, 4): "火雷噬嗑",
    (3, 5): "火风鼎", (3, 6): "火水未济", (3, 7): "火山旅", (3, 8): "火地晋",
    (4, 1): "雷天大壮", (4, 2): "雷泽归妹", (4, 3): "雷火丰", (4, 4): "震为雷",
    (4, 5): "雷风恒", (4, 6): "雷水解", (4, 7): "雷山小过", (4, 8): "雷地豫",
    (5, 1): "风天小畜", (5, 2): "风泽中孚", (5, 3): "风火家人", (5, 4): "风雷益",
    (5, 5): "巽为风", (5, 6): "风水涣", (5, 7): "风山渐", (5, 8): "风地观",
    (6, 1): "水天需", (6, 2): "水泽节", (6, 3): "水火既济", (6, 4): "水雷屯",
    (6, 5): "水风井", (6, 6): "坎为水", (6, 7): "水山蹇", (6, 8): "水地比",
    (7, 1): "山天大畜", (7, 2): "山泽损", (7, 3): "山火贲", (7, 4): "山雷颐",
    (7, 5): "山风蛊", (7, 6): "山水蒙", (7, 7): "艮为山", (7, 8): "山地剥",
    (8, 1): "地天泰", (8, 2): "地泽临", (8, 3): "地火明夷", (8, 4): "地雷复",
    (8, 5): "地风升", (8, 6): "地水师", (8, 7): "地山谦", (8, 8): "坤为地",
}
GENERATES = {"金": "水", "水": "木", "木": "火", "火": "土", "土": "金"}
OVERCOMES = {"金": "木", "木": "土", "土": "水", "水": "火", "火": "金"}
# 总诀五句。变体 B 默认关闭，旺衰不改这五档。
VERDICTS = {
    "用生体": ("用生体，有进益", "偏多"),
    "体克用": ("体克用，事情可成", "略偏多"),
    "体用比和": ("体用比和，顺", "震荡"),
    "体生用": ("体生用，有耗泄", "略偏空"),
    "用克体": ("用克体，事情不利", "偏空"),
}
QI_TABLE = {
    "寅": ("木", "土"), "卯": ("木", "土"), "辰": ("土", "水"),
    "巳": ("火", "金"), "午": ("火", "金"), "未": ("土", "水"),
    "申": ("金", "木"), "酉": ("金", "木"), "戌": ("土", "水"),
    "亥": ("水", "火"), "子": ("水", "火"), "丑": ("土", "水"),
}
US_HOUR = 6
US_HOUR_NAME = "巳"
DENOMINATOR_INDEX = "SPX"
TIER_ORDER = ("偏多", "略偏多", "震荡", "略偏空", "偏空")
_TOWARD_FLAT = {"偏多": "略偏多", "略偏多": "震荡", "偏空": "略偏空", "略偏空": "震荡"}


def mod_bagua(number: int) -> int:
    remainder = number % 8
    return 8 if remainder == 0 else remainder


def mod_line(number: int) -> int:
    remainder = number % 6
    return 6 if remainder == 0 else remainder


def digit_sum(printed: str | None) -> int | None:
    """印价的每一位数字相加。不预舍入，不补零。763.3 与 763.30 同和。"""
    if printed is None:
        return None
    text = str(printed).strip()
    if text.lower() in {"", "null", "none", "nan"}:
        return None
    if text[0] in "+-":
        text = text[1:]
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value) or value == 0:
        return None
    digits = [character for character in text if character.isdigit()]
    if not digits:
        return None
    return sum(int(character) for character in digits)


def relation(body_element: str, use_element: str) -> str:
    if body_element == use_element:
        return "体用比和"
    if GENERATES[use_element] == body_element:
        return "用生体"
    if OVERCOMES[body_element] == use_element:
        return "体克用"
    if GENERATES[body_element] == use_element:
        return "体生用"
    if OVERCOMES[use_element] == body_element:
        return "用克体"
    raise RuntimeError(f"无法断 {body_element}/{use_element}")


def is_reversal(opening: str, closing: str) -> bool:
    """起势与收势分处偏多侧和偏空侧。任一侧为震荡则不是变盘。"""
    bull = {"偏多", "略偏多"}
    bear = {"略偏空", "偏空"}
    return (opening in bull and closing in bear) or (opening in bear and closing in bull)


def apply_variant_b(rel: str, tier: str, qi: str) -> str:
    """失令时偏多侧向震荡挪一档；当令时偏空侧同样。默认不调用。"""
    if qi == "体失令" and rel in {"用生体", "体克用"}:
        return _TOWARD_FLAT.get(tier, tier)
    if qi == "体当令" and rel in {"体生用", "用克体"}:
        return _TOWARD_FLAT.get(tier, tier)
    return tier


def _qi_label(body_element: str, branch: str) -> tuple[str, str, str]:
    prosper, weak = QI_TABLE[branch]
    if body_element == prosper:
        label = "体当令"
    elif body_element == weak:
        label = "体失令"
    else:
        label = "体中"
    detail = f"{branch}月，体{body_element}，{prosper}当令、{weak}失令"
    return label, prosper, detail


def _hexagram(upper: int, lower: int, moving: int, session: date, variant_b: bool) -> dict:
    upper_name, _, upper_bits = TRIGRAMS[upper]
    lower_name, _, lower_bits = TRIGRAMS[lower]
    lines = list(lower_bits + upper_bits)
    changed = lines.copy()
    changed[moving - 1] = 1 - changed[moving - 1]
    changed_lower = _BITS[tuple(changed[:3])]
    changed_upper = _BITS[tuple(changed[3:])]
    mutual_lower = _BITS[tuple(lines[1:4])]
    mutual_upper = _BITS[tuple(lines[2:5])]
    if moving <= 3:
        use, body = lower, upper
    else:
        use, body = upper, lower
    body_name, body_element, _ = TRIGRAMS[body]
    use_name, use_element, _ = TRIGRAMS[use]
    rel = relation(body_element, use_element)
    phrase, tier = VERDICTS[rel]
    changed_use = changed_lower if moving <= 3 else changed_upper
    _, changed_element, _ = TRIGRAMS[changed_use]
    end_rel = relation(body_element, changed_element)
    end_phrase, end_tier = VERDICTS[end_rel]
    branch, jie_name = solar_month(session)
    qi, _, qi_detail = _qi_label(body_element, branch)
    scored_tier = apply_variant_b(rel, tier, qi) if variant_b else tier
    lunar = gregorian_to_lunar(session)
    return {
        "upper": upper,
        "lower": lower,
        "upper_name": upper_name,
        "lower_name": lower_name,
        "moving": moving,
        "lines": lines,
        "hexagram": NAMES[(upper, lower)],
        "changed": NAMES[(changed_upper, changed_lower)],
        "mutual": NAMES[(mutual_upper, mutual_lower)],
        "body": body_name,
        "use": use_name,
        "body_element": body_element,
        "use_element": use_element,
        "relation": rel,
        "phrase": phrase,
        "tier": scored_tier,
        "phrase_unchanged_by_qi": phrase,
        "qi": qi,
        "qi_detail": f"{jie_name}起{qi_detail}",
        "qishi_relation": rel,
        "qishi_phrase": phrase,
        "qishi_tier": scored_tier,
        "shoushi_relation": end_rel,
        "shoushi_phrase": end_phrase,
        "shoushi_tier": end_tier,
        "shoushi_display_only": True,
        "variant_b": variant_b,
        "lunar_year": lunar.year,
        "lunar_month": lunar.month,
        "lunar_day": lunar.day,
        "lunar_leap": lunar.leap,
        "year_branch": lunar.branch,
        "year_branch_name": lunar.branch_name,
        "solar_branch": branch,
    }


def cast_index(session: date, *, hour: int = US_HOUR, variant_b: bool = False) -> dict:
    """美股指数。日频时辰固定巳时 6。问事可传入别的时辰数。"""
    lunar = gregorian_to_lunar(session)
    total = lunar.branch + lunar.month + lunar.day
    record = _hexagram(
        mod_bagua(total),
        mod_bagua(total + hour),
        mod_line(total + hour),
        session,
        variant_b,
    )
    record.update(
        {
            "method": "time",
            "status": "ok",
            "hour": hour,
            "hour_name": BRANCHES[hour - 1] if 1 <= hour <= 12 else US_HOUR_NAME,
            "session": session.isoformat(),
        }
    )
    return record


def cast_prices(
    open_print: str | None,
    close_print: str | None,
    session: date,
    *,
    variant_b: bool = False,
) -> dict:
    """板块、个股。数字和用不复权印价。高低和成交量不进公式。"""
    opened = digit_sum(open_print)
    closed = digit_sum(close_print)
    if opened is None or closed is None:
        return {
            "method": "digits",
            "status": "missing",
            "tier": "缺价",
            "phrase": "缺价",
            "qishi_tier": "缺价",
            "shoushi_tier": "缺价",
            "shoushi_display_only": True,
            "variant_b": variant_b,
            "session": session.isoformat(),
            "open_print": open_print,
            "close_print": close_print,
        }
    record = _hexagram(
        mod_bagua(opened),
        mod_bagua(closed),
        mod_line(opened + closed),
        session,
        variant_b,
    )
    record.update(
        {
            "method": "digits",
            "status": "ok",
            "session": session.isoformat(),
            "open_print": None if open_print is None else str(open_print),
            "close_print": None if close_print is None else str(close_print),
            "open_sum": opened,
            "close_sum": closed,
        }
    )
    return record
