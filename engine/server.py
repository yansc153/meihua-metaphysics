"""独立起卦 HTTP 服务。不做登录、不算配额。"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

from engine.calendar_cn import NEW_YORK, SHANGHAI, next_session
from engine.cast import US_HOUR, cast_index, cast_prices, is_reversal
from engine.tables import QIJI_PATH, RULE_PATH, write_tables

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = Path(__import__("os").environ.get("MEIHUA_CSV", ROOT / "data" / "2026_us_daily.csv"))
RULES_VERSION = "tiyong-5"
SECTORS = (
    "DIA", "IWM", "XLC", "XLY", "XLF", "XLI", "XLB", "XLE",
    "XLV", "XLP", "XLRE", "XLU", "GLD", "SLV", "USO", "IBIT",
)
AI_GROUPS = ("QQQ", "XLK", "SMH")
ALLOW = set(SECTORS) | set(AI_GROUPS)

_PRINTS: dict[str, dict[date, tuple[str, str]]] = defaultdict(dict)


def load_prints(path: Path = CSV_PATH) -> None:
    _PRINTS.clear()
    if not path.is_file():
        return
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            symbol = (row.get("symbol") or "").upper()
            if symbol not in ALLOW:
                continue
            try:
                day = date.fromisoformat(row["date"])
            except ValueError:
                continue
            _PRINTS[symbol][day] = (row.get("open_raw") or "", row.get("close_raw") or "")


def shanghai_hour_branch(moment: datetime) -> int:
    hour = moment.astimezone(SHANGHAI).hour
    if hour in (23, 0):
        return 1
    return (hour + 1) // 2 + 1


def _public(record: dict) -> dict:
    if record.get("status") == "missing":
        return {"status": "missing", "tier": "缺价", "phrase": "缺价"}
    opening = record.get("qishi_tier")
    closing = record.get("shoushi_tier")
    return {
        "status": "ok",
        "hexagram": record.get("hexagram"),
        "mutual": record.get("mutual"),
        "changed": record.get("changed"),
        "moving": record.get("moving"),
        "relation": record.get("relation"),
        "phrase": record.get("phrase"),
        "qishi_tier": opening,
        "qishi_phrase": record.get("qishi_phrase"),
        "shoushi_tier": closing,
        "shoushi_phrase": record.get("shoushi_phrase"),
        "qi": record.get("qi"),
        "qi_detail": record.get("qi_detail"),
        "reversal": is_reversal(opening or "", closing or ""),
    }


def previous_prints(symbol: str, session: date) -> tuple[str, str] | None:
    days = [day for day in _PRINTS.get(symbol, {}) if day < session]
    if not days:
        return None
    return _PRINTS[symbol][max(days)]


def daily_payload(session_text: str | None, symbols: list[str] | None) -> dict:
    if session_text:
        session = next_session(date.fromisoformat(session_text), inclusive=True)
    else:
        session = next_session(datetime.now(NEW_YORK).date(), inclusive=True)
    wanted = symbols if symbols is not None else list(SECTORS) + list(AI_GROUPS)
    rejected = [symbol for symbol in wanted if symbol.upper() not in ALLOW]
    if rejected:
        raise ValueError("symbol not allowed")
    index = _public(cast_index(session, hour=US_HOUR))
    index["symbol"] = "SPX"

    def group(names: tuple[str, ...]) -> list[dict]:
        items = []
        for symbol in names:
            if symbols is not None and symbol not in {item.upper() for item in wanted}:
                continue
            pair = previous_prints(symbol, session)
            if pair is None:
                record = _public(cast_prices(None, None, session))
            else:
                record = _public(cast_prices(pair[0], pair[1], session))
            record["symbol"] = symbol
            items.append(record)
        return items

    return {
        "session": session.isoformat(),
        "index": index,
        "sectors": group(SECTORS),
        "ai": group(AI_GROUPS),
    }


def question_payload(symbol: str, asked_at: str, note: str) -> dict:
    if symbol.upper() not in ALLOW and symbol.upper() != "SPX":
        raise ValueError("symbol not allowed")
    moment = datetime.fromisoformat(asked_at)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=SHANGHAI)
    local = moment.astimezone(SHANGHAI)
    record = _public(cast_index(local.date(), hour=shanghai_hour_branch(local)))
    record["symbol"] = symbol.upper()
    record["note"] = note
    record["hour"] = shanghai_hour_branch(local)
    return record


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode())

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] != "/v1/health":
            self._json(404, {"error": "not-found"})
            return
        self._json(200, {"service": "meihua", "rules": RULES_VERSION})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            body = self._read()
            if path == "/v1/cast/daily":
                payload = daily_payload(body.get("session"), body.get("symbols"))
            elif path == "/v1/cast/question":
                payload = question_payload(
                    str(body.get("symbol") or ""),
                    str(body.get("asked_at") or ""),
                    str(body.get("note") or ""),
                )
            else:
                self._json(404, {"error": "not-found"})
                return
        except (ValueError, KeyError, json.JSONDecodeError):
            self._json(400, {"error": "bad-request"})
            return
        self._json(200, payload)


def main() -> None:
    write_tables()
    load_prints()
    if not RULE_PATH.is_file() or not QIJI_PATH.is_file():
        raise SystemExit("lookup tables missing")
    server = ThreadingHTTPServer(("0.0.0.0", 8090), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
