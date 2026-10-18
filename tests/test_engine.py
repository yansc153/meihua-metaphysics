import unittest
from datetime import date

from engine.backtest import score_rows
from engine.board import build_board
from engine.calendar_cn import gregorian_to_lunar, is_nyse_session, next_session, solar_month
from engine.cast import cast_index, cast_prices, digit_sum


class CalendarTests(unittest.TestCase):
    def test_year_branch_changes_on_lunar_new_year(self):
        before = gregorian_to_lunar(date(2026, 2, 16))
        new_year = gregorian_to_lunar(date(2026, 2, 17))
        self.assertEqual((before.year, before.branch_name), (2025, "巳"))
        self.assertEqual((new_year.year, new_year.month, new_year.day, new_year.branch_name), (2026, 1, 1, "午"))

    def test_dashboard_anchor_date(self):
        lunar = gregorian_to_lunar(date(2026, 10, 19))
        self.assertEqual((lunar.year, lunar.month, lunar.day, lunar.branch), (2026, 9, 10, 7))

    def test_solar_term_not_lunar_month(self):
        self.assertEqual(solar_month(date(2026, 2, 3))[0], "丑")
        self.assertEqual(solar_month(date(2026, 2, 4))[0], "寅")
        self.assertEqual(solar_month(date(2026, 10, 19))[0], "戌")

    def test_session_roll(self):
        self.assertFalse(is_nyse_session(date(2026, 7, 3)))
        self.assertFalse(is_nyse_session(date(2026, 4, 3)))
        self.assertEqual(next_session(date(2026, 10, 16), inclusive=False), date(2026, 10, 19))


class CastTests(unittest.TestCase):
    def test_digit_sum_ignores_trailing_zero_padding(self):
        self.assertEqual(digit_sum("763.3"), digit_sum("763.30"))
        self.assertNotEqual(digit_sum("763.30"), digit_sum("763.301"))

    def test_index_uses_si_hour_and_five_phrases(self):
        cast = cast_index(date(2026, 10, 19))
        self.assertEqual(cast["hour"], 6)
        self.assertEqual(cast["year_branch_name"], "午")
        self.assertEqual(cast["relation"], "用生体")
        self.assertEqual(cast["phrase"], "用生体，有进益")
        self.assertEqual(cast["qishi_tier"], "偏多")
        self.assertEqual(cast["shoushi_tier"], "略偏空")
        self.assertTrue(cast["shoushi_display_only"])
        self.assertFalse(cast["variant_b"])
        self.assertEqual(cast["qi"], "体中")
        self.assertEqual(cast["solar_branch"], "戌")

    def test_variant_b_off_does_not_move_tier(self):
        # 戌月金不是当令也不是失令。换一个体为土、用生体的日子会失令。
        cast = cast_index(date(2026, 10, 8))
        self.assertEqual(cast["tier"], cast["qishi_tier"])
        self.assertFalse(cast["variant_b"])

    def test_price_cast_uses_printed_digits(self):
        plain = cast_prices("763.3", "100", date(2026, 10, 19))
        padded = cast_prices("763.30", "100", date(2026, 10, 19))
        moved = cast_prices("763.301", "100", date(2026, 10, 19))
        self.assertEqual((plain["upper"], plain["lower"], plain["moving"]), (padded["upper"], padded["lower"], padded["moving"]))
        self.assertNotEqual(plain["upper"], moved["upper"])

    def test_missing_price(self):
        cast = cast_prices(None, "10", date(2026, 10, 19))
        self.assertEqual(cast["tier"], "缺价")


class BoardTests(unittest.TestCase):
    def test_a_shares_dropped_and_indexes_share_time_hexagram(self):
        rows = [
            {"g": "us", "sym": "SPY", "name": "标普500", "o": "1", "c": "2", "h": "3", "l": "1", "wo": "1"},
            {"g": "us", "sym": "IXIC", "name": "纳指", "o": "9", "c": "9", "h": "9", "l": "9", "wo": "9"},
            {"g": "us", "sym": "XLK", "name": "科技", "o": "188.28", "c": "183.47", "h": "188.54", "l": "182.82", "wo": "198.07"},
            {"g": "cn", "sym": "000001.SS", "name": "上证", "o": "1", "c": "1"},
            {"g": "us", "sym": "EMPTY", "name": "缺周开盘", "o": "10", "c": "11", "wo": None, "wc": None},
        ]
        # EMPTY week close falls back to c, so week still casts. Use a row with no close.
        rows[4]["c"] = None
        board = build_board(date(2026, 10, 19), rows)
        symbols = [item["sym"] for item in board["items"]]
        self.assertNotIn("000001.SS", symbols)
        spy = next(item for item in board["items"] if item["sym"] == "SPY")
        ixic = next(item for item in board["items"] if item["sym"] == "IXIC")
        self.assertEqual(spy["day"]["method"], "time")
        self.assertEqual(spy["day"]["hexagram"], ixic["day"]["hexagram"])
        self.assertTrue(spy["day"]["counts_in_denominator"])
        self.assertFalse(ixic["day"]["counts_in_denominator"])
        xlk = next(item for item in board["items"] if item["sym"] == "XLK")
        self.assertEqual(xlk["day"]["method"], "digits")
        self.assertNotIn("h", "".join(str(xlk["day"].get("open_print")) + str(xlk["day"].get("close_print"))))
        empty = next(item for item in board["items"] if item["sym"] == "EMPTY")
        self.assertEqual(empty["day"]["tier"], "缺价")
        self.assertEqual(empty["week"]["tier"], "缺价")


class BacktestTests(unittest.TestCase):
    def test_five_tiers_and_bihe_not_flat(self):
        rows = [
            {
                "date": "2026-10-19",
                "symbol": "SPX",
                "role": "index",
                "scale": "day",
                "open_adj": "100",
                "close_adj": "101",
            },
            {
                "date": "2026-10-19",
                "symbol": "IXIC",
                "role": "index",
                "scale": "day",
                "open_adj": "100",
                "close_adj": "50",
            },
            {
                "date": "2026-10-19",
                "symbol": "XLK",
                "role": "sector",
                "scale": "day",
                "cast_open": "10",
                "cast_close": "10",
                "open_adj": "100",
                "close_adj": "100",
                "open_raw": "50",
                "close_raw": "100",
                "ex_date": "1",
            },
        ]
        report = score_rows(rows)
        day = report["scales"]["day"]
        self.assertEqual(day["tiers"]["偏多"]["n"], 1)
        self.assertIsNone(day["tiers"]["震荡"]["hit_rate"])
        self.assertEqual(len(report["ex_dates"]), 1)
        self.assertEqual(report["ex_dates"][0]["symbol"], "XLK")
        self.assertFalse(day["secondary_buckets"]["acceptance"])
        symbols_would_have_doubled = day["tiers"]["偏多"]["n"] + day["tiers"]["略偏多"]["n"]
        self.assertEqual(symbols_would_have_doubled, 1)


if __name__ == "__main__":
    unittest.main()
