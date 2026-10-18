"""从 Yahoo Finance 拉日线。印价用未复权开收盘，收益用复权开收盘。"""

from __future__ import annotations

import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

from engine.board import SECTORS_PATH

NEW_YORK = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "2026_us_daily.csv"
_COLUMNS = [
    "date",
    "symbol",
    "role",
    "scale",
    "cast_open",
    "cast_close",
    "open_raw",
    "close_raw",
    "open_adj",
    "close_adj",
    "prev_close_raw",
    "prev_close_adj",
    "ex_date",
]


def printed(value: float) -> str:
    """美股日线印到分。末尾的零不改变数字和。"""
    quant = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(quant, "f")


def adjusted(value: float) -> str:
    quant = Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return format(quant, "f")


def universe() -> list[tuple[str, str, str]]:
    """(yahoo代码, 样本代码, role)。A 股不进。IXIC 与标普同卦，不另计。"""
    rows = json.loads(SECTORS_PATH.read_text(encoding="utf-8"))
    symbols = [("SPX", "^GSPC", "index")]
    for row in rows:
        if row.get("g") == "cn" or row.get("sym") == "IXIC":
            continue
        symbols.append((str(row["sym"]), str(row["sym"]), "sector"))
    return symbols


def _chart(yahoo: str, start: datetime, end: datetime) -> dict:
    query = urllib.parse.urlencode(
        {
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "interval": "1d",
            "includeAdjustedClose": "true",
            "events": "div|split",
        }
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo)}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    payload = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                payload = json.load(response)
            break
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    result = payload["chart"]["result"]
    if not result:
        raise RuntimeError(payload["chart"].get("error") or yahoo)
    return result[0]


def _event_days(chart: dict) -> set[str]:
    days = set()
    events = chart.get("events") or {}
    for kind in ("dividends", "splits"):
        for item in (events.get(kind) or {}).values():
            stamp = item.get("date")
            if stamp:
                days.add(datetime.fromtimestamp(stamp, NEW_YORK).date().isoformat())
    return days


def _bars(chart: dict) -> list[dict]:
    stamps = chart.get("timestamp") or []
    quote = chart["indicators"]["quote"][0]
    adjusted_close = chart["indicators"].get("adjclose", [{}])[0].get("adjclose") or []
    rows = []
    for index, stamp in enumerate(stamps):
        raw_open = quote["open"][index]
        raw_close = quote["close"][index]
        adj_close = adjusted_close[index] if index < len(adjusted_close) else None
        if raw_open is None or raw_close is None or adj_close is None or raw_close == 0:
            continue
        factor = adj_close / raw_close
        day = datetime.fromtimestamp(stamp, NEW_YORK).date()
        rows.append(
            {
                "date": day,
                "open_raw": printed(raw_open),
                "close_raw": printed(raw_close),
                "open_adj": adjusted(raw_open * factor),
                "close_adj": adjusted(adj_close),
                "factor": factor,
            }
        )
    rows.sort(key=lambda item: item["date"])
    return rows


def build_rows(year: int = 2026) -> list[dict]:
    start = datetime(year - 1, 12, 1, tzinfo=NEW_YORK)
    end = datetime.now(NEW_YORK)
    scored = []
    for symbol, yahoo, role in universe():
        print(f"下载 {symbol} {yahoo}", flush=True)
        chart = _chart(yahoo, start, end)
        events = _event_days(chart)
        bars = _bars(chart)
        previous = None
        for bar in bars:
            if previous and bar["date"].year == year:
                factor_changed = abs(bar["factor"] - previous["factor"]) / abs(previous["factor"]) > 0.001
                scored.append(
                    {
                        "date": bar["date"].isoformat(),
                        "symbol": symbol,
                        "role": role,
                        "scale": "day",
                        "cast_open": previous["open_raw"],
                        "cast_close": previous["close_raw"],
                        "open_raw": bar["open_raw"],
                        "close_raw": bar["close_raw"],
                        "open_adj": bar["open_adj"],
                        "close_adj": bar["close_adj"],
                        "prev_close_raw": previous["close_raw"],
                        "prev_close_adj": previous["close_adj"],
                        "ex_date": "1" if bar["date"].isoformat() in events or factor_changed else "0",
                    }
                )
            previous = bar
        time.sleep(0.15)
    return scored


def write_csv(rows: list[dict], path: Path = CSV_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path
