"""回测。主命中按五档分列，比和不进平桶。指数分母只计标普。"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime

from engine.cast import DENOMINATOR_INDEX, TIER_ORDER, cast_index, cast_prices

DEFAULT_BAND = 0.002
_TRUE = {"1", "true", "yes", "y", "是"}
_INDEX_ALIASES = {DENOMINATOR_INDEX, "^GSPC", "GSPC"}
_SKIPPED_INDEXES = {"IXIC", "^IXIC", "NDX", "^NDX"}


def band_width(fee: float = 0.0) -> float:
    return max(DEFAULT_BAND, fee)


def direction(change: float, band: float) -> str:
    if change > band:
        return "up"
    if change < -band:
        return "down"
    return "flat"


def _flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in _TRUE


def _number(value: str | None) -> float | None:
    text = str(value or "").strip()
    if text.lower() in {"", "null", "none", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _factor_jump(row: dict) -> bool:
    pairs = []
    for raw_key, adj_key in (("open_raw", "open_adj"), ("close_raw", "close_adj"), ("prev_close_raw", "prev_close_adj")):
        raw = _number(row.get(raw_key))
        adj = _number(row.get(adj_key))
        if raw not in (None, 0) and adj is not None:
            pairs.append(adj / raw)
    if len(pairs) < 2:
        return False
    base = pairs[0]
    return any(abs(item - base) / abs(base) > 0.001 for item in pairs[1:])


def load_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _cast_row(row: dict, session: date, variant_b: bool) -> dict | None:
    role = (row.get("role") or "").strip().lower()
    symbol = (row.get("symbol") or "").strip().upper()
    if role == "index" or symbol in _INDEX_ALIASES or symbol in _SKIPPED_INDEXES:
        if symbol in _SKIPPED_INDEXES:
            return None
        if symbol not in _INDEX_ALIASES:
            return None
        return cast_index(session, variant_b=variant_b)
    return cast_prices(row.get("cast_open"), row.get("cast_close"), session, variant_b=variant_b)


def score_rows(rows: list[dict], *, fee: float = 0.0, variant_b: bool = False) -> dict:
    band = band_width(fee)
    grouped: dict[str, list[dict]] = defaultdict(list)
    ex_dates = []
    for row in rows:
        scale = (row.get("scale") or "day").strip().lower()
        session = datetime.strptime(row["date"], "%Y-%m-%d").date()
        change = _number(row.get("open_adj")), _number(row.get("close_adj"))
        if change[0] in (None, 0) or change[1] is None:
            continue
        result = change[1] / change[0] - 1
        cast = _cast_row(row, session, variant_b)
        if cast is None or cast.get("status") == "missing" or cast.get("tier") == "缺价":
            continue
        tier = cast["qishi_tier"]
        if _flag(row.get("ex_date")) or _factor_jump(row):
            ex_dates.append(
                {
                    "date": session.isoformat(),
                    "symbol": row.get("symbol"),
                    "scale": scale,
                    "tier": tier,
                }
            )
        grouped[scale].append(
            {
                "date": session.isoformat(),
                "month": session.strftime("%Y-%m"),
                "symbol": row.get("symbol"),
                "tier": tier,
                "relation": cast.get("relation"),
                "result": result,
                "bucket": direction(result, band),
            }
        )
    reports = {}
    for scale, items in grouped.items():
        summary = _summarize(items, band)
        by_month: dict[str, list[dict]] = defaultdict(list)
        for item in items:
            by_month[item["month"]].append(item)
        summary["months"] = {month: _summarize(by_month[month], band) for month in sorted(by_month)}
        reports[scale] = summary
    return {
        "band": band,
        "fee": fee,
        "variant_b": variant_b,
        "acceptance": "五档分列。比和不设平桶命中。三桶粗表不作为验收。",
        "denominator_index": DENOMINATOR_INDEX,
        "scales": reports,
        "ex_dates": ex_dates,
    }


def _summarize(items: list[dict], band: float) -> dict:
    tiers = {}
    for name in TIER_ORDER:
        subset = [item for item in items if item["tier"] == name]
        ups = sum(item["bucket"] == "up" for item in subset)
        flats = sum(item["bucket"] == "flat" for item in subset)
        downs = sum(item["bucket"] == "down" for item in subset)
        entry = {"n": len(subset), "up": ups, "flat": flats, "down": downs}
        if name == "震荡":
            entry["hit_rate"] = None
            entry["note"] = "比和不设平桶命中，只报告分布"
        elif name in {"偏多", "略偏多"}:
            entry["hits"] = ups
            entry["hit_rate"] = None if not subset else ups / len(subset)
        else:
            entry["hits"] = downs
            entry["hit_rate"] = None if not subset else downs / len(subset)
        tiers[name] = entry
    directional = [item for item in items if item["tier"] != "震荡"]
    baseline_hits = sum(item["bucket"] == "up" for item in directional)
    secondary_up = [item for item in items if item["tier"] in {"偏多", "略偏多"}]
    secondary_down = [item for item in items if item["tier"] in {"略偏空", "偏空"}]
    return {
        "tiers": tiers,
        "always_up_hit_rate": None if not directional else baseline_hits / len(directional),
        "always_up_n": len(directional),
        "secondary_buckets": {
            "acceptance": False,
            "up_n": len(secondary_up),
            "up_hit_rate": None if not secondary_up else sum(item["bucket"] == "up" for item in secondary_up) / len(secondary_up),
            "down_n": len(secondary_down),
            "down_hit_rate": None if not secondary_down else sum(item["bucket"] == "down" for item in secondary_down) / len(secondary_down),
            "bihe_excluded_from_flat": True,
        },
    }
