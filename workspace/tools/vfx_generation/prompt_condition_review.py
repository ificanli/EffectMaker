"""Review whether rendered Prompt compositions satisfy each requested condition."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import cv2
import numpy as np


CHOICES = ("符合", "部分符合", "不符合", "无法判断")
CONDITION_FIELDS = ("风格", "主色", "特效类别", "节奏", "无长拖尾", "整体")


def _repo_root() -> Path:
    return Path(__file__).parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    root = _repo_root().resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_image(path: Path) -> np.ndarray | None:
    try:
        return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    except OSError:
        return None


def _blue_fraction(path: Path) -> float | None:
    image = _read_image(path)
    if image is None:
        return None
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    corners = np.concatenate((
        image[:8, :8].reshape(-1, 3), image[:8, -8:].reshape(-1, 3),
        image[-8:, :8].reshape(-1, 3), image[-8:, -8:].reshape(-1, 3),
    ))
    background = np.median(corners, axis=0).astype(np.uint8)
    difference = cv2.cvtColor(cv2.absdiff(image, background), cv2.COLOR_BGR2GRAY)
    visible = (difference > 8) & (hsv[:, :, 1] >= 45)
    if not visible.any():
        return 0.0
    blue = (hsv[:, :, 0] >= 90) & (hsv[:, :, 0] <= 132)
    return round(float(blue[visible].mean()), 8)


def _color_draft(prompt: dict[str, Any], frame: Path) -> tuple[str, dict[str, Any]]:
    colors = set(prompt.get("color_keywords") or [])
    if not colors:
        return "无法判断", {"reason": "prompt_has_no_supported_color_keyword"}
    if colors != {"blue"}:
        return "无法判断", {"reason": "color_draft_only_supports_blue"}
    blue_fraction = _blue_fraction(frame)
    if blue_fraction is None:
        return "无法判断", {"reason": "frame_unreadable"}
    decision = "符合" if blue_fraction >= 0.55 else "部分符合" if blue_fraction >= 0.2 else "不符合"
    return decision, {"blue_visible_fraction": blue_fraction}


def _highest_blue_frame(paths: list[Path]) -> Path:
    if not paths:
        raise ValueError("cannot select a color draft frame from an empty sequence")
    scored = []
    for path in paths:
        blue_fraction = _blue_fraction(path)
        scored.append((blue_fraction if blue_fraction is not None else -1.0, path))
    return max(scored, key=lambda item: item[0])[1]


def _draft_for_record(prompt: dict[str, Any], record: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    frame = Path(record["frames"][min(1, len(record["frames"]) - 1)]["path"])
    color, color_evidence = _color_draft(prompt, frame)
    source_label = source.get("human_label_context") or {}
    source_style = str(source_label.get("style_family") or "unknown")
    style = "部分符合" if source_style == prompt.get("style_family") else "无法判断"
    expected_families = set(prompt.get("effect_families") or [])
    family_hint = str(record["effect_family_hint"])
    effect_family = "部分符合" if expected_families and family_hint in expected_families else "无法判断"
    duration = float(record["duration_seconds"])
    rhythm = "符合" if prompt.get("timing_profile") == "fast_impact" and duration <= 2.0 else "无法判断"
    no_long_trail = "符合" if "长拖尾" in set(prompt.get("negative_constraints") or []) and duration <= 2.0 else "无法判断"
    concrete = [style, color, effect_family, rhythm, no_long_trail]
    overall = "不符合" if "不符合" in concrete else "部分符合" if "部分符合" in concrete else "无法判断"
    return {
        "schema_version": "prompt_condition_ai_draft.v1",
        "batch_id": record["batch_id"],
        "candidate_id": record["candidate_id"],
        "status": "ai_draft_not_human_label",
        "suggested_conditions": {
            "风格": style, "主色": color, "特效类别": effect_family,
            "节奏": rhythm, "无长拖尾": no_long_trail, "整体": overall,
        },
        "evidence": {
            "source_style_label": source_style,
            "effect_family_hint": family_hint,
            "duration_seconds": duration,
            "color": color_evidence,
        },
    }


def build_review_batch(composition_root: Path, output_root: Path, batch_id: str) -> dict[str, Path]:
    composition_root, output_root = composition_root.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"review output already exists and is not empty: {output_root}")
    composition = _read_json(composition_root / "composition_manifest.json")
    retrieval_path = Path(str(composition["retrieval_manifest_path"]))
    if not retrieval_path.is_absolute():
        retrieval_path = _repo_root() / retrieval_path
    retrieval = _read_json(retrieval_path)
    source_by_id = {str(row["candidate_id"]): row for row in retrieval["candidates"]}
    records = []
    drafts = []
    for index, candidate in enumerate(composition["candidates"], start=1):
        candidate_id = str(candidate["candidate_id"])
        source = source_by_id[candidate_id]
        result = _read_json(composition_root / "candidates" / candidate_id / "execution_result.json")
        frame_paths = [composition_root / "candidates" / candidate_id / "frames" / str(frame["path"]) for frame in result["frames"]]
        if not frame_paths or any(not path.is_file() for path in frame_paths):
            raise FileNotFoundError(f"condition review frame is missing: {candidate_id}")
        record = {
            "review_index": index,
            "batch_id": batch_id,
            "candidate_id": candidate_id,
            "prefab_path": candidate["source_prefab"]["prefab_path"],
            "effect_family_hint": candidate["source_prefab"]["effect_family_hint"],
            "duration_seconds": float(result["duration_seconds"]),
            "frames": [
                {"time_seconds": float(frame["requested_time_seconds"]), "path": _portable(path)}
                for frame, path in zip(result["frames"], frame_paths)
            ],
            "source_prefab_label": source.get("human_label_context"),
            "quality_feedback_is_separate": True,
            "feedback_status": "pending",
        }
        records.append(record)
        drafts.append(_draft_for_record(composition["prompt_condition"], record, source))
    batch = {
        "schema_version": "prompt_condition_review_batch.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "source_composition_manifest": _portable(composition_root / "composition_manifest.json"),
        "prompt_condition": composition["prompt_condition"],
        "selected_count": len(records),
        "records": records,
    }
    return {
        "review_batch": _write_json(output_root / "review_batch.json", batch),
        "feedback_store": _write_json(output_root / "feedback_store.json", {"schema_version": "prompt_condition_feedback_store.v1", "batch_id": batch_id, "records": {}}),
        "ai_drafts": _write_jsonl(output_root / "ai_drafts.jsonl", drafts),
    }


def build_variation_review_batch(variation_root: Path, output_root: Path, batch_id: str) -> dict[str, Path]:
    variation_root, output_root = variation_root.resolve(), output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"review output already exists and is not empty: {output_root}")
    proposal = _read_json(variation_root / "proposal_manifest.json")
    execution = _read_json(variation_root / "variant_manifest.json")
    result = _read_json(Path(str(execution["execution_result_path"])))
    candidate_id = str(execution["proposal_id"])
    frame_paths = [variation_root / "candidates" / candidate_id / "frames" / str(frame["path"]) for frame in result["frames"]]
    if not frame_paths or any(not path.is_file() for path in frame_paths):
        raise FileNotFoundError("variation condition review is missing frames")
    record = {
        "review_index": 1,
        "batch_id": batch_id,
        "candidate_id": candidate_id,
        "prefab_path": proposal["source_prefab"]["prefab_path"],
        "effect_family_hint": "explosion",
        "duration_seconds": float(result["duration_seconds"]),
        "frames": [
            {"time_seconds": float(frame["requested_time_seconds"]), "path": _portable(path)}
            for frame, path in zip(result["frames"], frame_paths)
        ],
        "source_prefab_label": None,
        "quality_feedback_is_separate": True,
        "feedback_status": "pending",
        "review_subject": "prompt_variation",
        "review_subject_cn": "受约束变异结果（本次运行）",
        "variation_manifest": _portable(variation_root / "variant_manifest.json"),
    }
    source = {"human_label_context": None}
    draft = _draft_for_record(proposal["prompt_condition"], record, source)
    color, color_evidence = _color_draft(proposal["prompt_condition"], _highest_blue_frame(frame_paths))
    draft["suggested_conditions"]["主色"] = color
    concrete = [draft["suggested_conditions"][field] for field in CONDITION_FIELDS if field != "整体"]
    draft["suggested_conditions"]["整体"] = "不符合" if "不符合" in concrete else "部分符合" if "部分符合" in concrete else "无法判断"
    draft["evidence"]["color"] = color_evidence
    batch = {
        "schema_version": "prompt_condition_review_batch.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "source_variation_manifest": _portable(variation_root / "variant_manifest.json"),
        "prompt_condition": proposal["prompt_condition"],
        "selected_count": 1,
        "records": [record],
    }
    return {
        "review_batch": _write_json(output_root / "review_batch.json", batch),
        "feedback_store": _write_json(output_root / "feedback_store.json", {"schema_version": "prompt_condition_feedback_store.v1", "batch_id": batch_id, "records": {}}),
        "ai_drafts": _write_jsonl(output_root / "ai_drafts.jsonl", [draft]),
    }


def _load_drafts(root: Path) -> dict[str, dict[str, Any]]:
    return {str(row["candidate_id"]): row for row in _read_jsonl(root / "ai_drafts.jsonl")}


def save_feedback(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    batch = _read_json(root / "review_batch.json")
    sources = {str(row["candidate_id"]): row for row in batch["records"]}
    candidate_id = str(payload.get("candidate_id") or "")
    if candidate_id not in sources:
        raise ValueError(f"candidate is not in review batch: {candidate_id}")
    conditions = payload.get("conditions")
    if not isinstance(conditions, dict) or set(conditions) != set(CONDITION_FIELDS):
        raise ValueError("condition feedback must provide every requested condition")
    if any(value not in CHOICES for value in conditions.values()):
        raise ValueError("condition feedback contains an unsupported choice")
    draft = _load_drafts(root).get(candidate_id, {}).get("suggested_conditions")
    record = {
        "schema_version": "prompt_condition_human_feedback.v1",
        "batch_id": batch["batch_id"],
        "candidate_id": candidate_id,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewer": "local_human",
        "conditions": conditions,
        "confirmation_mode": "human_accepted_ai_draft" if conditions == draft else "human_corrected_ai_draft",
        "trace": {
            "prefab_path": sources[candidate_id]["prefab_path"],
            "render_paths": [frame["path"] for frame in sources[candidate_id]["frames"]],
        },
    }
    store = _read_json(root / "feedback_store.json")
    store["records"][candidate_id] = record
    _write_json(root / "feedback_store.json", store)
    return record


def finalize_feedback(root: Path) -> dict[str, Path]:
    root = root.resolve()
    batch = _read_json(root / "review_batch.json")
    store = _read_json(root / "feedback_store.json")
    records = store.get("records") if isinstance(store.get("records"), dict) else {}
    expected = [str(row["candidate_id"]) for row in batch["records"]]
    missing = [candidate_id for candidate_id in expected if candidate_id not in records]
    if missing:
        raise ValueError(f"Prompt condition review is incomplete: {len(records)}/{len(expected)} saved; next missing candidate: {missing[0]}")
    overlays = []
    exclusions = []
    for candidate_id in expected:
        feedback = records[candidate_id]
        known = {field: value for field, value in feedback["conditions"].items() if value != "无法判断"}
        if not known:
            exclusions.append({
                "schema_version": "prompt_condition_training_exclusion.v1",
                "batch_id": batch["batch_id"],
                "candidate_id": candidate_id,
                "reason": "all_prompt_conditions_not_judgable",
                "human_feedback": feedback,
                "excluded_from": ["prompt_condition_supervision", "positive_generation_supervision", "preference_training"],
            })
            continue
        overlays.append({
            "schema_version": "prompt_condition_human_label_overlay.v1",
            "batch_id": batch["batch_id"],
            "candidate_id": candidate_id,
            "reviewed_at": feedback["reviewed_at"],
            "prompt_condition": batch["prompt_condition"],
            "human_conditions": known,
            "unknown_conditions": sorted(field for field in CONDITION_FIELDS if field not in known),
            "trace": feedback["trace"],
            "training_eligibility": {
                "prompt_condition_supervision": True,
                "positive_generation_supervision": feedback["conditions"]["整体"] == "符合",
                "preference_training": False,
            },
        })
    summary = {
        "schema_version": "prompt_condition_review_summary.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch["batch_id"],
        "review_count": len(expected),
        "condition_supervision_count": len(overlays),
        "technical_exclusion_count": len(exclusions),
        "not_judgable_is_not_training_data": True,
        "condition_choice_counts": {
            field: {choice: sum(record["conditions"][field] == choice for record in records.values()) for choice in CHOICES}
            for field in CONDITION_FIELDS
        },
    }
    return {
        "prompt_condition_human_label_overlays": _write_jsonl(root / "prompt_condition_human_label_overlays.jsonl", overlays),
        "prompt_condition_technical_exclusions": _write_jsonl(root / "prompt_condition_technical_exclusions.jsonl", exclusions),
        "prompt_condition_feedback_summary": _write_json(root / "prompt_condition_feedback_summary.json", summary),
    }


_HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>组合候选 Prompt 一致性评价</title><style>
:root{--bg:#10151b;--panel:#171e26;--panel2:#1d2731;--line:#2b3946;--text:#e9eef4;--muted:#9aa8b6;--cyan:#49c7d6;--yellow:#f3c969;--green:#7cc58e}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 "Segoe UI","Microsoft YaHei",sans-serif}header{height:64px;display:flex;align-items:center;gap:16px;padding:0 16px;border-bottom:1px solid var(--line);background:#121920}h1{margin:0;font-size:16px}.prompt{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted)}.progress{margin-left:auto;color:var(--muted)}main{height:calc(100vh - 64px);display:grid;grid-template-columns:280px minmax(420px,1fr) 380px;gap:10px;padding:10px}.panel{min-height:0;border:1px solid var(--line);background:var(--panel)}.list,.details{overflow:auto}.item{width:100%;display:grid;grid-template-columns:32px minmax(0,1fr);gap:7px;padding:9px;border:1px solid transparent;background:transparent;color:var(--text);text-align:left;cursor:pointer}.item.active{border-color:var(--cyan);background:var(--panel2)}.item.done .idx{color:var(--green)}.idx{color:var(--yellow);font-family:Consolas}.item span{min-width:0;overflow-wrap:anywhere}.item small{display:block;color:var(--muted)}.stage{display:grid;grid-template-rows:minmax(0,1fr) 100px auto}.hero{display:grid;place-items:center;background:#080c10;overflow:hidden}.hero img{max-width:100%;max-height:100%;object-fit:contain}.frames{display:flex;gap:6px;overflow-x:auto;padding:7px;border-top:1px solid var(--line)}.frame{flex:0 0 86px;border:1px solid var(--line);padding:3px;background:#111820;color:var(--muted);cursor:pointer}.frame.active{border-color:var(--yellow)}.frame img{width:78px;height:62px;object-fit:contain;background:#070a0d}.transport{display:grid;grid-template-columns:auto auto auto minmax(100px,1fr) auto;gap:7px;align-items:center;padding:8px;border-top:1px solid var(--line)}button,input,select{font:inherit}.icon{width:34px;height:32px;border:1px solid var(--line);background:var(--panel2);color:var(--text);cursor:pointer}.details{padding:12px}.meta{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px}.meta div{padding:7px;background:var(--panel2);color:var(--muted);font-size:12px}.meta b{display:block;color:var(--text)}label{display:block;margin:10px 0 4px;color:var(--muted);font-size:12px}select{width:100%;padding:9px;border:1px solid var(--line);background:#10161c;color:var(--text)}.actions{display:flex;gap:8px;margin-top:14px;position:sticky;bottom:-12px;padding:10px 0 4px;background:var(--panel)}.save{flex:1;border:1px solid var(--green);background:#20372a;color:#d8f5df;padding:9px;cursor:pointer}.next{border:1px solid var(--cyan);background:var(--panel2);color:var(--text);padding:9px;cursor:pointer}.status{color:var(--muted);font-size:12px}@media(max-width:900px){header{height:auto;min-height:64px;align-items:flex-start;flex-wrap:wrap;padding:10px 14px}.prompt{width:100%;white-space:normal}main{height:auto;grid-template-columns:1fr}.list{max-height:245px}.stage{height:610px}.details{overflow:visible}.actions{bottom:0}}
</style></head><body><header><h1>组合候选 Prompt 一致性评价</h1><span id="prompt" class="prompt"></span><span id="progress" class="progress"></span></header><main><aside id="list" class="panel list"></aside><section class="panel stage"><div id="hero" class="hero"></div><div id="frames" class="frames"></div><div class="transport"><button id="prev" class="icon">←</button><button id="play" class="icon">▶</button><button id="nextFrame" class="icon">→</button><input id="timeline" type="range" min="0" max="0" value="0"><span id="time"></span></div></section><aside class="panel details"><div id="meta" class="meta"></div><div id="form"></div></aside></main><script>
let batch=null,feedback={},drafts={},index=0,frame=0,timer=null;const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),asset=p=>'/asset/'+p.split('/').map(encodeURIComponent).join('/'),current=()=>batch.records[index],choices=['符合','部分符合','不符合','无法判断'],fields=['风格','主色','特效类别','节奏','无长拖尾','整体'];function opts(field,value){return `<label>${field}</label><select id="c-${field}">${choices.map(x=>`<option ${x===value?'selected':''}>${x}</option>`).join('')}</select>`}function renderList(){$('list').innerHTML=batch.records.map((r,i)=>`<button class="item ${i===index?'active':''} ${feedback[r.candidate_id]?'done':''}" data-i="${i}"><span class="idx">${String(i+1).padStart(3,'0')}</span><span>${esc(r.candidate_id)}<small>${esc(r.prefab_path.split('/').pop())}</small></span></button>`).join('');document.querySelectorAll('.item').forEach(x=>x.onclick=()=>selectCandidate(Number(x.dataset.i)))}function renderStage(){let r=current(),f=r.frames[frame];$('hero').innerHTML=`<img src="${asset(f.path)}" alt="组合候选帧">`;$('frames').innerHTML=r.frames.map((x,i)=>`<button class="frame ${i===frame?'active':''}" data-i="${i}"><img src="${asset(x.path)}"><span>${Number(x.time_seconds).toFixed(2)}s</span></button>`).join('');document.querySelectorAll('.frame').forEach(x=>x.onclick=()=>{frame=Number(x.dataset.i);renderStage()});$('timeline').max=r.frames.length-1;$('timeline').value=frame;$('time').textContent=`${frame+1}/${r.frames.length}`}function renderForm(){let r=current(),draft=drafts[r.candidate_id]?.suggested_conditions||{},saved=feedback[r.candidate_id],conditions=saved?.conditions||draft;$('meta').innerHTML=`<div><b>评价对象</b>本次组合结果</div><div><b>来源 Prefab</b>${esc(r.prefab_path.split('/').pop())}</div><div><b>时长</b>${r.duration_seconds.toFixed(2)}s</div><div><b>来源标签</b>${esc(r.source_prefab_label?.style_family||'暂不判断')}，仅作草稿依据</div>`;$('form').innerHTML=`<div class="status">${saved?'已保存':draft?'AI 建议，未保存':'未评价'}</div>${fields.map(x=>opts(x,conditions[x]||'无法判断')).join('')}<div class="actions"><button id="save" class="save">保存本条</button><button id="nextCandidate" class="next">下一条</button></div>`;$('save').onclick=save;$('nextCandidate').onclick=()=>selectCandidate(nextUnreviewed())}function render(){renderList();renderStage();renderForm();$('prompt').textContent=batch.prompt_condition.text;$('progress').textContent=`${Object.keys(feedback).length}/${batch.records.length} 已评价`}function selectCandidate(i){if(i<0)i=Math.min(batch.records.length-1,index);if(timer){clearInterval(timer);timer=null}$('play').textContent='▶';index=i;frame=Math.min(1,batch.records[i].frames.length-1);render()}function nextUnreviewed(){for(let i=index+1;i<batch.records.length;i++)if(!feedback[batch.records[i].candidate_id])return i;return -1}function move(delta){let r=current();frame=Math.max(0,Math.min(r.frames.length-1,frame+delta));renderStage()}function toggle(){if(timer){clearInterval(timer);timer=null;$('play').textContent='▶';return}$('play').textContent='Ⅱ';timer=setInterval(()=>{let r=current();if(frame>=r.frames.length-1){clearInterval(timer);timer=null;$('play').textContent='▶';return}move(1)},350)}async function save(){let conditions=Object.fromEntries(fields.map(x=>[x,$(`c-${x}`).value])),response=await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({candidate_id:current().candidate_id,conditions})}),body=await response.json();if(!response.ok)return;feedback[current().candidate_id]=body.record;render()}$('prev').onclick=()=>move(-1);$('play').onclick=toggle;$('nextFrame').onclick=()=>move(1);$('timeline').oninput=e=>{frame=Number(e.target.value);renderStage()};Promise.all([fetch('/api/batch').then(r=>r.json()),fetch('/api/feedback').then(r=>r.json()),fetch('/api/drafts').then(r=>r.json())]).then(([b,f,d])=>{batch=b;feedback=f.records||{};drafts=d.records||{};let first=batch.records.findIndex(r=>!feedback[r.candidate_id]);if(first>=0)index=first;render()});
</script></body></html>'''


class ReviewHandler(BaseHTTPRequestHandler):
    root = Path(".")
    repo = _repo_root()

    def _send(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: dict[str, Any], code: int = 200) -> None:
        self._send(code, "application/json; charset=utf-8", json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, "text/html; charset=utf-8", _HTML.encode("utf-8"))
        elif path == "/api/batch":
            self._json(_read_json(self.root / "review_batch.json"))
        elif path == "/api/feedback":
            self._json(_read_json(self.root / "feedback_store.json"))
        elif path == "/api/drafts":
            self._json({"records": _load_drafts(self.root)})
        elif path.startswith("/asset/"):
            asset = (self.repo / Path(unquote(path[7:]))).resolve()
            if asset.is_file() and asset.is_relative_to(self.repo.resolve()):
                self._send(200, "image/png" if asset.suffix.lower() == ".png" else "image/jpeg", asset.read_bytes())
            else:
                self._json({"error": "asset not found"}, 404)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/feedback":
            self._json({"error": "not found"}, 404)
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            self._json({"ok": True, "record": save_feedback(self.root, payload)})
        except (ValueError, json.JSONDecodeError) as error:
            self._json({"error": str(error)}, 400)

    def log_message(self, *_: object) -> None:
        pass


def serve(root: Path, port: int) -> None:
    ReviewHandler.root = root.resolve()
    ThreadingHTTPServer(("127.0.0.1", port), ReviewHandler).serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--composition-root", type=Path, required=True)
    build.add_argument("--output-root", type=Path, required=True)
    build.add_argument("--batch-id", required=True)
    variation = commands.add_parser("build-variation")
    variation.add_argument("--variation-root", type=Path, required=True)
    variation.add_argument("--output-root", type=Path, required=True)
    variation.add_argument("--batch-id", required=True)
    server = commands.add_parser("serve")
    server.add_argument("--root", type=Path, required=True)
    server.add_argument("--port", type=int, default=8792)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "serve":
        serve(args.root, args.port)
        return 0
    try:
        if args.command == "build":
            paths = build_review_batch(args.composition_root, args.output_root, args.batch_id)
        elif args.command == "build-variation":
            paths = build_variation_review_batch(args.variation_root, args.output_root, args.batch_id)
        else:
            paths = finalize_feedback(args.root)
    except (FileExistsError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps({"success": True, **{key: path.as_posix() for key, path in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
