"""从 sectors.json 生成板块板。A 股不进入样本。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from engine.cast import DENOMINATOR_INDEX, cast_index, cast_prices

ROOT = Path(__file__).resolve().parents[1]
SECTORS_PATH = ROOT / "dashboard" / "sectors.json"
# 看板上的指数行只展示时间卦。标普进分母，纳指同卦不进。
INDEX_ROWS = {
    "SPY": {"index_id": DENOMINATOR_INDEX, "in_denominator": True, "label": "标普"},
    "IXIC": {"index_id": "IXIC", "in_denominator": False, "label": "纳指"},
}


def load_sectors(path: Path | None = None) -> list[dict]:
    source = path or SECTORS_PATH
    with source.open(encoding="utf-8") as handle:
        payload = json.load(handle, parse_float=str, parse_int=str)
    return [row for row in payload if row.get("g") != "cn"]


def _blank(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in {"", "null", "none"}:
        return None
    return text


def build_board(session: date, sectors: list[dict] | None = None, *, variant_b: bool = False) -> dict:
    rows = sectors if sectors is not None else load_sectors()
    rows = [row for row in rows if row.get("g") != "cn"]
    index_cast = cast_index(session, variant_b=variant_b)
    items = []
    for row in rows:
        symbol = str(row["sym"])
        high = _blank(row.get("h"))
        low = _blank(row.get("l"))
        change = _blank(row.get("chg"))
        base = {
            "sym": symbol,
            "name": row.get("name"),
            "group": row.get("g"),
            "high": high,
            "low": low,
            "change": change,
            "basis": row.get("basis"),
        }
        if symbol in INDEX_ROWS:
            spec = INDEX_ROWS[symbol]
            day = dict(index_cast)
            day["counts_in_denominator"] = spec["in_denominator"]
            day["note"] = (
                "时间卦，不用开收盘。回测分母只计这一只。"
                if spec["in_denominator"]
                else "与标普同一农历日、同一巳时，卦相同，不进分母。"
            )
            items.append({**base, "kind": "index", "index_id": spec["index_id"], "day": day, "week": None})
            continue
        week_open = _blank(row.get("wo"))
        week_close = _blank(row.get("wc")) or _blank(row.get("c"))
        items.append(
            {
                **base,
                "kind": "sector" if row.get("g") in {"us", "cmd"} else "stock",
                "day": cast_prices(_blank(row.get("o")), _blank(row.get("c")), session, variant_b=variant_b),
                "week": cast_prices(week_open, week_close, session, variant_b=variant_b),
            }
        )
    return {
        "session": session.isoformat(),
        "hour_name": "巳",
        "hour": 6,
        "excluded": "A股（g=cn）不进入样本，页面不渲染",
        "denominator_index": DENOMINATOR_INDEX,
        "variant_b": variant_b,
        "items": items,
    }


def write_board(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def index_card(session: date, *, open_passed: bool = False, variant_b: bool = False) -> dict:
    cast = cast_index(session, variant_b=variant_b)
    return {
        "name": "标普",
        "symbol": DENOMINATOR_INDEX,
        "session": session.isoformat(),
        "open_passed": open_passed,
        "same_hexagram_not_in_denominator": ["IXIC"],
        "cast": cast,
    }
