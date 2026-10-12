"""Beads 本地网页看板后端。

纯标准库实现（http.server + json），不引入第三方依赖。
数据源：每次请求调用 `bd list --all --format json` 拉取全量议题。

启动：
    python -m workspace.tools.board_server [--port 8611] [--no-browser]

页面：
    http://127.0.0.1:8611/          看板页面
    http://127.0.0.1:8611/api/board 看板数据 JSON
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DEFAULT_PORT = 8611
REFRESH_MS = 10_000  # 页面轮询间隔（毫秒）

_STATUS_LABELS = {
    "open": "待办",
    "in_progress": "进行中",
    "blocked": "阻塞",
    "deferred": "延后",
    "closed": "已完成",
}
_STATUS_ORDER = ["open", "in_progress", "blocked", "deferred", "closed"]
_PRIORITY_LABELS = {0: "P0", 1: "P1", 2: "P2", 3: "P3", 4: "P4"}

# 合规检查：与 bd_guard 的 guard-check 保持一致（缺验收 / closed 缺 reason / closed 无结论）
_COMPLIANCE_KEYWORDS = ("完成", "产出", "沉淀", "弯路", "结果", "记录")
_COMPLIANCE_MIN_LEN = 8
LEGACY_TAG = "legacy"


def compliance_problems(issue: dict[str, Any]) -> list[str]:
    """返回议题的合规问题列表；legacy 标签的任务视为豁免。"""
    if LEGACY_TAG in (issue.get("labels") or []):
        return []
    problems = []
    if issue.get("issue_type") in ("task", "feature", "bug") and not (issue.get("acceptance_criteria") or "").strip():
        problems.append("缺验收标准")
    if issue.get("status") == "closed":
        if not (issue.get("close_reason") or "").strip():
            problems.append("closed 缺 close_reason")
        text = (issue.get("notes") or "") + "\n" + "\n".join(issue.get("comments") or [])
        if len(text.strip()) < _COMPLIANCE_MIN_LEN or not any(kw in text for kw in _COMPLIANCE_KEYWORDS):
            problems.append("closed 无结论记录")
    return problems

_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Beads 任务看板</title>
<style>
  :root {
    --bg: #161616; --card: #252525; --border: #3a3a3a;
    --text: #eee; --muted: #9a9a9a; --accent: #6c9bd1;
    --open: #5a8a5a; --in_progress: #d1a24c; --blocked: #c0564a;
    --deferred: #7a7a9a; --closed: #4a7a4a;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
         font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif; }
  header { display: flex; align-items: center; gap: 16px; padding: 12px 20px;
           border-bottom: 1px solid var(--border); position: sticky; top: 0;
           background: var(--bg); z-index: 10; flex-wrap: wrap; }
  header h1 { font-size: 18px; margin: 0; }
  .tabs { display: flex; gap: 6px; }
  .tab { background: none; border: 1px solid var(--border); color: var(--muted);
         padding: 6px 14px; cursor: pointer; border-radius: 4px; font-size: 13px; }
  .tab.active { background: var(--accent); color: #111; border-color: var(--accent); }
  .status-msg { margin-left: auto; font-size: 12px; color: var(--muted); }
  main { padding: 16px 20px; }
  .hidden { display: none !important; }

  /* ---- 看板列 ---- */
  .board { display: grid; grid-template-columns: repeat(5, minmax(200px, 1fr));
           gap: 12px; align-items: start; }
  .col { background: #1d1d1d; border: 1px solid var(--border); border-radius: 6px;
         padding: 8px; min-height: 200px; }
  .col h2 { font-size: 13px; margin: 4px 8px 10px; display: flex; justify-content: space-between; }
  .col h2 .count { color: var(--muted); font-weight: normal; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 4px;
          padding: 8px 10px; margin-bottom: 8px; cursor: pointer; }
  .card:hover { border-color: var(--accent); }
  .card .id { font-size: 11px; color: var(--muted); }
  .card .title { font-size: 13px; margin: 3px 0; word-break: break-word; }
  .card .parent { font-size: 11px; color: var(--muted); }
  .card .meta { display: flex; gap: 8px; font-size: 11px; color: var(--muted); }
  .badge { display: inline-block; padding: 1px 6px; border-radius: 3px;
           font-size: 11px; color: #111; }
  .badge.p0 { background: #e8a0a0; } .badge.p1 { background: #e8c08a; }
  .badge.p2 { background: #a8c8e8; } .badge.p3 { background: #b0b0b0; }
  .badge.p4 { background: #909090; }
  .label-chip { display: inline-block; padding: 1px 6px; margin: 1px 2px 1px 0;
                border-radius: 3px; font-size: 11px; background: #333; color: #ccc; }
  .redflag { display: inline-block; margin-left: 6px; color: #f0a0a0;
             font-size: 11px; font-weight: normal; }

  /* ---- 列表 ---- */
  .filters { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;
             align-items: center; }
  .filters input, .filters select { background: #1d1d1d; color: var(--text);
       border: 1px solid var(--border); border-radius: 4px; padding: 6px 8px; font-size: 13px; }
  .filters label { font-size: 12px; color: var(--muted); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: normal; font-size: 12px; }
  tr:hover td { background: #222; cursor: pointer; }
  td.id { font-size: 12px; color: var(--muted); white-space: nowrap; }
  .status-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%;
                margin-right: 6px; vertical-align: middle; }

  /* ---- 聚合 ---- */
  .group { margin-bottom: 20px; }
  .group h2 { font-size: 14px; margin: 0 0 8px; color: var(--accent); }
  .epic-card { background: var(--card); border: 1px solid var(--border);
               border-radius: 6px; padding: 12px 14px; margin-bottom: 10px; }
  .epic-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
  .epic-title { font-size: 14px; font-weight: bold; }
  .epic-sub { font-size: 12px; color: var(--muted); margin: 4px 0 8px; }
  .progress-bar { height: 8px; background: #333; border-radius: 4px; overflow: hidden; margin: 6px 0; }
  .progress-fill { height: 100%; background: var(--accent); border-radius: 4px; }
  .epic-meta { font-size: 12px; color: var(--muted); display: flex; gap: 16px; flex-wrap: wrap; }

  /* ---- 弹窗 ---- */
  .overlay { position: fixed; inset: 0; background: rgba(0,0,0,.6);
             display: flex; align-items: flex-start; justify-content: center;
             padding: 40px 20px; z-index: 100; overflow-y: auto; }
  .modal { background: #1d1d1d; border: 1px solid var(--border); border-radius: 8px;
           max-width: 640px; width: 100%; padding: 20px 24px; }
  .modal h3 { margin: 0 0 4px; font-size: 17px; }
  .modal .m-id { font-size: 12px; color: var(--muted); margin-bottom: 10px; }
  .modal .close { float: right; background: none; border: none; color: var(--muted);
                  font-size: 20px; cursor: pointer; }
  .modal .row { display: flex; gap: 8px; margin-bottom: 8px; font-size: 13px; }
  .modal .row .k { color: var(--muted); min-width: 64px; flex-shrink: 0; }
  .modal .section { margin-top: 14px; }
  .modal .section .k { font-size: 12px; color: var(--muted); margin-bottom: 4px; }
  .modal .section .v { font-size: 13px; white-space: pre-wrap; background: #222;
                       border-radius: 4px; padding: 8px 10px; }
  .modal .v.empty { color: var(--muted); }
</style>
</head>
<body>
<header>
  <h1>Beads 任务看板</h1>
  <nav class="tabs">
    <button class="tab active" data-view="board">看板</button>
    <button class="tab" data-view="list">列表</button>
    <button class="tab" data-view="epics">系列进度</button>
  </nav>
  <span class="status-msg" id="status">加载中…</span>
</header>
<main>
  <section id="view-board" class="view"></section>
  <section id="view-list" class="view hidden"></section>
  <section id="view-epics" class="view hidden"></section>
</main>
<div id="modal-root"></div>
<script>
const REFRESH_MS = %REFRESH_MS%;
const STATUS_LABELS = %STATUS_LABELS%;
const STATUS_ORDER = %STATUS_ORDER%;
const PRIORITY_LABELS = %PRIORITY_LABELS%;
let STATE = { issues: [], epics: [], generated_at: null };

// ---------- helpers ----------
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtTime = (iso) => iso ? new Date(iso).toLocaleString("zh-CN", { hour12: false }) : "—";
const statusColor = (s) => ({ open: "var(--open)", in_progress: "var(--in_progress)",
  blocked: "var(--blocked)", deferred: "var(--deferred)", closed: "var(--closed)" }[s] || "var(--muted)");
const prioBadge = (p) => {
  const label = PRIORITY_LABELS[p] ?? ("P" + p);
  return `<span class="badge p${p ?? 4}">${label}</span>`;
};
const labelsHtml = (labels) => (labels || []).map((l) =>
  `<span class="label-chip">${esc(l)}</span>`).join("");
const redFlag = (i) => (i.problems && i.problems.length
  ? `<span class="redflag" title="${esc(i.problems.join("; "))}">⚠ ${esc(i.problems.join("; "))}</span>` : "");

// ---------- data ----------
async function refresh() {
  const msg = $("#status");
  try {
    const r = await fetch("/api/board");
    if (!r.ok) throw new Error("HTTP " + r.status);
    STATE = await r.json();
    render();
    msg.textContent = "更新于 " + fmtTime(STATE.generated_at);
  } catch (e) {
    msg.textContent = "刷新失败: " + e.message;
  }
}

// ---------- board view ----------
function renderBoard() {
  const cols = STATUS_ORDER.map((s) => ({ s, items: STATE.issues.filter((i) => i.status === s) }));
  $("#view-board").innerHTML = `<div class="board">` + cols.map((c) => `
    <div class="col">
      <h2><span class="status-dot" style="background:${statusColor(c.s)}"></span>${STATUS_LABELS[c.s]}
        <span class="count">${c.items.length}</span></h2>
      ${c.items.map(cardHtml).join("")}
    </div>`).join("") + `</div>`;
}
function cardHtml(i) {
  return `<div class="card" data-id="${esc(i.id)}" onclick="openModal('${esc(i.id)}')">
    <div class="id">${esc(i.id)} ${prioBadge(i.priority)} ${redFlag(i)}</div>
    <div class="title">${esc(i.title || "(无标题)")}</div>
    ${i.parent_title ? `<div class="parent">${esc(i.parent_title)}</div>` : ""}
    <div class="meta">${labelsHtml(i.labels)}</div>
  </div>`;
}

// ---------- list view ----------
function renderList() {
  const q = ($("#f-q") || { value: "" }).value.toLowerCase();
  const s = ($("#f-status") || { value: "all" }).value;
  const p = ($("#f-prio") || { value: "all" }).value;
  const l = ($("#f-label") || { value: "all" }).value;
  let items = STATE.issues.filter((i) => {
    if (s !== "all" && i.status !== s) return false;
    if (p !== "all" && i.priority !== Number(p)) return false;
    if (l !== "all" && !(i.labels || []).includes(l)) return false;
    if (q) {
      const hay = (i.title + " " + i.id + " " + i.parent_title + " " + (i.labels || []).join(" ")).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  const rows = items.map((i) => `<tr data-id="${esc(i.id)}" onclick="openModal('${esc(i.id)}')">
    <td class="id">${esc(i.id)} ${redFlag(i)}</td>
    <td>${esc(i.title || "(无标题)")}</td>
    <td><span class="status-dot" style="background:${statusColor(i.status)}"></span>${STATUS_LABELS[i.status]}</td>
    <td>${prioBadge(i.priority)}</td>
    <td>${labelsHtml(i.labels)}</td>
    <td>${esc(i.parent_title || "—")}</td>
    <td class="id">${fmtTime(i.updated_at)}</td>
  </tr>`).join("");
  const labelOpts = [...new Set(STATE.issues.flatMap((i) => i.labels || []))].sort()
    .map((x) => `<option ${x === l ? "selected" : ""}>${esc(x)}</option>`).join("");
  $("#view-list").innerHTML = `
    <div class="filters">
      <input id="f-q" placeholder="搜索标题/ID/标签…" value="${esc(q)}" oninput="renderList()">
      <label>状态 <select id="f-status" onchange="renderList()">
        <option value="all">全部</option>
        ${Object.entries(STATUS_LABELS).map(([k, v]) =>
          `<option value="${k}" ${k === s ? "selected" : ""}>${v}</option>`).join("")}
      </select></label>
      <label>优先级 <select id="f-prio" onchange="renderList()">
        <option value="all">全部</option>
        ${Object.entries(PRIORITY_LABELS).map(([k, v]) =>
          `<option value="${k}" ${String(k) === p ? "selected" : ""}>${v}</option>`).join("")}
      </select></label>
      <label>标签 <select id="f-label" onchange="renderList()">
        <option value="all">全部</option>${labelOpts}
      </select></label>
      <span style="color:var(--muted);font-size:12px">共 ${items.length} 条</span>
    </div>
    <table><thead><tr>
      <th>ID</th><th>标题</th><th>状态</th><th>优先级</th><th>标签</th><th>所属系列</th><th>更新时间</th>
    </tr></thead><tbody>${rows}</tbody></table>`;
}

// ---------- epics view ----------
function renderEpics() {
  const groups = {};
  for (const e of STATE.epics) {
    const key = e.series || "其他";
    (groups[key] = groups[key] || []).push(e);
  }
  const order = Object.keys(groups).sort((a, b) => (a === "其他" ? 1 : b === "其他" ? -1 : a.localeCompare(b)));
  $("#view-epics").innerHTML = order.map((g) => `
    <div class="group"><h2>${esc(g)}</h2>
      ${groups[g].map(epicHtml).join("")}
    </div>`).join("");
}
function epicHtml(e) {
  const pct = e.total ? Math.round((e.done / e.total) * 100) : 0;
  const inprog = e.children.filter((c) => c.status === "in_progress");
  return `<div class="epic-card" data-id="${esc(e.id)}">
    <div class="epic-head">
      <span class="epic-title">${esc(e.title || e.id)}</span> ${prioBadge(e.priority)}
    </div>
    <div class="epic-sub">${esc(e.id)}${e.series ? " · " + esc(e.series) : ""}</div>
    <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
    <div class="epic-meta">
      <span>已完成 ${e.done}/${e.total}（${pct}%）</span>
      ${inprog.length ? `<span>进行中: ${inprog.map((c) => esc(c.title || c.id)).join("、")}</span>` : ""}
      ${e.children.length ? `<a href="javascript:void(0)" onclick="openModal('${esc(e.id)}')">查看详情</a>` : ""}
    </div>
  </div>`;
}

// ---------- modal ----------
function openModal(id) {
  const i = STATE.issues.find((x) => x.id === id) || STATE.epics.find((x) => x.id === id);
  if (!i) return;
  const rows = (k, v) => `<div class="row"><span class="k">${k}</span><span>${v}</span></div>`;
  const sec = (k, v) => `<div class="section"><div class="k">${k}</div>
    <div class="v ${v ? "" : "empty"}">${v ? esc(v) : "（无）"}</div></div>`;
  $("#modal-root").innerHTML = `<div class="overlay" onclick="if(event.target===this)closeModal()">
    <div class="modal">
      <button class="close" onclick="closeModal()">&times;</button>
      <h3>${esc(i.title || "(无标题)")}</h3>
      <div class="m-id">${esc(i.id)}</div>
      ${i.problems && i.problems.length ? `<div class="redflag" style="margin:0 0 8px;display:block">⚠ ${esc(i.problems.join("；"))}</div>` : ""}
      ${rows("状态", `<span class="status-dot" style="background:${statusColor(i.status)}"></span>${STATUS_LABELS[i.status] || i.status}`)}
      ${rows("优先级", prioBadge(i.priority))}
      ${rows("类型", esc(i.issue_type || "—"))}
      ${rows("标签", labelsHtml(i.labels) || "—")}
      ${i.parent_title ? rows("所属系列", esc(i.parent_title)) : ""}
      ${rows("创建时间", fmtTime(i.created_at))}
      ${rows("开始时间", fmtTime(i.started_at))}
      ${i.closed_at ? rows("完成时间", fmtTime(i.closed_at)) : ""}
      ${i.close_reason ? rows("关闭原因", esc(i.close_reason)) : ""}
      ${i.dependency_count != null ? rows("依赖数", i.dependency_count) : ""}
      ${i.comment_count != null ? rows("评论数", i.comment_count) : ""}
      ${sec("描述", i.description)}
      ${sec("验收标准", i.acceptance_criteria)}
      ${sec("备注", i.notes)}
    </div></div>`;
}
function closeModal() { $("#modal-root").innerHTML = ""; }

// ---------- tabs & polling ----------
document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
  b.classList.add("active");
  document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
  $("#view-" + b.dataset.view).classList.remove("hidden");
  render();
}));

function render() {
  renderBoard();
  renderList();
  renderEpics();
}

refresh();
if (location.search.includes("noauth=1")) {
  $("#status").textContent += "（轮询已暂停: noauth）";
} else {
  setInterval(refresh, REFRESH_MS);
}
</script>
</body>
</html>
"""


