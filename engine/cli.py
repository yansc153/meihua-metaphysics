"""命令行。在仓库根目录运行：python3 -m engine"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from engine.backtest import load_csv, score_rows
from engine.board import ROOT, SECTORS_PATH, build_board, index_card, load_sectors, write_board
from engine.calendar_cn import NEW_YORK, session_for_clock
from engine.cast import cast_index, cast_prices
from engine.fetch_yahoo import build_rows, write_csv
from engine.report_page import write_page


def _session(text: str | None):
    if text:
        return datetime.strptime(text, "%Y-%m-%d").date()
    day, _passed = session_for_clock()
    return day


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="梅花日频预测引擎")
    parser.add_argument("command", nargs="?", default="build", choices=["build", "board", "card", "cast", "backtest", "year2026"])
    parser.add_argument("symbol", nargs="?")
    parser.add_argument("day", nargs="?")
    parser.add_argument("--session", help="目标会话 YYYY-MM-DD，默认按美东时钟取这场或下一场")
    parser.add_argument("--open", dest="open_print")
    parser.add_argument("--close", dest="close_print")
    parser.add_argument("--sectors", type=Path, default=SECTORS_PATH)
    parser.add_argument("--board-out", type=Path, default=ROOT / "dashboard" / "board.json")
    parser.add_argument("--card-out", type=Path, default=ROOT / "dashboard" / "index_card.json")
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--fee", type=float, default=0.0)
    parser.add_argument("--variant-b", action="store_true", help="打开失令挪档。默认关闭")
    args = parser.parse_args(argv)

    if args.command == "cast":
        day = datetime.strptime(args.day or args.session, "%Y-%m-%d").date()
        symbol = (args.symbol or "SPX").upper()
        if symbol in {"SPX", "^GSPC", "GSPC"}:
            _print(cast_index(day, variant_b=args.variant_b))
        else:
            _print(cast_prices(args.open_print, args.close_print, day, variant_b=args.variant_b))
        return 0

    if args.command == "year2026":
        rows = build_rows(2026)
        csv_path = write_csv(rows)
        report = score_rows(rows)
        dates = sorted({row["date"] for row in rows})
        page = write_page(
            report,
            source="Yahoo Finance 日线",
            first=dates[0],
            last=dates[-1],
            symbols=len({row["symbol"] for row in rows}),
        )
        print(f"行情 {csv_path}  {len(rows)} 行")
        print(f"报告 {page}")
        return 0

    if args.command == "backtest":
        if not args.csv:
            parser.error("backtest 需要 --csv")
        _print(score_rows(load_csv(args.csv), fee=args.fee, variant_b=args.variant_b))
        return 0

    session = _session(args.session or args.day)
    now = datetime.now(NEW_YORK)
    open_passed = session == now.date() and (now.hour, now.minute) >= (9, 30)
    if args.command in {"build", "card"}:
        card = index_card(session, open_passed=open_passed, variant_b=args.variant_b)
        write_board(card, args.card_out)
        print(f"指数卡 {args.card_out}  会话 {session.isoformat()}  {card['cast']['hexagram']}  {card['cast']['tier']}")
    if args.command in {"build", "board"}:
        board = build_board(session, load_sectors(args.sectors), variant_b=args.variant_b)
        write_board(board, args.board_out)
        print(f"板块板 {args.board_out}  {len(board['items'])} 只，已去掉 A 股")
    return 0
