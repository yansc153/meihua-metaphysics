"""把 2026 回测写成看板页。"""

from __future__ import annotations

import json
from pathlib import Path

from engine.cast import TIER_ORDER

ROOT = Path(__file__).resolve().parents[1]
PAGE_PATH = ROOT / "dashboard" / "backtest-2026.html"


def _pct(value) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _cell(entry: dict, tier: str) -> str:
    stats = entry["tiers"][tier]
    if stats["n"] == 0:
        return "<td>—</td>"
    if tier == "震荡":
        return (
            f"<td class='flat'>{stats['n']} 场<br>"
            f"<span>涨 {stats['up']} · 平 {stats['flat']} · 跌 {stats['down']}</span></td>"
        )
    return f"<td>{_pct(stats['hit_rate'])}<br><span>{stats['hits']}/{stats['n']}</span></td>"


def render(report: dict, *, source: str, first: str, last: str, symbols: int) -> str:
    day = report["scales"]["day"]
    months = day["months"]
    header = "".join(f"<th>{tier}</th>" for tier in TIER_ORDER)
    body = []
    for month, summary in months.items():
        cells = "".join(_cell(summary, tier) for tier in TIER_ORDER)
        body.append(f"<tr><th>{month}</th>{cells}</tr>")
    overall = "".join(_cell(day, tier) for tier in TIER_ORDER)
    ex_rows = report["ex_dates"]
    ex_html = "".join(
        f"<li>{item['date']} · {item['symbol']} · 起势 {item['tier']}</li>" for item in ex_rows
    ) or "<li>没有</li>"
    baseline = _pct(day["always_up_hit_rate"])
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>2026 梅花日频回测</title>
<style>
  :root {{ --ink:#1c1612; --muted:#6e6258; --paper:#f4eee4; --line:#e4d8c8; --up:#c23b32; --down:#1f7a4d; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; color:var(--ink); background:var(--paper); font-family:"Songti SC","Noto Serif SC",serif; }}
  main {{ max-width:1100px; margin:0 auto; padding:28px 18px 64px; }}
  h1 {{ margin:0; font-size:28px; }}
  p {{ color:var(--muted); line-height:1.7; }}
  table {{ width:100%; border-collapse:collapse; background:#fffdf8; }}
  th, td {{ border-bottom:1px solid var(--line); padding:10px 8px; text-align:right; vertical-align:top; font-weight:500; }}
  th:first-child, td:first-child {{ text-align:left; }}
  thead th {{ font-size:14px; }}
  td span, td.flat {{ color:var(--muted); font-size:12px; }}
  .note {{ font-size:13px; }}
  ul {{ columns:2; padding-left:18px; font-size:14px; }}
  @media (max-width:700px) {{ ul {{ columns:1; }} }}
</style>
</head>
<body>
<main>
  <h1>2026 梅花日频回测</h1>
  <p class="note">{first} 至 {last} · {symbols} 个代码 · 来源 {source}<br>
  指数只计标普，时间卦用美东巳时。板块和商品 ETF 用上一场印价的开收盘数字和。<br>
  收益是复权开盘到复权收盘。命中带 {report['band'] * 100:.2f}%。偏多、略偏多对照上涨，略偏空、偏空对照下跌。震荡不设平桶命中，格子里是场数和涨平跌分布。<br>
  始终看多的命中率 {baseline}（{day['always_up_n']} 场方向档）。变体 B 关闭。</p>
  <h2>全年</h2>
  <table>
    <thead><tr><th></th>{header}</tr></thead>
    <tbody><tr><th>2026</th>{overall}</tr></tbody>
  </table>
  <h2>分月</h2>
  <table>
    <thead><tr><th>月份</th>{header}</tr></thead>
    <tbody>
      {''.join(body)}
    </tbody>
  </table>
  <h2>除权除息日</h2>
  <p class="note">这些日子另列，仍用复权收益留在上面的命中率里。共 {len(ex_rows)} 场。</p>
  <ul>{ex_html}</ul>
</main>
</body>
</html>
"""


def write_page(report: dict, path: Path = PAGE_PATH, **meta) -> Path:
    path.write_text(render(report, **meta), encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