def _bd_cmd() -> list[str]:
    """返回真实 bd 可执行文件路径（绕过 PATH 中的守卫 wrapper）。

    bd 是 npm 全局安装的 CLI：Windows 上是 bd.cmd shim（在 npm 全局 bin 目录，
    即 `npm prefix -g`），POSIX 上可能是 bin 目录下的 bd 或 node_modules/.bin。
    依次探测 npm prefix -g、npm root -g 下的候选，最后回退 shutil.which，
    避免 PATH 里 workspace/bin 的守卫 wrapper 干扰工具链自身（看板/守卫必须
    调用真实 bd，否则会递归）。
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

    bases = [b for b in (_npm_out("prefix"), _npm_out("root")) if b]
    for base in bases:
        candidate = Path(base) / ("bd.cmd" if os.name == "nt" else "bd")
        if candidate.exists():
            return [str(candidate)]
    exe = shutil.which("bd")
    if exe:
        return [exe]
    return ["bd"]


def run_bd_list() -> list[dict[str, Any]]:
    """调用 `bd list --all --format json`，返回议题列表。"""
    proc = subprocess.run(
        _bd_cmd() + ["list", "--all", "--format", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"bd list 失败 (exit {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"bd list 输出不是合法 JSON: {exc}") from exc
    if not isinstance(data, list):
        raise RuntimeError(f"bd list 输出格式异常: {type(data).__name__}")
    return data


def _natural_key(issue_id: str) -> tuple:
    """按 ID 数字后缀自然排序：vfx-mp7.11 排在 vfx-mp7.2 之后。"""
    parts = re.split(r"(\d+)", issue_id or "")
    return tuple(int(part) if part.isdigit() else part.lower() for part in parts)


def normalize(data: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """清洗议题字段并计算 epic 聚合。

    返回 (issues, epics)：
    - issues：全部议题（含 closed），字段已补默认值，并附 parent_title。
    - epics：type=epic 的聚合信息（children、done/total、进度百分比、series 标签）。
    """
    by_id: dict[str, dict[str, Any]] = {}
    for raw in data:
        issue = {
            "id": raw.get("id") or "",
            "title": raw.get("title") or "",
            "description": raw.get("description") or "",
            "status": raw.get("status") or "open",
            "priority": raw.get("priority"),
            "issue_type": raw.get("issue_type") or "task",
            "created_at": raw.get("created_at") or "",
            "started_at": raw.get("started_at") or "",
            "closed_at": raw.get("closed_at") or "",
            "close_reason": raw.get("close_reason") or "",
            "updated_at": raw.get("updated_at") or "",
            "labels": raw.get("labels") or [],
            "assignee": raw.get("assignee") or "",
            "design": raw.get("design") or "",
            "acceptance_criteria": raw.get("acceptance_criteria") or "",
            "notes": raw.get("notes") or "",
            "parent": raw.get("parent") or "",
            "dependencies": raw.get("dependencies") or [],
            "dependency_count": raw.get("dependency_count") if raw.get("dependency_count") is not None else 0,
            "comment_count": raw.get("comment_count") if raw.get("comment_count") is not None else 0,
            "comments": raw.get("comments") or [],
            "parent_title": "",
            "problems": [],
        }
        by_id[issue["id"]] = issue

    # 填充父标题（父级不在列表中时回退为父 ID）
    for issue in by_id.values():
        parent = issue["parent"]
        if parent:
            issue["parent_title"] = by_id.get(parent, {}).get("title") or parent
        issue["problems"] = compliance_problems(issue)

    issues = list(by_id.values())
    issues.sort(key=lambda i: _natural_key(i["id"]))

    epics = []
    for issue in issues:
        if issue["issue_type"] != "epic":
            continue
        children = [c for c in issues if c["parent"] == issue["id"]]
        children.sort(key=lambda c: _natural_key(c["id"]))
        done = sum(1 for c in children if c["status"] == "closed")
        series = next((lbl for lbl in issue["labels"] if lbl.startswith("SRC-")), "")
        epics.append({
            **issue,
            "children": children,
            "done": done,
            "total": len(children),
            "series": series,
        })

    return issues, epics


def build_payload() -> dict[str, Any]:
    """构造看板 API 响应。"""
    issues, epics = normalize(run_bd_list())
    return {
        "issues": issues,
        "epics": epics,
        "generated_at": None,  # 由 HTTP 层填充
    }


class BoardHandler(BaseHTTPRequestHandler):
    server_version = "BeadsBoard/1.0"

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        try:
            if self.path == "/" or self.path == "/index.html":
                html = _HTML.replace("%REFRESH_MS%", str(REFRESH_MS))
                html = html.replace("%STATUS_LABELS%", json.dumps(_STATUS_LABELS, ensure_ascii=False))
                html = html.replace("%STATUS_ORDER%", json.dumps(_STATUS_ORDER))
                html = html.replace("%PRIORITY_LABELS%", json.dumps(_PRIORITY_LABELS))
                self._send(200, html.encode("utf-8"), "text/html")
            elif self.path == "/api/board":
                issues, epics = normalize(run_bd_list())
                payload = {
                    "issues": issues,
                    "epics": epics,
                    "generated_at": None,
                }
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json")
            elif self.path == "/favicon.ico":
                self._send(204, b"", "image/x-icon")
            else:
                self._send(404, b"Not Found", "text/plain")
        except Exception as exc:  # noqa: BLE001 - 统一返回错误 JSON，避免连接中断
            body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
            self._send(500, body, "application/json")

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[board] %s - %s\n" % (self.address_string(), fmt % args))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Beads 本地网页看板")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口（默认 %(default)s）")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), BoardHandler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Beads 看板已启动: {url}")
    print(f"数据源: bd list --all --format json  |  刷新间隔: {REFRESH_MS // 1000}s")
    print("按 Ctrl+C 停止。")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
