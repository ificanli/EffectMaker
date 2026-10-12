from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable

_THEME_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("lightning", ("lightning", "thunder", "雷电", "闪电", "雷")),
    ("fire", ("fire", "flame", "burn", "火焰", "火")),
    ("explosion", ("explosion", "爆炸", "爆破", "blast", "impact")),
    ("smoke", ("smoke", "烟雾", "烟", "dust", "尘")),
    ("water", ("water", "splash", "liquid", "水", "水花")),
    ("ice", ("ice", "frost", "snow", "冰", "寒")),
    ("energy", ("energy", "power", "orb", "electric", "能量", "光球")),
    ("magic-circle", ("magic circle", "magic-circle", "法阵", "魔法阵", "符文")),
    ("shield", ("shield", "barrier", "护盾", "屏障")),
    ("slash", ("slash", "blade", "sword", "刀光", "斩击")),
    ("trail", ("trail", "ribbon", "拖尾", "轨迹")),
    ("portal", ("portal", "传送门", "传送")),
    ("blood", ("blood", "bleed", "gore", "血", "出血")),
)


def _contains(text: str, term: str) -> bool:
    return term.casefold() in text.casefold()


def classify_title(title: str) -> dict[str, Any]:
    normalized = re.sub(r"\s+", " ", title).strip()
    matches: list[tuple[str, str]] = []
    for theme, terms in _THEME_TERMS:
        for term in terms:
            if _contains(normalized, term):
                matches.append((theme, term))
                break
    if not matches:
        return {"theme": "unclassified", "matched_terms": [], "evidence_level": "no-theme-evidence"}
    theme, _ = matches[0]
    return {
        "theme": theme,
        "matched_terms": [term for _, term in matches],
        "evidence_level": "title-keyword",
    }


def build_clusters(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        classification = classify_title(record["relative_path"])
        groups[classification["theme"]].append({**record, "classification": classification})
    result: list[dict[str, Any]] = []
    for theme in sorted(groups):
        items = sorted(groups[theme], key=lambda item: item["relative_path"])
        terms = sorted({term for item in items for term in item["classification"]["matched_terms"]})
        result.append({
            "theme": theme,
            "media_count": len(items),
            "media_ids": [item["media_id"] for item in items],
            "relative_paths": [item["relative_path"] for item in items],
            "matched_terms": terms,
            "evidence_level": "title-keyword" if theme != "unclassified" else "no-theme-evidence",
            "interpretation": "候选主题，仅表示文件名关键词命中；不代表视觉内容或实现方式已验证。",
        })
    return result
