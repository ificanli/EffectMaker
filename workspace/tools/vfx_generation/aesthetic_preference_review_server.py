"""Serve and finalize a Chinese-only human A/B aesthetic preference review."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from jsonschema import Draft202012Validator


CHOICES = {"a", "b", "tie", "not_comparable"}
REASONS = {"core_readability", "layer_separation", "rhythm", "material", "composition", "style_match", "overall_quality", "other"}
STORE_SCHEMA = "vfx_aesthetic_preference_feedback_store.v1"


class PreferenceReviewError(ValueError):
    """Raised when a preference review write is invalid."""


def _repo_root() -> Path:
    return Path(__file__).parents[3].resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PreferenceReviewError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def _portable(path: Path) -> str:
    root = _repo_root()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _load_batch(batch_root: Path) -> dict[str, Any]:
    batch = _read_json(batch_root.resolve() / "preference_review_batch.json")
    if batch.get("schema_version") != "vfx_aesthetic_preference_review_batch.v1":
        raise PreferenceReviewError("unsupported preference review batch")
    schema_path = Path(__file__).parents[3] / "workspace/data/vfx_generation/schemas/aesthetic_preference_review_batch.schema.json"
    errors = list(Draft202012Validator(_read_json(schema_path)).iter_errors(batch))
    if errors:
        raise PreferenceReviewError(f"preference review batch schema error: {errors[0].message}")
    return batch


def _store_path(batch_root: Path) -> Path:
    return batch_root.resolve() / "feedback_store.json"


def _load_store(batch_root: Path, batch: dict[str, Any]) -> dict[str, Any]:
    path = _store_path(batch_root)
    if not path.is_file():
        return {"schema_version": STORE_SCHEMA, "batch_id": batch["batch_id"], "records": {}}
    store = _read_json(path)
    if store.get("schema_version") != STORE_SCHEMA or store.get("batch_id") != batch["batch_id"]:
        raise PreferenceReviewError("preference feedback store does not match batch")
    if not isinstance(store.get("records"), dict):
        raise PreferenceReviewError("preference feedback store records must be an object")
    return store


def save_preference(batch_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    batch_root = batch_root.resolve()
    batch = _load_batch(batch_root)
    pair_id = str(payload.get("pair_id") or "")
    pairs = {str(row["pair_id"]): row for row in batch["pairs"]}
    if pair_id not in pairs:
        raise PreferenceReviewError(f"pair is not in review batch: {pair_id}")
    preference = str(payload.get("preference") or "")
    if preference not in CHOICES:
        raise PreferenceReviewError(f"invalid preference choice: {preference}")
    reason_codes = payload.get("reason_codes") if isinstance(payload.get("reason_codes"), list) else []
    reason_codes = sorted(set(str(value) for value in reason_codes))
    if any(value not in REASONS for value in reason_codes):
        raise PreferenceReviewError("invalid preference reason code")
    human_note = str(payload.get("human_note") or "").strip()
    if len(human_note) > 2000:
        raise PreferenceReviewError("human note is too long")
    record = {
        "schema_version": "vfx_aesthetic_preference_feedback.v1",
        "batch_id": batch["batch_id"],
        "pair_id": pair_id,
        "candidate_a": pairs[pair_id]["candidate_a"],
        "candidate_b": pairs[pair_id]["candidate_b"],
        "preference": preference,
        "reason_codes": reason_codes,
        "human_note": human_note,
        "reviewer": "local_human",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "status": "human_finalized",
    }
    store = _load_store(batch_root, batch)
    store["records"][pair_id] = record
    _write_json(_store_path(batch_root), store)
    _write_jsonl(batch_root / "feedback.jsonl", [store["records"][key] for key in sorted(store["records"])])
    return record


def _candidate_map(batch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["candidate_id"]): row for row in batch["candidates"]}


def _final_record(batch_root: Path, batch: dict[str, Any], pair: dict[str, Any], feedback: dict[str, Any], candidates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidate_a = candidates[pair["candidate_a"]]
    candidate_b = candidates[pair["candidate_b"]]
    frames = [*candidate_a["frames"], *candidate_b["frames"]]
    frame_paths = [str(frame["path"]) for frame in frames]
    record_id = "preference_" + hashlib.sha256(f"{batch['batch_id']}|{pair['pair_id']}".encode("utf-8")).hexdigest()[:20]
    preference = feedback["preference"]
    eligible = preference in {"a", "b"}
    return {
        "schema_version": "vfx_aesthetic_record.v1",
        "record_id": record_id,
        "record_kind": "preference_pair",
        "provenance": {
            "source_kind": "human_preference",
            "source_path": _portable(batch_root / "preference_review_batch.json"),
            "source_record_id": pair["pair_id"],
            "source_sha256": None,
            "asset_content_sha256": None,
            "source_group_id": batch["batch_id"],
            "material_group_id": None,
            "shader_group_id": None,
            "run_id": batch["batch_id"],
            "run_manifest_path": None,
            "spec_path": None,
            "prefab_path": candidate_a["prefab_path"],
            "render_candidate_id": None,
            "timecodes": [],
            "frame_paths": frame_paths,
            "parent_record_ids": [],
        },
        "scope": {
            "effect_family": batch["effect_family"],
            "style_family": str(batch["prompt"].get("style_family") or "unknown"),
            "style_keywords": [],
            "prompt_id": str(batch["prompt"].get("prompt_id") or "") or None,
            "candidate_ids": [pair["candidate_a"], pair["candidate_b"]],
            "scene_context": list(batch["prompt"].get("source_categories") or []),
        },
        "evidence": {
            "visibility_status": "visible",
            "evidence_status": "observed",
            "technical_status": "pass",
            "independent_visual_evidence": True,
            "continuous_frame_evidence": True,
            "visual_review_channel": "local_browser",
            "evidence_notes": "两侧候选均来自技术通过的连续帧。",
        },
        "payload": {
            "candidate_a": pair["candidate_a"],
            "candidate_b": pair["candidate_b"],
            "preference": preference,
            "comparable": preference in {"a", "b", "tie"},
            "reason_codes": list(feedback["reason_codes"]),
            "human_note": feedback["human_note"],
        },
        "training_eligibility": {
            "aesthetic_judge": False,
            "preference_training": eligible,
            "controller_sft": False,
            "positive_generation_supervision": False,
            "excluded_reasons": [] if eligible else ["tie_or_not_comparable_is_not_preference_training"],
        },
    }


def finalize_preferences(batch_root: Path) -> dict[str, Path]:
    batch_root = batch_root.resolve()
    batch = _load_batch(batch_root)
    store = _load_store(batch_root, batch)
    expected = {str(row["pair_id"]) for row in batch["pairs"]}
    saved = set(store["records"])
    missing = sorted(expected - saved)
    if missing:
        raise PreferenceReviewError(f"human preference review is incomplete: {len(saved)}/{len(expected)}; next missing pair: {missing[0]}")
    candidates = _candidate_map(batch)
    records = [_final_record(batch_root, batch, pair, store["records"][pair["pair_id"]], candidates) for pair in batch["pairs"]]
    schema_path = Path(__file__).parents[3] / "workspace/data/vfx_generation/schemas/aesthetic_record.schema.json"
    validator = Draft202012Validator(_read_json(schema_path))
    for record in records:
        errors = list(validator.iter_errors(record))
        if errors:
            raise PreferenceReviewError(f"final preference record schema error: {errors[0].message}")
    exclusions = [record for record in records if not record["training_eligibility"]["preference_training"]]
    trainable = [record for record in records if record["training_eligibility"]["preference_training"]]
    records_path = _write_jsonl(batch_root / "preference_records.jsonl", records)
    exclusion_path = _write_jsonl(batch_root / "preference_exclusions.jsonl", exclusions)
    summary_path = _write_json(batch_root / "preference_feedback_summary.json", {
        "schema_version": "vfx_aesthetic_preference_feedback_summary.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch["batch_id"],
        "pair_count": len(records),
        "trainable_preference_count": len(trainable),
        "excluded_tie_or_not_comparable_count": len(exclusions),
        "preference_counts": dict(sorted(__import__("collections").Counter(record["payload"]["preference"] for record in records).items())),
        "status": "human_finalized",
        "policy": {"not_comparable_is_not_training": True, "technical_pass_is_not_aesthetic_acceptance": True},
    })
    return {"records": records_path, "exclusions": exclusion_path, "summary": summary_path}


HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VFX A/B审美评价</title>
<style>
:root{color-scheme:dark;font-family:Arial,"Microsoft YaHei",sans-serif;background:#12161b;color:#e7edf2}
*{box-sizing:border-box}body{margin:0;background:#12161b}.top{position:sticky;top:0;z-index:2;padding:16px 20px;background:#1a2129;border-bottom:1px solid #34414d;display:flex;gap:18px;align-items:center;justify-content:space-between}.top h1{font-size:19px;margin:0}.muted{color:#94a5b4;font-size:13px}.layout{display:grid;grid-template-columns:280px 1fr;min-height:calc(100vh - 64px)}aside{border-right:1px solid #34414d;padding:12px;overflow:auto}.pair{width:100%;display:block;text-align:left;background:#1b232c;color:#dce5eb;border:1px solid #34414d;border-radius:4px;padding:10px;margin-bottom:7px;cursor:pointer}.pair.active{border-color:#5ec7e8;background:#203541}.pair.done{border-left:4px solid #65d39b}.main{padding:20px;max-width:1500px;width:100%;margin:auto}.candidate-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.candidate{background:#181f26;border:1px solid #34414d;border-radius:6px;padding:12px}.candidate h2{font-size:15px;margin:0 0 8px;color:#8bdcf0}.candidate .meta{font-size:12px;color:#98a8b5;margin-bottom:10px;word-break:break-all}.frames{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.frames button{border:1px solid #34414d;background:#101419;padding:0;cursor:pointer}.frames img{display:block;width:100%;aspect-ratio:1/1;object-fit:contain;background:#0b0e11}.frames span{display:block;font-size:11px;padding:4px;color:#aab8c2}.controls{margin-top:18px;background:#181f26;border-top:1px solid #34414d;padding:16px}.choices{display:flex;flex-wrap:wrap;gap:8px}.choices button{padding:10px 16px;border:1px solid #526474;background:#202b35;color:#e7edf2;border-radius:4px;cursor:pointer}.choices button.selected{border-color:#65d39b;background:#214c40}.reasons{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}.reasons label{font-size:13px}.note{width:100%;min-height:70px;background:#101419;border:1px solid #526474;color:#e7edf2;padding:9px;resize:vertical}.actions{display:flex;gap:8px;margin-top:12px}.actions button{padding:9px 14px;border:0;border-radius:4px;cursor:pointer}.save{background:#65d39b;color:#102018}.next{background:#526474;color:#fff}.error{color:#ff9b9b;margin-top:8px}.progress{white-space:nowrap}@media(max-width:900px){.layout{grid-template-columns:1fr}aside{max-height:220px;border-right:0;border-bottom:1px solid #34414d}.candidate-grid{grid-template-columns:1fr}.frames{grid-template-columns:repeat(4,minmax(0,1fr))}}
</style></head>
<body><header class="top"><div><h1>VFX A/B审美评价</h1><div id="prompt" class="muted"></div></div><div id="progress" class="progress"></div></header>
<div class="layout"><aside id="pairs"></aside><main class="main"><div id="stage"></div><div class="controls"><div class="muted">选择比较结论</div><div id="choices" class="choices"></div><div id="reasons" class="reasons"></div><textarea id="note" class="note" maxlength="2000" placeholder="人工备注"></textarea><div class="actions"><button id="save" class="save">保存本条</button><button id="next" class="next">下一条</button></div><div id="error" class="error"></div></div></main></div>
<script>
let batch,feedback={},index=0,choice=null;const $=id=>document.getElementById(id),reasonList=[['core_readability','主体可读性'],['layer_separation','层级分离'],['rhythm','节奏'],['material','材质'],['composition','构图'],['style_match','风格匹配'],['overall_quality','整体质量']];
const asset=p=>'/asset/'+p.split('/').map(encodeURIComponent).join('/');
function current(){return batch.pairs[index]};function renderList(){$('pairs').innerHTML=batch.pairs.map((p,i)=>`<button class="pair ${i===index?'active':''} ${feedback[p.pair_id]?'done':''}" data-i="${i}">${i+1}. ${p.pair_id.slice(0,12)}<br><span class="muted">${feedback[p.pair_id]?'已保存':'待评价'}</span></button>`).join('');document.querySelectorAll('.pair').forEach(x=>x.onclick=()=>{index=Number(x.dataset.i);choice=feedback[current().pair_id]?.preference||null;render()})}
function candidate(id){return batch.candidates.find(x=>x.candidate_id===id)}function renderStage(){let p=current(),a=candidate(p.candidate_a),b=candidate(p.candidate_b);$('stage').innerHTML=`<div class="candidate-grid">${card('A',a)}${card('B',b)}</div>`}
function card(label,c){return `<section class="candidate"><h2>候选${label}</h2><div class="meta">${c.source_candidate_id}<br>${c.run_id}</div><div class="frames">${c.frames.map(f=>`<button title="${Number(f.time_seconds).toFixed(3)}s"><img src="${asset(f.path)}"><span>${Number(f.time_seconds).toFixed(2)}s</span></button>`).join('')}</div></section>`}
function renderForm(){let p=current(),saved=feedback[p.pair_id]||{};choice=saved.preference||choice;$('choices').innerHTML=[['a','A更好'],['b','B更好'],['tie','差不多'],['not_comparable','无法比较']].map(([v,t])=>`<button class="${choice===v?'selected':''}" data-choice="${v}">${t}</button>`).join('');document.querySelectorAll('[data-choice]').forEach(x=>x.onclick=()=>{choice=x.dataset.choice;renderForm()});let reasons=new Set(saved.reason_codes||[]);$('reasons').innerHTML=reasonList.map(([v,t])=>`<label><input type="checkbox" value="${v}" ${reasons.has(v)?'checked':''}>${t}</label>`).join('');$('note').value=saved.human_note||'';$('progress').textContent=`${Object.keys(feedback).length}/${batch.pairs.length} 已评价`}
function render(){renderList();renderStage();renderForm();$('prompt').textContent=batch.prompt.text}function next(){index=Math.min(batch.pairs.length-1,index+1);choice=feedback[current().pair_id]?.preference||null;render()}
async function save(){if(!choice){$('error').textContent='请选择结论';return}let reasons=[...document.querySelectorAll('#reasons input:checked')].map(x=>x.value);let res=await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pair_id:current().pair_id,preference:choice,reason_codes:reasons,human_note:$('note').value})});let body=await res.json();if(!res.ok){$('error').textContent=body.error||'保存失败';return}$('error').textContent='';feedback[current().pair_id]=body.record;render();}async function init(){let b=await fetch('/api/batch').then(x=>x.json()),f=await fetch('/api/feedback').then(x=>x.json());batch=b;feedback=f.records||{};let first=batch.pairs.findIndex(x=>!feedback[x.pair_id]);index=first>=0?first:0;render()}$('save').onclick=save;$('next').onclick=next;init();
</script></body></html>'''


class _Handler(BaseHTTPRequestHandler):
    batch_root: Path

    def _send(self, status: int, body: bytes, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            batch = _load_batch(self.batch_root)
            if parsed.path == "/":
                self._send(HTTPStatus.OK, HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif parsed.path == "/api/batch":
                self._send(HTTPStatus.OK, json.dumps(batch, ensure_ascii=False).encode("utf-8"))
            elif parsed.path == "/api/feedback":
                self._send(HTTPStatus.OK, json.dumps(_load_store(self.batch_root, batch), ensure_ascii=False).encode("utf-8"))
            elif parsed.path.startswith("/asset/"):
                relative = unquote(parsed.path[len("/asset/"):]).replace("/", "\\")
                path = (_repo_root() / relative).resolve()
                if not path.is_file() or _repo_root() not in path.parents:
                    raise PreferenceReviewError("asset path is outside repository")
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self._send(HTTPStatus.OK, path.read_bytes(), content_type)
            else:
                self._send(HTTPStatus.NOT_FOUND, b"{}")
        except (PreferenceReviewError, FileNotFoundError, OSError, json.JSONDecodeError) as error:
            self._send(HTTPStatus.BAD_REQUEST, json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8"))

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if urlparse(self.path).path == "/api/feedback":
                result = save_preference(self.batch_root, payload)
                self._send(HTTPStatus.OK, json.dumps({"record": result}, ensure_ascii=False).encode("utf-8"))
            elif urlparse(self.path).path == "/api/finalize":
                paths = finalize_preferences(self.batch_root)
                self._send(HTTPStatus.OK, json.dumps({key: path.name for key, path in paths.items()}, ensure_ascii=False).encode("utf-8"))
            else:
                self._send(HTTPStatus.NOT_FOUND, b"{}")
        except (PreferenceReviewError, FileNotFoundError, OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            self._send(HTTPStatus.BAD_REQUEST, json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve(batch_root: Path, host: str, port: int) -> None:
    _load_batch(batch_root)
    handler = type("PreferenceHandler", (_Handler,), {"batch_root": batch_root.resolve()})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"http://{host}:{port}/")
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve a Chinese-only VFX A/B preference review.")
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8795)
    args = parser.parse_args(argv)
    try:
        serve(args.batch_root, args.host, args.port)
    except (PreferenceReviewError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
