"""Local HTML review server for teaching-reference annotations."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_ROOT = Path("knowledge/sources/SRC-2026-UP389578709/teaching_comparisons/BV198v6BoE9h_final_case/reference")


def load_annotations(root: Path) -> dict:
    timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
    path = root / "annotations.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema": "teaching-annotation.v1",
        "source_id": timeline.get("source_id"),
        "case_id": timeline.get("case_id"),
        "frames": [
            {
                "id": frame["id"],
                "source_time_seconds": frame["source_time_seconds"],
                "image": frame["image"],
                "status": "unreviewed",
                "phase": frame.get("phase", "unreviewed"),
                "observations": frame.get("observations", {}),
            }
            for frame in timeline.get("frames", [])
        ],
    }


def save_annotations(root: Path, payload: dict) -> Path:
    path = root / "annotations.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>教学复现参考标注</title>
<style>
:root{--bg:#101418;--panel:#192027;--line:#34404a;--text:#e9eef2;--muted:#91a0aa;--accent:#4db6ac;--warn:#e0a458}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px "Segoe UI","Microsoft YaHei",sans-serif}header{height:52px;display:flex;align-items:center;padding:0 16px;border-bottom:1px solid var(--line);gap:16px}h1{font-size:16px;margin:0}.status{margin-left:auto;color:var(--muted)}main{height:calc(100vh - 52px);display:grid;grid-template-columns:280px minmax(420px,1fr) 360px;gap:12px;padding:12px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:5px;min-height:0}.frames{overflow:auto;padding:8px}.thumb{display:grid;grid-template-columns:96px 1fr;gap:8px;padding:6px;border:1px solid transparent;cursor:pointer;margin-bottom:6px}.thumb.active{border-color:var(--accent);background:#21343a}.thumb img{width:96px;height:54px;object-fit:cover}.thumb small{color:var(--muted);display:block;margin-top:5px}.stage{display:flex;flex-direction:column;min-width:0}.hero{flex:1;display:flex;align-items:center;justify-content:center;padding:14px;background:#0a0d10}.hero img{max-width:100%;max-height:100%;object-fit:contain}.transport{padding:10px;border-top:1px solid var(--line);display:flex;gap:8px;align-items:center}.transport button,.actions button{background:#26323a;color:var(--text);border:1px solid var(--line);border-radius:4px;padding:7px 12px;cursor:pointer}.transport button:hover,.actions button:hover{border-color:var(--accent)}.details{padding:14px;overflow:auto}.details label{display:block;color:var(--muted);font-size:12px;margin:12px 0 5px}.details input,.details textarea,.details select{width:100%;background:#10161b;color:var(--text);border:1px solid var(--line);border-radius:4px;padding:8px;font:inherit}.details textarea{min-height:58px;resize:vertical}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.actions .confirm{border-color:var(--accent);color:#b6eee8}.actions .reject{border-color:#bc6c63;color:#f2b0a8}.badge{display:inline-block;padding:3px 7px;border-radius:10px;background:#35414a;color:var(--muted);font-size:11px}.hint{color:var(--muted);line-height:1.5;font-size:12px}
</style></head><body><header><h1>教学复现参考标注</h1><span id="case" class="badge"></span><span id="status" class="status"></span></header><main><section class="panel frames" id="frames"></section><section class="panel stage"><div class="hero"><img id="hero" alt="参考帧"></div><div class="transport"><button onclick="move(-1)" title="上一帧">上一帧</button><button onclick="move(1)" title="下一帧">下一帧</button><span id="counter"></span></div></section><section class="panel details"><div id="form"></div></section></main>
<script>
let data=null,index=0,dirty=false;const phases=['preparation','swing','peak','impact','recovery','residual','unreviewed'];
const $=id=>document.getElementById(id);function current(){return data.frames[index]}
function render(){let f=current();$('case').textContent=data.case_id||'';$('hero').src=f.image;$('counter').textContent=`${index+1}/${data.frames.length} · ${f.source_time_seconds.toFixed(2)}s`;$('status').textContent=dirty?'未保存':'已保存';$('frames').innerHTML=data.frames.map((x,i)=>`<div class="thumb ${i===index?'active':''}" onclick="selectFrame(${i})"><img src="${x.image}"><div><b>${x.id}</b><small>${x.source_time_seconds.toFixed(2)}s · ${x.status}</small></div></div>`).join('');let o=f.observations||{};$('form').innerHTML=`<div class="hint">AI 初标由系统预填；人工确认后才可作为教学复现依据。</div><label>审核状态</label><select id="f-status"><option value="ai_draft">AI 初标</option><option value="human_confirmed">人工确认</option><option value="human_rejected">人工否决</option></select><label>动作阶段</label><select id="f-phase">${phases.map(p=>`<option>${p}</option>`).join('')}</select><label>主体轮廓</label><textarea id="silhouette">${o.silhouette||''}</textarea><label>挥砍方向</label><textarea id="direction">${o.direction||''}</textarea><label>刀尖/外缘</label><textarea id="leading_edge">${o.leading_edge||''}</textarea><label>亮度中心</label><textarea id="brightness_center">${o.brightness_center||''}</textarea><label>拖尾/支撑层</label><textarea id="support_layers">${o.support_layers||''}</textarea><label>命中/收束</label><textarea id="impact_feedback">${o.impact_feedback||''}</textarea><div class="actions"><button class="confirm" onclick="setStatus('human_confirmed')">确认当前帧</button><button class="reject" onclick="setStatus('human_rejected')">否决当前帧</button><button onclick="save()">保存标注</button></div>`;$('f-status').value=f.status;$('f-phase').value=phases.includes(f.phase)?f.phase:'unreviewed'}
function readForm(){let f=current();f.status=$('f-status').value;f.phase=$('f-phase').value;f.observations={silhouette:$('silhouette').value,direction:$('direction').value,leading_edge:$('leading_edge').value,brightness_center:$('brightness_center').value,support_layers:$('support_layers').value,impact_feedback:$('impact_feedback').value};dirty=true}
function selectFrame(i){readForm();index=i;render()}function move(d){readForm();index=Math.max(0,Math.min(data.frames.length-1,index+d));render()}function setStatus(s){readForm();current().status=s;render()}async function save(){readForm();let r=await fetch('/api/annotations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(!r.ok)alert('保存失败');else{dirty=false;render()}}
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft')move(-1);if(e.key==='ArrowRight')move(1);if(e.key==='s'&&(e.ctrlKey||e.metaKey)){e.preventDefault();save()}});fetch('/api/annotations').then(r=>r.json()).then(x=>{data=x;render()});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    root = DEFAULT_ROOT

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/annotations":
            self._send_json(load_annotations(self.root))
        elif path == "/":
            self._send(200, "text/html; charset=utf-8", _HTML.encode("utf-8"))
        else:
            file = (self.root / path.lstrip("/"))
            if file.is_file() and file.resolve().is_relative_to(self.root.resolve()):
                self._send(200, "image/jpeg" if file.suffix.lower() in (".jpg", ".jpeg") else "application/octet-stream", file.read_bytes())
            else:
                self._send(404, "text/plain; charset=utf-8", b"Not found")

    def do_POST(self):
        if urlparse(self.path).path != "/api/annotations":
            self._send(404, "text/plain; charset=utf-8", b"Not found"); return
        length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length))
        save_annotations(self.root, payload); self._send_json({"ok": True})

    def _send(self, code, content_type, body):
        self.send_response(code); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def _send_json(self, payload): self._send(200, "application/json; charset=utf-8", json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    def log_message(self, *_): pass


def serve(root: Path = DEFAULT_ROOT, port: int = 8622) -> None:
    Handler.root = root.resolve()
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=DEFAULT_ROOT); parser.add_argument("--port", type=int, default=8622); args = parser.parse_args(); serve(args.root, args.port)
