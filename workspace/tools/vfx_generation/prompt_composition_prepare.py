from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def build_requests(
    retrieval_manifest: Path,
    output_root: Path,
    *,
    unity_project: Path = Path("UnityDemo/EffectDemo"),
    execution_project: Path | None = None,
) -> Path:
    retrieval_manifest = retrieval_manifest.resolve(); output_root = output_root.resolve()
    unity_project = unity_project.resolve()
    execution_project = (execution_project or unity_project).resolve()
    if output_root.exists() and any(output_root.iterdir()): raise FileExistsError(output_root)
    source = json.loads(retrieval_manifest.read_text(encoding="utf-8")); requests=[]; curriculum_roots=set()
    for candidate in source["candidates"]:
        spec_path = Path(candidate["material_trajectory"]["spec_path"]).resolve()
        curriculum_roots.add(spec_path.parent.parent.as_posix())
        spec = json.loads(spec_path.read_text(encoding="utf-8")); root=output_root/"candidates"/candidate["candidate_id"]
        requests.append({"trajectory_id":spec["trajectory_id"],"candidate_id":candidate["candidate_id"],"prefab_path":candidate["source_prefab"]["prefab_path"],"spec_path":spec_path.as_posix(),"capture_dir":(root/"frames").as_posix(),"material_timeline_path":(root/"material_timeline.json").as_posix(),"result_path":(root/"execution_result.json").as_posix(),"track_clamps":[{"has_min":t.get("clamp_min") is not None,"min":float(t.get("clamp_min") or 0),"has_max":t.get("clamp_max") is not None,"max":float(t.get("clamp_max") or 0)} for t in spec.get("parameter_tracks",[])],"has_negative_mutation":spec.get("negative_mutation") is not None})
    if len(curriculum_roots) != 1:
        raise ValueError("prompt composition candidates must use one material trajectory curriculum")
    output_root.mkdir(parents=True,exist_ok=True); path=output_root/"execution_requests.json"
    path.write_text(json.dumps({"schema_version":"effectdemo_material_trajectory_requests.v1","created_at":datetime.now(timezone.utc).isoformat(),"run_id":output_root.name,"execution_mode":"selected","curriculum_root":next(iter(curriculum_roots)),"unity_project":unity_project.as_posix(),"execution_project":execution_project.as_posix(),"width":512,"height":512,"target_intervals":10,"run_resource_audit_path":(output_root/"run_resource_audit.json").as_posix(),"selection":{"kind":"prompt_composition","count":len(requests),"candidate_ids":[item["candidate_id"] for item in requests],"trajectory_ids":[item["trajectory_id"] for item in requests]},"requests":requests},ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); return path

def main() -> int:
    p=argparse.ArgumentParser();p.add_argument("--retrieval-manifest",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True);p.add_argument("--unity-project",type=Path,default=Path("UnityDemo/EffectDemo"));p.add_argument("--execution-project",type=Path);a=p.parse_args()
    try:path=build_requests(a.retrieval_manifest,a.output_root,unity_project=a.unity_project,execution_project=a.execution_project)
    except (OSError,ValueError,FileExistsError,json.JSONDecodeError) as e:print(json.dumps({"success":False,"error":str(e)},ensure_ascii=False));return 2
    print(json.dumps({"success":True,"request_path":path.as_posix()},ensure_ascii=False,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
