from __future__ import annotations

import json
from pathlib import Path


def write_cluster_report(clusters: list[dict], output: Path) -> Path:
    lines = [
        "# SRC-2026-VFXLIB-001 视觉主题候选联系表",
        "",
        "> 本表是基于文件名关键词的保守候选聚类，不是逐帧视觉判断，也不证明实现方式。",
        "",
        "| 候选主题 | 媒体数 | 证据等级 | 命中词 |",
        "|---|---:|---|---|",
    ]
    for cluster in sorted(clusters, key=lambda item: (-item["media_count"], item["theme"])):
        terms = ", ".join(cluster["matched_terms"]) or "无"
        lines.append(f"| `{cluster['theme']}` | {cluster['media_count']} | `{cluster['evidence_level']}` | {terms} |")
    lines.extend(["", "## 代表路径", ""])
    for cluster in sorted(clusters, key=lambda item: (-item["media_count"], item["theme"])):
        lines.append(f"### `{cluster['theme']}`")
        lines.append("")
        lines.append(f"- 媒体数：{cluster['media_count']}")
        lines.append(f"- 解释：{cluster['interpretation']}")
        for path in cluster["relative_paths"][:8]:
            lines.append(f"- 证据路径：`{path}`")
        if cluster["media_count"] > 8:
            lines.append(f"- 其余：见同目录 `assignments.jsonl`，按 `media_id` 和 `relative_path` 回溯。")
        lines.append("")
    lines.extend([
        "## 使用限制",
        "",
        "1. 文件名可能来自下载页标题、作者名、站点名或下载器默认名；关键词命中不等于画面实际包含该元素。",
        "2. `unclassified` 条目必须通过代表帧或人工观看后才能继续分类。",
        "3. 本表不支持制作步骤、Shader、粒子参数或材质结论；这些需要明确操作证据与 Unity 实验。",
        "4. 后续审美卡片必须引用本表之外的帧/时间点证据，不得只引用主题名。",
    ])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def main() -> int:
    root = Path(__file__).resolve().parents[3] / "workspace" / "data" / "resource_index" / "vfx_library" / "clusters"
    clusters = json.loads((root / "clusters.json").read_text(encoding="utf-8"))
    write_cluster_report(clusters, root / "clusters.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
