"""从 1996《预测致胜》摘「本卦变变卦」原文。摘不到的键留空，不补句子。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from engine.cast import NAMES, TRIGRAMS, VERDICTS, relation

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "knowledge_base" / "1996_预测致胜_期货股票运筹韬略.md"
OUT = ROOT / "knowledge_base" / "qiji_64x64.json"

# 上卦、下卦，先天数。顺序是周易卦序。
KING_WEN = [
    (1, 1), (8, 8), (6, 4), (7, 6), (6, 1), (1, 6), (8, 6), (6, 8),
    (5, 1), (1, 2), (8, 1), (1, 8), (1, 3), (3, 1), (8, 7), (4, 8),
    (2, 4), (7, 5), (8, 2), (5, 8), (3, 4), (7, 3), (7, 8), (8, 4),
    (1, 4), (7, 1), (7, 4), (2, 5), (6, 6), (3, 3), (2, 7), (4, 5),
    (1, 7), (4, 1), (3, 8), (8, 3), (5, 3), (3, 2), (6, 7), (4, 6),
    (7, 2), (5, 4), (2, 1), (1, 5), (2, 8), (8, 5), (2, 6), (5, 6),
    (2, 3), (3, 5), (4, 4), (7, 7), (5, 7), (4, 2), (4, 3), (3, 7),
    (5, 5), (2, 2), (6, 5), (6, 2), (5, 2), (4, 7), (6, 3), (3, 6),
]
SHORT = [
    "乾", "坤", "屯", "蒙", "需", "讼", "师", "比", "小畜", "履",
    "泰", "否", "同人", "大有", "谦", "豫", "随", "蛊", "临", "观",
    "噬嗑", "贲", "剥", "复", "无妄", "大畜", "颐", "大过", "坎", "离",
    "咸", "恒", "遯", "大壮", "晋", "明夷", "家人", "睽", "蹇", "解",
    "损", "益", "夬", "姤", "萃", "升", "困", "井", "革", "鼎",
    "震", "艮", "渐", "归妹", "丰", "旅", "巽", "兑", "涣", "节",
    "中孚", "小过", "既济", "未济",
]


def lines_of(upper: int, lower: int) -> tuple[int, ...]:
    return TRIGRAMS[lower][2] + TRIGRAMS[upper][2]


BITS = {short: lines_of(*pair) for short, pair in zip(SHORT, KING_WEN)}
BY_LEN = sorted(SHORT, key=len, reverse=True)


def moving_line(base: str, changed: str) -> int | None:
    left, right = BITS[base], BITS[changed]
    diffs = [index for index, (a, b) in enumerate(zip(left, right)) if a != b]
    if len(diffs) != 1:
        return None
    return diffs[0] + 1


def ti_yong(base: str, moving: int | None) -> dict | None:
    if moving is None:
        return None
    upper, lower = next(pair for short, pair in zip(SHORT, KING_WEN) if short == base)
    use, body = (lower, upper) if moving <= 3 else (upper, lower)
    body_element = TRIGRAMS[body][1]
    use_element = TRIGRAMS[use][1]
    rel = relation(body_element, use_element)
    phrase, tier = VERDICTS[rel]
    return {"relation": rel, "phrase": phrase, "tier": tier}


def bare_name(line: str) -> str | None:
    named = match_name(line, 0)
    if not named:
        return None
    if line[named[1]:].strip(" ，,"):
        return None
    return named[0]


def match_name(text: str, start: int) -> tuple[str, int] | None:
    for name in BY_LEN:
        token = "遁" if name == "遯" else name
        if text.startswith(token, start):
            return name, start + len(token)
        if name == "遯" and text.startswith("遯", start):
            return name, start + 1
    # OCR sometimes splits a two- or three-character name: 「变小 过」.
    for name in BY_LEN:
        token = "遁" if name == "遯" else name
        if len(token) < 2:
            continue
        for cut in range(1, len(token)):
            for gap in (" ", "　"):
                spaced = token[:cut] + gap + token[cut:]
                if text.startswith(spaced, start):
                    return name, start + len(spaced)
    return None


def extract() -> dict[tuple[str, str], dict]:
    raw = BOOK.read_text(encoding="utf-8")
    pages = []
    for chunk in re.split(r"\n## 第 (\d+) 页\n", raw)[1:]:
        pass
    parts = re.split(r"\n## 第 (\d+) 页\n", raw)
    # parts[0] is title, then page number, body, page number, body...
    page_no = None
    chunks: list[tuple[int, str]] = []
    index = 1
    while index < len(parts):
        page_no = int(parts[index])
        body = parts[index + 1]
        body = re.sub(r"第\s*[０-９0-9]+\s*页", "", body)
        chunks.append((page_no, body))
        index += 2
    found: dict[tuple[str, str], dict] = {}
    last_base: str | None = None
    for page_no, body in chunks:
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        cursor = 0
        while cursor < len(lines):
            line = lines[cursor]
            skip_after = 0
            if last_base and not match_name(line, 0):
                # 「噬    变师」把「噬嗑」的第二个字扫丢了。
                mark = line.find("变")
                if 0 < mark <= 6 and all(ch.isspace() or ch in last_base for ch in line[:mark]):
                    line = last_base + line[mark:]
            bare = re.match(r"^变\s*", line)
            if bare:
                tail = line[bare.end():].lstrip()
                target = match_name(tail, 0)
                prev = lines[cursor - 1] if cursor else ""
                named = match_name(prev, 0) if prev else None
                if target and named and "变" not in prev[: named[1] + 3]:
                    before = prev[named[1]:].lstrip("，, ")
                    after = tail[target[1]:].lstrip("，, ")
                    line = f"{named[0]}变{target[0]}，{before}{after}"
                elif target and cursor + 1 < len(lines) and bare_name(lines[cursor + 1]):
                    # 「变谦」在上一行，卦名「蹇」被排到了下一行。
                    nxt_base = bare_name(lines[cursor + 1])
                    after = tail[target[1]:].lstrip("，, ")
                    cont = ""
                    if cursor + 2 < len(lines) and not starts_header(lines, cursor + 2):
                        cont = lines[cursor + 2].lstrip("，, ")
                        skip_after = 2
                    else:
                        skip_after = 1
                    line = f"{nxt_base}变{target[0]}，{after}{cont}"
                elif target and last_base:
                    # 这一行只剩「变讼」，卦名在上一条，扫描时掉了。
                    after = tail[target[1]:].lstrip("，, ")
                    line = f"{last_base}变{target[0]}，{after}"
            if cursor + 1 < len(lines):
                nxt = lines[cursor + 1]
                if bare_name(line) and (nxt.startswith("变") or nxt.startswith("不变")):
                    line = line + nxt
                    cursor += 1
            hit = header_at(line)
            if not hit:
                cursor += 1
                continue
            base, changed, rest = hit
            last_base = base
            pieces = [rest]
            cursor += 1 + skip_after
            while cursor < len(lines) and not starts_header(lines, cursor):
                piece = lines[cursor].strip()
                if piece:
                    pieces.append(piece)
                cursor += 1
            text = re.sub(r"\s+", "", "".join(pieces))
            text = text.strip("，,。")
            if not text:
                continue
            key = (base, changed)
            if key not in found:
                found[key] = {"verdict": text, "source": f"1996第{page_no}页"}
    return found


def starts_header(lines: list[str], cursor: int) -> bool:
    line = lines[cursor]
    if re.match(r"^[\u4e00-\u9fff]\s+变", line) and match_name(line[line.find("变") + 1:].lstrip(), 0):
        return True
    if re.match(r"^变\s*", line):
        tail = line[line.find("变") + 1:].lstrip()
        if match_name(tail, 0):
            return True
    if cursor + 1 < len(lines):
        nxt = lines[cursor + 1]
        if bare_name(line) and (nxt.startswith("变") or nxt.startswith("不变")):
            return True
    return header_at(line) is not None


def header_at(line: str) -> tuple[str, str, str] | None:
    if not line:
        return None
    matched = match_name(line, 0)
    if not matched:
        return None
    base, end = matched
    window = line[end:end + 8]
    if "不变" in window:
        mark = line.find("不变", end)
        rest = line[mark + 2:]
        rest = re.sub(r"^[卦\s，,]*", "", rest)
        return base, base, rest
    # 扫描把「变」认成「度」，或直接把「变」丢掉：贲度升、小畜未济。
    mark = line.find("变", end)
    if mark < 0 or mark - end > 6:
        degree = line.find("度", end)
        if 0 <= degree - end <= 6:
            mark = degree
        else:
            naked = line[end:].lstrip()
            alt = match_name(naked, 0)
            if not alt:
                return None
            rest = naked[alt[1]:].lstrip()
            if not rest.startswith(("，", ",")):
                return None
            rest = rest.lstrip("，, ")
            return base, alt[0], rest
    tail = line[mark + 1:].lstrip()
    if tail.startswith("变"):
        doubled = match_name(tail[1:].lstrip(), 0)
        if doubled:
            tail = tail[1:].lstrip()
    target = match_name(tail, 0)
    if not target and tail.startswith("归"):
        # 「变归丰」是上一行「归妹」带下来的错字，后面才是丰。
        skipped = match_name(tail[1:].lstrip(), 0)
        if skipped:
            tail = tail[1:].lstrip()
            target = skipped
    if not target:
        # 困卦里三个卦名被扫错：盅=蛊，现=观，无=无妄。只认后面紧跟空格或逗号。
        alias = {"盅": "蛊", "现": "观", "无": "无妄"}
        if tail[:1] in alias and len(tail) > 1 and tail[1] in " 　，,":
            changed = alias[tail[:1]]
            rest = tail[1:]
            rest = re.sub(r"^[^\u4e00-\u9fff，,。]{0,4}", "", rest)
            rest = re.sub(r"^[\u4e00-\u9fff][，,]", "", rest)
            rest = re.sub(r"^[，,]\s*", "", rest)
            return base, changed, rest
        return None
    changed, target_end = target
    rest = tail[target_end:]
    rest = re.sub(r"^[^\u4e00-\u9fff，,。]{0,4}", "", rest)
    # 乾卦前几条在卦名和逗号之间夹了一个扫描错字：韨，不宜做单。
    rest = re.sub(r"^[\u4e00-\u9fff][，,]", "", rest)
    rest = re.sub(r"^[，,]\s*", "", rest)
    return base, changed, rest


def build() -> dict:
    found = extract()
    entries = {}
    filled = 0
    empty_one_line = 0
    empty_not_one_line = 0
    for base in SHORT:
        for changed in SHORT:
            moving = moving_line(base, changed)
            row = {
                "base": base,
                "changed": changed,
                "moving": moving,
                "ti_yong": ti_yong(base, moving),
                "verdict": None,
                "source": None,
                "empty_reason": None,
            }
            hit = found.get((base, changed))
            if hit:
                row["verdict"] = hit["verdict"]
                row["source"] = hit["source"]
                filled += 1
            elif moving is None and base != changed:
                row["empty_reason"] = "1996 原文没有摘到这一条。1999、2006、2011 没有本卦变变卦这张表。这条也不是一条动爻能走到的变卦。"
                empty_not_one_line += 1
            elif base == changed and moving is None:
                row["empty_reason"] = "1996 这一卦的「不变卦」没有摘到。1999、2006、2011 没有本卦变变卦这张表。"
                empty_not_one_line += 1
            else:
                row["empty_reason"] = "一条动爻可以走到这卦，但 1996 原文没有摘到这一条。1999、2006、2011 没有本卦变变卦这张表。"
                empty_one_line += 1
            entries[f"{base}|{changed}"] = row
    return {
        "kind": "qiji-64x64",
        "note": "本卦到变卦。断语只来自 1996《预测致胜》原文。1999、2006、2011 没有这张网格。摘不到的格子 verdict 为空。",
        "total": 4096,
        "filled": filled,
        "empty": 4096 - filled,
        "empty_not_one_moving_line": empty_not_one_line,
        "empty_one_moving_line_but_unextracted": empty_one_line,
        "entries": entries,
    }


def main() -> None:
    payload = build()
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in payload if k != "entries"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
