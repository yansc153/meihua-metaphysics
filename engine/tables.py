"""生成 64 卦 × 6 动爻规则表。旺衰不写入格内。"""

from __future__ import annotations

import json
from pathlib import Path

from engine.cast import (
    NAMES,
    TRIGRAMS,
    VERDICTS,
    _BITS,
    relation,
)

ROOT = Path(__file__).resolve().parents[1]
RULE_PATH = ROOT / "knowledge_base" / "meihua_64x6.json"
QIJI_PATH = ROOT / "knowledge_base" / "qiji_64x64.json"


def _cell(upper: int, lower: int, moving: int) -> dict:
    upper_name, _, upper_bits = TRIGRAMS[upper]
    lower_name, _, lower_bits = TRIGRAMS[lower]
    lines = list(lower_bits + upper_bits)
    changed = lines.copy()
    changed[moving - 1] = 1 - changed[moving - 1]
    changed_lower = _BITS[tuple(changed[:3])]
    changed_upper = _BITS[tuple(changed[3:])]
    if moving <= 3:
        use, body = lower, upper
        changed_use = changed_lower
    else:
        use, body = upper, lower
        changed_use = changed_upper
    _, body_element, _ = TRIGRAMS[body]
    _, use_element, _ = TRIGRAMS[use]
    _, changed_element, _ = TRIGRAMS[changed_use]
    opening = relation(body_element, use_element)
    closing = relation(body_element, changed_element)
    opening_phrase, opening_tier = VERDICTS[opening]
    closing_phrase, closing_tier = VERDICTS[closing]
    return {
        "upper": upper_name,
        "lower": lower_name,
        "hexagram": NAMES[(upper, lower)],
        "moving": moving,
        "body_element": body_element,
        "use_element": use_element,
        "relation": opening,
        "phrase": opening_phrase,
        "tier": opening_tier,
        "changed": NAMES[(changed_upper, changed_lower)],
        "closing_relation": closing,
        "closing_phrase": closing_phrase,
        "closing_tier": closing_tier,
    }


def build_rule_table() -> dict:
    cells = {}
    for upper in range(1, 9):
        for lower in range(1, 9):
            name = NAMES[(upper, lower)]
            cells[name] = {str(moving): _cell(upper, lower, moving) for moving in range(1, 7)}
    return {
        "kind": "meihua-64x6",
        "cell_count": 64 * 6,
        "note": "键是本卦加一个动爻。时间卦式子不要求铺满这 384 格。旺衰在运行时按目标日节气计算。",
        "cells": cells,
    }


def write_tables() -> tuple[Path, Path]:
    RULE_PATH.write_text(json.dumps(build_rule_table(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not QIJI_PATH.exists():
        QIJI_PATH.write_text(
            json.dumps(
                {
                    "kind": "qiji-64x64",
                    "note": "只收录从 1996 原文摘出的句子。没有的键不出现，服务不编造。",
                    "entries": {},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return RULE_PATH, QIJI_PATH
