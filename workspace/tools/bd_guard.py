"""bdg — Beads 强制工作记录门禁。

在真实 bd CLI 之上包一层校验，强制"每阶段写结果、完成写结论、弯路必记录"。

子命令（等价 bd 命令，但带强制校验）：
  bdg create  带守卫创建任务（缺描述/验收标准/备注之一 → 拒绝）
  bdg close   带守卫关闭任务（缺 --reason → 拒绝；--require-notes 时缺备注 → 拒绝）
  bdg note    追加阶段记录（备注）到任务
  bdg update  修订验收标准并追加记录（不修改状态或覆盖历史）
  bdg comment 追加评论（交流讨论）到任务
  bdg guard-check  扫描不合规任务并输出报告

用法：
  python -m workspace.tools.bd_guard create "标题" --description "..." --acceptance "..." --notes "..."
  python -m workspace.tools.bd_guard close <id> --reason "完成，产出 ..."
  python -m workspace.tools.bd_guard close <id> --reason "..." --require-notes
  python -m workspace.tools.bd_guard note <id> "阶段结论：...（弯路：X → Y）"
  python -m workspace.tools.bd_guard guard-check [--format json]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# 强制关闭时要求的最低备注关键词（命中任一且内容足够长，才视为"有结论"）
CONCLUSION_KEYWORDS = ("完成", "产出", "沉淀", "弯路", "结果", "记录")
CONCLUSION_MIN_LEN = 8
LEGACY_TAG = "legacy"  # 历史不合规任务的标记标签


def bd_cmd() -> list[str]:
    """返回真实 bd 可执行文件路径（绕过 PATH 中的守卫 wrapper）。

    依次探测 npm prefix -g（bin 目录，Windows shim 所在）、npm root -g
    （node_modules，POSIX 常见安装位置）下的真实 bd，最后回退 shutil.which。
    PATH 里可能有 workspace/bin 的守卫 wrapper，工具链自身必须调用真实 bd
    以免递归守卫。
    """

    def _npm_out(cmd: str) -> str:
        # Windows 上 npm 是 .CMD shim，subprocess 直调会 WinError 2，需经 cmd /c
        args: list[str] = ["npm", cmd, "-g"]
        if os.name == "nt":
            args = ["cmd", "/c", *args]
        try:
            return subprocess.run(
                args, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            ).stdout.strip()
        except OSError:
            return ""

    for base in (b for b in (_npm_out("prefix"), _npm_out("root")) if b):
        candidate = Path(base) / ("bd.cmd" if os.name == "nt" else "bd")
        if candidate.exists():
            return [str(candidate)]
    exe = shutil.which("bd")
    if exe:
        return [exe]
    return ["bd"]


def run_bd(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """执行真实 bd 命令，返回 CompletedProcess。"""
    proc = subprocess.run(
        bd_cmd() + args, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"bd {' '.join(args)} 失败 (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc


def load_issues() -> list[dict[str, Any]]:
    """读取全量议题（含 closed）。"""
    proc = run_bd(["list", "--all", "--format", "json"])
    data = json.loads(proc.stdout)
    if not isinstance(data, list):
        raise RuntimeError(f"bd list 输出格式异常: {type(data).__name__}")
    return data


def _has_conclusion(notes: str, comments: list[str]) -> bool:
    """判断任务是否已有结论性记录（备注或评论命中产出关键词且足够长）。

    用"完成/产出/沉淀/弯路/结果/记录"等产出词，避免把纯过程描述误判为结论；
    同时要求文本足够长（>= CONCLUSION_MIN_LEN），防止一两句流水账被当作结论。
    """
    text = (notes or "") + "\n" + "\n".join(comments or [])
    if len(text.strip()) < CONCLUSION_MIN_LEN:
        return False
    return any(kw in text for kw in CONCLUSION_KEYWORDS)


# ---------------------------------------------------------------- create ----

def cmd_create(args: argparse.Namespace) -> int:
    missing = []
    if not (args.description or "").strip():
        missing.append("--description")
    if not (args.acceptance or "").strip():
        missing.append("--acceptance")
    if not (args.notes or "").strip():
        missing.append("--notes")
    if missing:
        print(f"[bdg] 拒绝创建：缺少必填字段 {', '.join(missing)}", file=sys.stderr)
        print("[bdg] 强制要求：创建任务必须带 --description（做什么）、--acceptance（验收标准）、"
              "--notes（含阶段/弯路记录）", file=sys.stderr)
        return 2
    cmd = ["create", args.title]
    if args.description:
        cmd += ["--description", args.description]
    if args.acceptance:
        cmd += ["--acceptance", args.acceptance]
    if args.notes:
        cmd += ["--notes", args.notes]
    if args.parent:
        cmd += ["--parent", args.parent]
    if args.labels:
        cmd += ["--labels", args.labels]
    if args.priority is not None:
        cmd += ["--priority", str(args.priority)]
    run_bd(cmd)
    print("[bdg] 已创建（带强制工作记录字段）")
    return 0


# ----------------------------------------------------------------- close ----

def cmd_close(args: argparse.Namespace) -> int:
    if not (args.reason or "").strip():
        print("[bdg] 拒绝关闭：缺少 --reason（关闭原因/完成结论）", file=sys.stderr)
        print("[bdg] 关闭必须写清：做了什么、产出什么、有无弯路，例如 --reason \"完成…产出…\"", file=sys.stderr)
        return 2

    if args.require_notes:
        try:
            issues = load_issues()
        except RuntimeError as exc:
            print(f"[bdg] 无法读取议题以校验备注：{exc}", file=sys.stderr)
            return 1
        target = next((i for i in issues if i["id"] == args.id), None)
        if target is None:
            print(f"[bdg] 找不到议题 {args.id}", file=sys.stderr)
            return 1
        notes = target.get("notes") or ""
        comments = target.get("comments") or []
        if not _has_conclusion(notes, comments):
            print(f"[bdg] 拒绝关闭：{args.id} 缺少结论性记录（备注/评论中没有「弯路/完成/产出/结论/结果」等）",
                  file=sys.stderr)
            print("[bdg] 请先用 bdg note <id> \"阶段结论/弯路记录\" 补写，再关闭。", file=sys.stderr)
            return 2

    run_bd(["close", args.id, "--reason", args.reason])
    print(f"[bdg] 已关闭 {args.id}")
    return 0


# ------------------------------------------------------------------ note ----

def cmd_update(args: argparse.Namespace) -> int:
    if not (args.acceptance or "").strip() or not (args.notes or "").strip():
        print("[bdg] 验收修订必须同时提供非空 --acceptance 和 --notes。", file=sys.stderr)
        return 2
    run_bd(["update", args.id, "--acceptance", args.acceptance, "--append-notes", args.notes])
    print(f"[bdg] 已修订 {args.id} 验收标准并追加记录。")
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    if not (args.text or "").strip():
        print("[bdg] 拒绝：note 内容为空", file=sys.stderr)
        return 2
    run_bd(["note", args.id, args.text])
    print(f"[bdg] 已追加备注到 {args.id}")
    return 0


# --------------------------------------------------------------- comment ----

def cmd_comment(args: argparse.Namespace) -> int:
    if not (args.text or "").strip():
        print("[bdg] 拒绝：comment 内容为空", file=sys.stderr)
        return 2
    run_bd(["comment", args.id, args.text])
    print(f"[bdg] 已追加评论到 {args.id}")
    return 0


# ----------------------------------------------------------------- claim ----

def cmd_claim(args: argparse.Namespace) -> int:
    """认领任务：等价 `bd update <id> --claim`，属于写操作，统一走 bdg。"""
    run_bd(["update", args.id, "--claim"])
    print(f"[bdg] 已认领 {args.id}（status → in_progress）")
    return 0


# ------------------------------------------------------------ guard-check ----

def cmd_guard_check(args: argparse.Namespace) -> int:
    issues = load_issues()
    report: list[dict[str, Any]] = []
    for i in issues:
        labels = i.get("labels") or []
        if LEGACY_TAG in labels:
            continue  # 历史遗留任务跳过
        problems = []
        if i.get("issue_type") in ("task", "feature", "bug") and not (i.get("acceptance_criteria") or "").strip():
            problems.append("缺验收标准")
        if i.get("status") == "closed":
            if not (i.get("close_reason") or "").strip():
                problems.append("closed 缺 close_reason")
            notes = i.get("notes") or ""
            comments = i.get("comments") or []
            if not _has_conclusion(notes, comments):
                problems.append("closed 无结论记录")
        if problems:
            report.append({
                "id": i["id"],
                "title": i.get("title") or "",
                "status": i.get("status"),
                "issues": problems,
            })
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if not report:
            print("[bdg] 全部任务合规（legacy 已跳过）。")
            return 0
        print(f"[bdg] 发现 {len(report)} 个不合规任务：")
        for r in report:
            print(f"  - {r['id']} | {r['title'][:30]} | {'; '.join(r['issues'])}")
    return 1 if report else 0


# ------------------------------------------------------------------ main ----

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bdg",
        description="Beads 强制工作记录门禁（包一层真实 bd）。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="带守卫创建任务")
    p_create.add_argument("title")
    p_create.add_argument("--description", default="")
    p_create.add_argument("--acceptance", default="")
    p_create.add_argument("--notes", default="")
    p_create.add_argument("--parent", default="")
    p_create.add_argument("--labels", default="")
    p_create.add_argument("--priority", type=int, default=None)
    p_create.set_defaults(func=cmd_create)

    p_update = sub.add_parser("update", help="修订验收标准并追加记录，不修改状态")
    p_update.add_argument("id")
    p_update.add_argument("--acceptance", default="")
    p_update.add_argument("--notes", default="")
    p_update.set_defaults(func=cmd_update)

    p_close = sub.add_parser("close", help="带守卫关闭任务")
    p_close.add_argument("id")
    p_close.add_argument("--reason", default="")
    p_close.add_argument("--require-notes", action="store_true",
                         help="关闭前强制要求任务已有结论性备注/评论")
    p_close.set_defaults(func=cmd_close)

    p_note = sub.add_parser("note", help="追加阶段记录/弯路记录（备注）")
    p_note.add_argument("id")
    p_note.add_argument("text")
    p_note.set_defaults(func=cmd_note)

    p_claim = sub.add_parser("claim", help="认领任务（等价 bd update --claim）")
    p_claim.add_argument("id")
    p_claim.set_defaults(func=cmd_claim)

    p_comment = sub.add_parser("comment", help="追加评论（交流讨论）")
    p_comment.add_argument("id")
    p_comment.add_argument("text")
    p_comment.set_defaults(func=cmd_comment)

    p_check = sub.add_parser("guard-check", help="扫描不合规任务")
    p_check.add_argument("--format", choices=["text", "json"], default="text")
    p_check.set_defaults(func=cmd_guard_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
