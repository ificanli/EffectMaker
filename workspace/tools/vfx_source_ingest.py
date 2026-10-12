"""Build source-ingestion records for Unity VFX assets.

The scanner is intentionally conservative: it records Unity files, .meta GUIDs,
GUID dependencies, and coarse component counts. Visual correctness still has to
come from render captures and human feedback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import uuid
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from workspace.tools.resource_index.metadata import read_image_metadata
from workspace.tools.resource_index.texture_tagger import tag_texture_record


GUID_RE = re.compile(r"\bguid:\s*([0-9a-fA-F]{32})\b")
META_GUID_RE = re.compile(r"^guid:\s*([0-9a-fA-F]{32})\s*$", re.MULTILINE)
INCLUDE_RE = re.compile(r'(?m)^\s*#include(?:_with_pragmas)?\s+["<]([^">]+)[">]')
CUSTOM_EDITOR_RE = re.compile(r'(?m)^\s*CustomEditor\s+"([A-Za-z_][A-Za-z0-9_.]*)"')
MATERIAL_TEXTURE_SLOT_RE = re.compile(r'(?m)^\s*m_Texture:\s*\{([^}\r\n]*)\}')
CS_NAMESPACE_RE = re.compile(r'(?m)^\s*namespace\s+([A-Za-z_][A-Za-z0-9_.]*)')
CS_CLASS_RE = re.compile(r'\bclass\s+([A-Za-z_][A-Za-z0-9_]*)')
UNITY_BUILTIN_GUID_RE = re.compile(r"^0{16}[0-9a-fA-F][0-9a-fA-F]{15}$")

KNOWN_CUSTOM_EDITOR_PACKAGES = {
    "TMPro.EditorUtilities.TMP_SDFShaderGUI": "com.unity.textmeshpro",
}
ALLOWED_SHADER_GUI_LICENSE_STATUSES = {
    "local_reference_only",
    "redistributable",
    "trainable_internal",
    "trainable_public",
}

IGNORED_DIRS = {
    ".git",
    ".svn",
    "Library",
    "Temp",
    "Logs",
    "UserSettings",
    "obj",
    "Build",
    "Builds",
    "MemoryCaptures",
}

TEXT_EXTENSIONS = {
    ".prefab",
    ".unity",
    ".mat",
    ".asset",
    ".anim",
    ".controller",
    ".overridecontroller",
    ".playable",
    ".shader",
    ".hlsl",
    ".cginc",
    ".shadergraph",
    ".shadersubgraph",
    ".vfx",
    ".json",
    ".txt",
    ".meta",
}

TEXTURE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tga", ".dds", ".exr", ".psd"}
MESH_EXTENSIONS = {".fbx", ".obj", ".blend"}
ANIMATION_EXTENSIONS = {".anim", ".controller", ".overridecontroller", ".playable"}
SHADER_EXTENSIONS = {".shader", ".hlsl", ".cginc", ".shadergraph", ".shadersubgraph"}
UNITY_DATA_EXTENSIONS = {".asset", ".spriteatlas", ".rendertexture", ".cubemap"}
SCRIPT_EXTENSIONS = {".cs", ".asmdef", ".dll"}
COPYABLE_DEPENDENCY_EXTENSIONS = (
    {".prefab", ".mat", ".vfx"}
    | TEXTURE_EXTENSIONS
    | MESH_EXTENSIONS
    | ANIMATION_EXTENSIONS
    | SHADER_EXTENSIONS
    | UNITY_DATA_EXTENSIONS
)
DEFAULT_TEXTURE_TAG_INDEX = Path("workspace/data/resource_index/texture_tags.jsonl")


@dataclass(frozen=True)
class IngestConfig:
    source_path: Path
    output_dir: Path
    source_id: str
    title: str
    effect_family: str
    source_kind: str = "unity_effect_package"
    source_unity_project: Path | None = None
    target_unity_project: Path | None = None
    copy_under: str = "Assets/VFXSourceIngest/Trains"
    copy_name: str | None = None
    copy_assets: bool = False
    overwrite: bool = False
    license_status: str = "local_reference_only"
    beads_id: str | None = None
    hash_files: bool = False
    resolve_project_guids: bool = False
    texture_tag_index_path: Path | None = None
    copy_dependency_closure: bool = False
    include_script_dependencies: bool = False
    max_dependency_depth: int = 32
    shared_dependency_store: str | None = None
    shared_index_path: Path | None = None
    dedupe_by: str = "none"
    rewrite_guid_references: bool = False
    dry_run: bool = False
    project_guid_cache: Path | None = None
    shader_gui_policy_path: Path | None = None
    copy_shader_gui_dependencies: bool = False


def infer_unity_project(path: Path) -> Path | None:
    """Return the closest parent that looks like a Unity project."""
    candidates = [path if path.is_dir() else path.parent, *path.parents]
    for candidate in candidates:
        if (candidate / "Assets").is_dir() and (candidate / "ProjectSettings").is_dir():
            return candidate.resolve()
    return None


def read_unity_version(project: Path | None) -> str | None:
    if project is None:
        return None
    version_file = project / "ProjectSettings" / "ProjectVersion.txt"
    if not version_file.exists():
        return None
    text = version_file.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"m_EditorVersion:\s*(.+)", text)
    return match.group(1).strip() if match else None


def read_urp_version(project: Path | None) -> str | None:
    if project is None:
        return None
    manifest = project / "Packages" / "manifest.json"
    if not manifest.exists():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    deps = data.get("dependencies", {})
    version = deps.get("com.unity.render-pipelines.universal")
    return str(version) if version is not None else None


def is_ignored(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part in IGNORED_DIRS for part in parts)


def iter_files(path: Path) -> list[Path]:
    path = path.resolve()
    if path.is_file():
        files = [path]
        meta = Path(str(path) + ".meta")
        if meta.exists():
            files.append(meta)
        return files
    files: list[Path] = []
    for child in path.rglob("*"):
        if child.is_file() and not is_ignored(child, path):
            files.append(child)
    return sorted(files, key=lambda p: p.as_posix().lower())


def infer_role(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix == ".meta":
        return "meta"
    if suffix == ".prefab":
        return "prefab"
    if suffix == ".unity":
        return "scene"
    if suffix == ".mat":
        return "material"
    if suffix == ".shader":
        return "shader"
    if suffix in {".hlsl", ".cginc"}:
        return "shader_include"
    if suffix == ".shadergraph":
        return "shadergraph"
    if suffix == ".shadersubgraph":
        return "shadersubgraph"
    if suffix == ".vfx":
        return "vfxgraph"
    if suffix in TEXTURE_EXTENSIONS:
        return "texture"
    if suffix in MESH_EXTENSIONS:
        return "mesh"
    if suffix in ANIMATION_EXTENSIONS:
        return "animation"
    if suffix in UNITY_DATA_EXTENSIONS:
        return "unity_asset"
    if suffix == ".cs":
        return "script"
    if "particle" in name or "fx" in name or "effect" in name:
        return "effect_asset"
    return "other"


def read_meta_guid(meta_path: Path) -> str | None:
    if not meta_path.exists():
        return None
    text = meta_path.read_text(encoding="utf-8", errors="ignore")
    match = META_GUID_RE.search(text)
    return match.group(1).lower() if match else None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def asset_path(path: Path, project: Path | None, fallback_root: Path | None = None) -> str:
    path = path.resolve()
    for root in [project, fallback_root]:
        if root is None:
            continue
        try:
            return path.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return path.as_posix()


def scan_guid_map(root: Path, project: Path | None) -> dict[str, Path]:
    guid_map: dict[str, Path] = {}
    for meta in iter_files(root):
        if meta.suffix.lower() != ".meta":
            continue
        guid = read_meta_guid(meta)
        if guid:
            guid_map[guid] = meta.with_suffix("")
    return guid_map


def guid_cache_fingerprint(root: Path) -> str:
    root = root.resolve()
    digest = hashlib.sha256()
    for meta in iter_files(root):
        if meta.suffix.lower() != ".meta":
            continue
        stat = meta.stat()
        digest.update(meta.relative_to(root).as_posix().encode("utf-8"))
        digest.update(f":{stat.st_size}:{stat.st_mtime_ns}\n".encode("ascii"))
    return digest.hexdigest()


def load_or_build_guid_map(root: Path, project: Path | None, cache_path: Path | None = None) -> tuple[dict[str, Path], dict]:
    """Load a cached GUID map when the source Assets metadata has not changed."""
    root = root.resolve()
    fingerprint = guid_cache_fingerprint(root)
    if cache_path is not None and cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if payload.get("root") == root.as_posix() and payload.get("fingerprint") == fingerprint:
                entries = payload.get("entries") or {}
                guid_map = {
                    guid: (root / relative).resolve()
                    for guid, relative in entries.items()
                    if (root / relative).exists()
                }
                if len(guid_map) == len(entries):
                    return guid_map, {"status": "cache_hit", "entries": len(guid_map), "cache_path": cache_path.as_posix()}
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    guid_map = scan_guid_map(root, project)
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        entries = {guid: path.relative_to(root).as_posix() for guid, path in guid_map.items()}
        cache_path.write_text(
            json.dumps(
                {
                    "schema_version": "unity_guid_map.v1",
                    "root": root.as_posix(),
                    "fingerprint": fingerprint,
                    "entries": entries,
                },
                ensure_ascii=False,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
    return guid_map, {"status": "rebuilt", "entries": len(guid_map), "cache_path": cache_path.as_posix() if cache_path else None}



def is_copyable_dependency(path: Path, include_scripts: bool = False) -> bool:
    suffix = path.suffix.lower()
    if suffix in SCRIPT_EXTENSIONS:
        return include_scripts
    return suffix in COPYABLE_DEPENDENCY_EXTENSIONS


def extract_guids(path: Path) -> set[str]:
    if path.suffix.lower() not in TEXT_EXTENSIONS or path.suffix.lower() == ".meta":
        return set()
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return set()
    return {guid.lower() for guid in GUID_RE.findall(text)}


def extract_local_includes(path: Path) -> set[str]:
    if path.suffix.lower() not in TEXT_EXTENSIONS or path.suffix.lower() == ".meta":
        return set()
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return set()
    includes: set[str] = set()
    for raw_include in INCLUDE_RE.findall(text):
        include = raw_include.strip().replace("\\", "/")
        if include:
            includes.add(include)
    return includes


def is_unity_builtin_guid(guid: str) -> bool:
    return bool(UNITY_BUILTIN_GUID_RE.match(guid)) and guid != "0" * 32


def resolve_local_include(include: str, current: Path, source_project: Path | None) -> Path | None:
    candidates = [current.parent / include]
    if source_project is not None:
        candidates.append(source_project / include)
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.exists():
            if source_project is None:
                return resolved
            try:
                resolved.relative_to(source_project.resolve())
            except ValueError:
                continue
            return resolved
    return None


def collect_dependency_closure(
    initial_files: Iterable[Path],
    project_guid_map: dict[str, Path],
    source_project: Path | None = None,
    include_scripts: bool = False,
    max_depth: int = 32,
) -> tuple[list[Path], set[str]]:
    """Return source assets reachable through GUID references.

    Script dependencies are deliberately skipped by default: importing game
    runtime scripts just to read an effect often turns a data task into a
    compile task. The dependency is still reported as ignored.
    """
    selected: set[Path] = {path.resolve() for path in initial_files if path.is_file()}
    ignored_guids: set[str] = set()
    queue = deque((path.resolve(), 0) for path in initial_files if path.is_file())
    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for include in extract_local_includes(current):
            target = resolve_local_include(include, current, source_project)
            if target is None:
                continue
            if not is_copyable_dependency(target, include_scripts):
                continue
            if target in selected:
                continue
            selected.add(target)
            queue.append((target, depth + 1))
        for guid in extract_guids(current):
            if is_unity_builtin_guid(guid):
                continue
            target = project_guid_map.get(guid)
            if target is None:
                continue
            target = target.resolve()
            if not is_copyable_dependency(target, include_scripts):
                ignored_guids.add(guid)
                continue
            if target in selected:
                continue
            selected.add(target)
            queue.append((target, depth + 1))
    return sorted(selected, key=lambda p: p.as_posix().lower()), ignored_guids


def source_asset_relative_path(path: Path, source_project: Path | None, selected_root: Path) -> Path:
    path = path.resolve()
    if source_project is not None:
        assets_root = (source_project / "Assets").resolve()
        try:
            return path.relative_to(assets_root)
        except ValueError:
            pass
    selected_root = selected_root.resolve()
    try:
        if selected_root.is_file():
            return Path(path.name)
        return path.relative_to(selected_root)
    except ValueError:
        return Path(path.name)


def copy_folder_meta_for_relative_path(
    source_project: Path | None,
    destination_root: Path,
    relative_asset_path: Path,
) -> None:
    """Create destination-local folder metas without cloning source folder GUIDs.

    Folder GUIDs are not referenced by Prefab or Material dependencies. Reusing
    them below several imported sample roots can create duplicate Unity GUIDs,
    so only file assets retain their source GUID identity.
    """
    accumulated = Path()
    for part in relative_asset_path.parent.parts:
        accumulated = accumulated / part
        destination_folder = destination_root / accumulated
        destination_folder.mkdir(parents=True, exist_ok=True)
        destination_meta = Path(str(destination_folder) + ".meta")
        if destination_meta.exists():
            continue
        write_generated_folder_meta(destination_meta)


def copy_asset_with_meta(
    source_file: Path,
    destination_file: Path,
    destination_root: Path,
    source_project: Path | None,
    relative_asset_path: Path,
    preserve_guid: bool = True,
) -> None:
    copy_folder_meta_for_relative_path(source_project, destination_root, relative_asset_path)
    destination_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, destination_file)
    source_meta = Path(str(source_file) + ".meta")
    destination_meta = Path(str(destination_file) + ".meta")
    if source_meta.exists() and preserve_guid:
        shutil.copy2(source_meta, destination_meta)
    elif source_meta.exists():
        # Keep the source importer (TextureImporter, ModelImporter, etc.) and
        # replace only the GUID. A generic DefaultImporter makes image files
        # resolve by GUID but unusable as Material textures.
        source_meta_text = source_meta.read_text(encoding="utf-8", errors="ignore")
        if META_GUID_RE.search(source_meta_text):
            rebased_meta = META_GUID_RE.sub(f"guid: {uuid.uuid4().hex}", source_meta_text, count=1)
            destination_meta.write_text(rebased_meta, encoding="utf-8")
        else:
            write_generated_asset_meta(destination_meta)
    elif not destination_meta.exists():
        write_generated_asset_meta(destination_meta)


def remove_existing_destination(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination_meta = Path(str(destination) + ".meta")
    if destination_meta.exists():
        destination_meta.unlink()


def is_shared_dependency(path: Path) -> bool:
    """Return whether a dependency belongs in a cross-sample shared pool.

    Shader source stays in a source-relative package so its `#include` graph
    retains the same directory topology. Textures, meshes, animations, and
    Unity data assets use content-addressed deduplication.
    """
    return infer_role(path) in {"shader", "shader_include", "shadergraph", "shadersubgraph", "texture", "mesh", "animation", "unity_asset"}


def is_shader_package_dependency(path: Path) -> bool:
    return infer_role(path) in {"shader", "shader_include", "shadergraph", "shadersubgraph"}


def is_rewritable_unity_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS and path.suffix.lower() != ".meta"


def load_shared_dependency_index(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": "shared_dependency_index.v1", "assets": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid shared dependency index: {path}") from exc
    if not isinstance(payload.get("assets"), dict):
        raise ValueError(f"shared dependency index lacks assets map: {path}")
    return payload


def save_shared_dependency_index(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def default_shared_dependency_index_path(target_project: Path) -> Path:
    """Keep mutable dedupe bookkeeping outside Assets so Unity never imports it."""
    return target_project / "Library" / "VFXSourceIngest" / "shared_dependency_index.json"


def project_relative_or_absolute(path: Path, target_project: Path) -> str:
    try:
        return path.resolve().relative_to(target_project.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def rebuild_shared_dependency_index(shared_root: Path, target_project: Path) -> dict:
    """Recover the local index from canonical files when Library was regenerated."""
    assets: dict[str, dict] = {}
    if not shared_root.is_dir():
        return {"schema_version": "shared_dependency_index.v1", "assets": assets}
    for path in iter_files(shared_root):
        if path.suffix.lower() == ".meta" or not is_shared_dependency(path):
            continue
        digest = sha256_file(path)
        assets[digest] = {
            "relative_path": path.resolve().relative_to(target_project.resolve()).as_posix(),
            "unity_guid": read_meta_guid(Path(str(path) + ".meta")),
            "sha256": digest,
            "role": infer_role(path),
            "source_path": None,
        }
    return {"schema_version": "shared_dependency_index.v1", "assets": assets}


def ensure_distinct_shared_and_sample_roots(destination: Path, shared_root: Path) -> None:
    destination = destination.resolve()
    shared_root = shared_root.resolve()
    if destination == shared_root:
        raise ValueError("sample destination must not equal the shared dependency store")
    try:
        destination.relative_to(shared_root)
    except ValueError:
        pass
    else:
        raise ValueError("sample destination must not be inside the shared dependency store")
    try:
        shared_root.relative_to(destination)
    except ValueError:
        pass
    else:
        raise ValueError("shared dependency store must not be inside the sample destination")


def validate_shared_copy_integrity(
    target_project: Path,
    destination: Path,
    shared_manifest: list[dict],
    sample_files: list[Path],
    source_project: Path,
    selected_root: Path,
) -> dict:
    """Fail before metadata is emitted when a reported copy is not physically present."""
    missing: list[str] = []
    for record in shared_manifest:
        canonical = record.get("canonical", {}) if isinstance(record, dict) else {}
        relative = canonical.get("relative_path") if isinstance(canonical, dict) else None
        if not isinstance(relative, str):
            missing.append("shared dependency without canonical relative_path")
            continue
        file_path = target_project / relative
        if not file_path.is_file() or not Path(str(file_path) + ".meta").is_file():
            missing.append(file_path.as_posix())
    for source_file in sample_files:
        relative = source_asset_relative_path(source_file, source_project, selected_root)
        file_path = destination / relative
        if not file_path.is_file() or not Path(str(file_path) + ".meta").is_file():
            missing.append(file_path.as_posix())
    if missing:
        preview = "; ".join(missing[:3])
        raise RuntimeError(f"shared dependency import integrity check failed: {preview}")
    return {
        "status": "passed",
        "shared_asset_count": len(shared_manifest),
        "sample_asset_count": len(sample_files),
    }


def _shared_relative_path(source_file: Path, source_project: Path | None, digest: str) -> Path:
    if is_shader_package_dependency(source_file):
        return Path("ShaderPackages") / source_asset_relative_path(source_file, source_project, source_file)
    role = infer_role(source_file)
    suffix = source_file.suffix.lower()
    role_folder = {
        "shader": "Shaders",
        "shader_include": "ShaderIncludes",
        "shadergraph": "Shaders",
        "shadersubgraph": "Shaders",
        "texture": "Textures",
        "mesh": "Meshes",
        "animation": "Animation",
        "unity_asset": "UnityAssets",
    }.get(role, "Other")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source_file.stem).strip("_") or "asset"
    return Path(role_folder) / digest[:2] / f"{stem}_{digest[:16]}{suffix}"


def _rewrite_guid_references(path: Path, guid_map: dict[str, str], dry_run: bool) -> int:
    if not guid_map or not is_rewritable_unity_text(path):
        return 0
    text = path.read_text(encoding="utf-8", errors="ignore")
    changes = 0

    def replace(match: re.Match) -> str:
        nonlocal changes
        guid = match.group(1).lower()
        replacement = guid_map.get(guid)
        if replacement is None or replacement == guid:
            return match.group(0)
        changes += 1
        return match.group(0).replace(match.group(1), replacement)

    updated = GUID_RE.sub(replace, text)
    if changes and not dry_run:
        path.write_text(updated, encoding="utf-8")
    return changes


def copy_dependency_closure_shared(
    config: IngestConfig,
    destination: Path,
    source_project: Path,
    closure_files: list[Path],
) -> tuple[Path, dict]:
    """Copy a sample while sharing content-addressed dependencies across samples.

    Binary/shared dependency files are stored once under `shared_dependency_store`.
    Unity YAML references in copied sample files are rewritten to canonical GUIDs.
    """
    if config.target_unity_project is None:
        raise ValueError("target Unity project is required")
    target_project = config.target_unity_project.resolve()
    shared_under = config.shared_dependency_store or "Assets/VFXSourceIngest/Shared"
    shared_root = (target_project / shared_under).resolve()
    try:
        shared_root.relative_to((target_project / "Assets").resolve())
    except ValueError as exc:
        raise ValueError("shared dependency store must stay under target Unity Assets") from exc
    ensure_distinct_shared_and_sample_roots(destination, shared_root)
    index_path = config.shared_index_path.resolve() if config.shared_index_path else default_shared_dependency_index_path(target_project)
    index = load_shared_dependency_index(index_path) if index_path.exists() else rebuild_shared_dependency_index(shared_root, target_project)
    assets: dict = index["assets"]
    source_files = sorted(closure_files, key=lambda p: p.as_posix().lower())
    sample_files = [path for path in source_files if not is_shared_dependency(path)]
    shared_files = [path for path in source_files if is_shared_dependency(path)]
    shader_files = [path for path in shared_files if is_shader_package_dependency(path)]
    shared_files = shader_files + [path for path in shared_files if not is_shader_package_dependency(path)]
    if destination.exists() and config.overwrite and not config.dry_run:
        remove_existing_destination(destination)
    if not config.dry_run:
        destination.mkdir(parents=True, exist_ok=True)
        shared_root.mkdir(parents=True, exist_ok=True)
        _ensure_folder_meta(target_project / "Assets", destination)
        _ensure_folder_meta(target_project / "Assets", shared_root)

    old_to_new_guid: dict[str, str] = {}
    copied_shared = reused_shared = 0
    shared_manifest: list[dict] = []
    for source_file in shared_files:
        digest = sha256_file(source_file)
        original_guid = read_meta_guid(Path(str(source_file) + ".meta"))
        existing = assets.get(digest)
        relative = _shared_relative_path(source_file, source_project, digest)
        canonical_file = shared_root / relative
        if existing:
            indexed_path = target_project / existing.get("relative_path", "")
            if not indexed_path.is_file():
                existing = None
            elif is_shader_package_dependency(source_file) and indexed_path.resolve() != canonical_file.resolve():
                raise ValueError(
                    f"shader package path conflict for identical content: {source_file} -> {indexed_path}; expected {canonical_file}"
                )
        if existing:
            canonical_guid = existing.get("unity_guid")
            if not canonical_guid:
                raise RuntimeError(f"shared dependency has no .meta GUID: {indexed_path}")
            if original_guid and canonical_guid:
                old_to_new_guid[original_guid.lower()] = canonical_guid.lower()
            reused_shared += 1
            shared_manifest.append({"source": source_file.as_posix(), "sha256": digest, "action": "reused", "canonical": existing})
            continue
        if canonical_file.exists() and not config.dry_run:
            raise FileExistsError(f"shared canonical path exists but is not indexed: {canonical_file}")
        if not config.dry_run:
            copy_asset_with_meta(
                source_file,
                canonical_file,
                shared_root,
                source_project,
                relative,
                preserve_guid=False,
            )
        canonical_guid = read_meta_guid(Path(str(canonical_file) + ".meta")) if not config.dry_run else original_guid
        if original_guid and canonical_guid:
            old_to_new_guid[original_guid.lower()] = canonical_guid.lower()
        entry = {
            "relative_path": canonical_file.relative_to(target_project).as_posix(),
            "unity_guid": canonical_guid,
            "sha256": digest,
            "role": infer_role(source_file),
            "source_path": source_file.as_posix(),
        }
        assets[digest] = entry
        copied_shared += 1
        shared_manifest.append({"source": source_file.as_posix(), "sha256": digest, "action": "copied", "canonical": entry})

    # Materials keep per-sample parameter ownership. Reusing their source GUID
    # below several imported Prefab roots makes Unity bind one copy arbitrarily.
    sample_material_files = [path for path in sample_files if infer_role(path) == "material"]
    sample_non_material_files = [path for path in sample_files if infer_role(path) != "material"]
    copied_sample = 0
    rebased_materials = 0
    for source_file in sample_material_files:
        relative = source_asset_relative_path(source_file, source_project, config.source_path)
        if not config.dry_run:
            copied_material = destination / relative
            copy_asset_with_meta(
                source_file,
                copied_material,
                destination,
                source_project,
                relative,
                preserve_guid=False,
            )
            original_guid = read_meta_guid(Path(str(source_file) + ".meta"))
            rebased_guid = read_meta_guid(Path(str(copied_material) + ".meta"))
            if original_guid and rebased_guid:
                old_to_new_guid[original_guid.lower()] = rebased_guid.lower()
        rebased_materials += 1
        copied_sample += 1
    for source_file in sample_non_material_files:
        relative = source_asset_relative_path(source_file, source_project, config.source_path)
        if not config.dry_run:
            copy_asset_with_meta(source_file, destination / relative, destination, source_project, relative)
        copied_sample += 1
    rewritten_references = 0
    if config.rewrite_guid_references:
        for source_file in sample_files:
            relative = source_asset_relative_path(source_file, source_project, config.source_path)
            copied_file = destination / relative
            if config.dry_run:
                if is_rewritable_unity_text(source_file):
                    text = source_file.read_text(encoding="utf-8", errors="ignore")
                    rewritten_references += sum(1 for guid in GUID_RE.findall(text) if guid.lower() in old_to_new_guid)
            elif copied_file.exists():
                rewritten_references += _rewrite_guid_references(copied_file, old_to_new_guid, False)
    integrity = validate_shared_copy_integrity(
        target_project,
        destination,
        shared_manifest,
        sample_files,
        source_project,
        config.source_path,
    ) if not config.dry_run else {"status": "planned", "shared_asset_count": len(shared_manifest), "sample_asset_count": len(sample_files)}
    if not config.dry_run:
        save_shared_dependency_index(index_path, index)
    if config.target_unity_project is None:
        raise ValueError("target Unity project is required")
    if config.dry_run:
        report = {
            "mode": "shared_dependency_pool",
            "shared_root": shared_root.relative_to(target_project).as_posix(),
            "shader_package_policy": "source_relative_paths_preserved",
            "shared_index": project_relative_or_absolute(index_path, target_project),
            "copied_shared": copied_shared,
            "reused_shared": reused_shared,
            "copied_sample": copied_sample,
            "guid_rewrite_count": rewritten_references,
            "guid_mapping_count": len(old_to_new_guid),
            "rebased_material_count": rebased_materials,
            "dry_run": True,
            "assets": shared_manifest,
            "integrity": integrity,
        }
        return config.source_path.resolve(), report
    report = {
        "mode": "shared_dependency_pool",
        "shared_root": shared_root.relative_to(target_project).as_posix(),
        "shared_index": project_relative_or_absolute(index_path, target_project),
        "copied_shared": copied_shared,
        "reused_shared": reused_shared,
        "copied_sample": copied_sample,
        "guid_rewrite_count": rewritten_references,
        "guid_mapping_count": len(old_to_new_guid),
        "rebased_material_count": rebased_materials,
        "dry_run": config.dry_run,
        "assets": shared_manifest,
        "integrity": integrity,
    }
    return destination, report


def copy_into_unity_project(config: IngestConfig) -> Path:
    if config.target_unity_project is None:
        raise ValueError("--target-unity-project is required when --copy-assets is set")
    target_project = config.target_unity_project.resolve()
    target_assets = target_project / config.copy_under
    destination = (target_assets / (config.copy_name or config.source_id)).resolve()
    try:
        destination.relative_to((target_project / "Assets").resolve())
    except ValueError as exc:
        raise ValueError("copy destination must stay under the target Unity Assets directory") from exc
    if destination.exists() and not config.overwrite and not config.dry_run:
        raise FileExistsError(f"copy destination already exists: {destination}")
    if not config.dry_run:
        target_assets.mkdir(parents=True, exist_ok=True)
        _ensure_folder_meta(target_project / "Assets", target_assets)
    if config.copy_dependency_closure:
        source_project = config.source_unity_project or infer_unity_project(config.source_path)
        if source_project is None:
            raise ValueError("--copy-dependency-closure requires --source-unity-project or an inferable Unity project")
        if config.dedupe_by == "sha256" and config.shared_dependency_store:
            ensure_distinct_shared_and_sample_roots(destination, (target_project / config.shared_dependency_store).resolve())
        if config.overwrite and not config.dry_run:
            remove_existing_destination(destination)
        if not config.dry_run:
            destination.mkdir(parents=True, exist_ok=True)
            _ensure_folder_meta(target_project / "Assets", destination)
        project_guid_map = scan_guid_map(source_project / "Assets", source_project)
        initial_files = [path for path in iter_files(config.source_path) if path.suffix.lower() != ".meta"]
        closure_files, _ignored_guids = collect_dependency_closure(
            initial_files,
            project_guid_map,
            source_project=source_project,
            include_scripts=config.include_script_dependencies,
            max_depth=config.max_dependency_depth,
        )
        if config.dedupe_by == "sha256" and config.shared_dependency_store:
            _destination, _report = copy_dependency_closure_shared(
                config, destination, source_project, closure_files
            )
            report_path = config.output_dir.resolve() / "shared_dependency_report.json"
            if config.dry_run:
                config.output_dir.resolve().mkdir(parents=True, exist_ok=True)
                (config.output_dir.resolve() / "shared_dependency_dry_run.json").write_text(
                    json.dumps(_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                return config.source_path.resolve()
            if not config.dry_run:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(json.dumps(_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return destination
        for source_file in closure_files:
            relative_path = source_asset_relative_path(source_file, source_project, config.source_path)
            if not config.dry_run:
                copy_asset_with_meta(source_file, destination / relative_path, destination, source_project, relative_path)
        return config.source_path.resolve() if config.dry_run else destination
    source = config.source_path.resolve()
    if config.dry_run:
        return source
    if destination.exists() and config.overwrite:
        remove_existing_destination(destination)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=config.overwrite)
        source_meta = Path(str(source) + ".meta")
        if source_meta.exists():
            shutil.copy2(source_meta, Path(str(destination) + ".meta"))
        else:
            write_generated_folder_meta(Path(str(destination) + ".meta"))
    else:
        destination.mkdir(parents=True, exist_ok=True)
        if not Path(str(destination) + ".meta").exists():
            write_generated_folder_meta(Path(str(destination) + ".meta"))
        shutil.copy2(source, destination / source.name)
        source_meta = Path(str(source) + ".meta")
        if source_meta.exists():
            shutil.copy2(source_meta, destination / source_meta.name)
    return destination


def _ensure_folder_meta(assets_root: Path, folder: Path) -> None:
    assets_root = assets_root.resolve()
    folder = folder.resolve()
    chain = [folder]
    current = folder.parent
    while current != assets_root and current != current.parent:
        chain.append(current)
        current = current.parent
    for item in reversed(chain):
        meta = Path(str(item) + ".meta")
        if meta.exists():
            continue
        write_generated_folder_meta(meta)


def write_generated_folder_meta(meta: Path) -> None:
    meta.write_text(
        "\n".join(
            [
                "fileFormatVersion: 2",
                f"guid: {uuid.uuid4().hex}",
                "folderAsset: yes",
                "DefaultImporter:",
                "  externalObjects: {}",
                "  userData: ",
                "  assetBundleName: ",
                "  assetBundleVariant: ",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_generated_asset_meta(meta: Path) -> None:
    meta.write_text(
        "\n".join(
            [
                "fileFormatVersion: 2",
                f"guid: {uuid.uuid4().hex}",
                "DefaultImporter:",
                "  externalObjects: {}",
                "  userData: ",
                "  assetBundleName: ",
                "  assetBundleVariant: ",
                "",
            ]
        ),
        encoding="utf-8",
    )


def extract_text_markers(files: Iterable[Path]) -> Counter:
    markers: Counter = Counter()
    for path in files:
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        markers["particle_systems"] += len(re.findall(r"(?m)^ParticleSystem:", text))
        markers["particle_renderers"] += len(re.findall(r"(?m)^ParticleSystemRenderer:", text))
        markers["trail_renderers"] += len(re.findall(r"(?m)^TrailRenderer:", text))
        markers["line_renderers"] += len(re.findall(r"(?m)^LineRenderer:", text))
        markers["animators"] += len(re.findall(r"(?m)^Animator:", text))
    return markers


def dependency_records(
    files: Iterable[Path],
    selected_root: Path,
    selected_guid_map: dict[str, Path],
    project_guid_map: dict[str, Path],
    manifest_project: Path | None,
    source_project: Path | None,
    ignored_dependency_guids: set[str] | None = None,
    shared_guid_map: dict[str, Path] | None = None,
) -> list[dict]:
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    selected_root = selected_root.resolve()
    ignored_dependency_guids = ignored_dependency_guids or set()
    shared_guid_map = shared_guid_map or {}
    for path in files:
        if path.suffix.lower() not in TEXT_EXTENSIONS or path.suffix.lower() == ".meta":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        from_path = asset_path(path, manifest_project, selected_root)
        for raw_guid in GUID_RE.findall(text):
            guid = raw_guid.lower()
            key = (from_path, guid)
            if key in seen:
                continue
            seen.add(key)
            if is_unity_builtin_guid(guid):
                records.append(
                    {
                        "from_path": from_path,
                        "to_path": None,
                        "to_guid": guid,
                        "dependency_type": "unity_builtin",
                        "status": "unknown",
                    }
                )
                continue
            target = selected_guid_map.get(guid)
            status = "resolved"
            target_project = manifest_project
            if target is None and guid in shared_guid_map:
                target = shared_guid_map[guid]
                status = "resolved_shared"
                target_project = manifest_project
            if target is None:
                target = project_guid_map.get(guid)
                if target is not None and guid in ignored_dependency_guids:
                    status = "ignored"
                else:
                    status = "external" if target is not None else "missing"
                target_project = source_project
            records.append(
                {
                    "from_path": from_path,
                    "to_path": asset_path(target, target_project, selected_root) if target else None,
                    "to_guid": guid,
                    "dependency_type": infer_role(target) if target else "unknown",
                    "status": status,
                }
            )
    return records


def material_selection_summary(
    *,
    material_paths: list[str],
    texture_paths: list[str],
    shader_paths: list[str],
    dependencies: list[dict],
    texture_tag_index: dict[str, Any] | None = None,
) -> dict:
    dependency_groups: dict[str, list[dict[str, Any]]] = {}
    for dependency in dependencies:
        dependency_groups.setdefault(dependency["from_path"], []).append(dependency)

    texture_tag_index = texture_tag_index or {}
    texture_tag_index_status = texture_tag_index.get("status") or ("loaded" if texture_tag_index else "unavailable")
    texture_tag_index_path = texture_tag_index.get("path")
    texture_tag_index_records = texture_tag_index.get("record_count")

    def texture_tag_record(texture_path: str) -> tuple[str | None, dict[str, Any] | None]:
        normalized_path = texture_path.replace("\\", "/")
        asset_id = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()
        by_asset_id = texture_tag_index.get("by_asset_id") or {}
        by_relative_path = texture_tag_index.get("by_relative_path") or {}
        by_basename = texture_tag_index.get("by_basename") or {}
        record = by_asset_id.get(asset_id)
        if record is not None:
            return "asset_id", record
        record = by_relative_path.get(normalized_path)
        if record is not None:
            return "relative_path", record
        record = by_basename.get(Path(normalized_path).name)
        if record is not None:
            return "basename", record
        return None, None

    def slot_roles_from_tags(tags: list[str]) -> list[str]:
        return sorted({tag.removeprefix("slot.") for tag in tags if tag.startswith("slot.")})

    texture_candidates: list[dict[str, Any]] = []
    texture_candidate_by_path: dict[str, dict[str, Any]] = {}
    for texture_path in texture_paths:
        tag_match, tag_record = texture_tag_record(texture_path)
        tags = list(tag_record.get("tags") or []) if tag_record else []
        texture_candidate = {
            "path": texture_path,
            "role": "texture",
            "status": "candidate",
            "tag_match": tag_match,
            "tag_source": "texture_tag_index" if tag_record else "dependency_only",
            "asset_id": tag_record.get("asset_id") if tag_record else None,
            "tags": tags,
            "slot_roles": slot_roles_from_tags(tags),
            "license_status": tag_record.get("license_status", "unknown") if tag_record else "unknown",
            "thumbnail_status": tag_record.get("thumbnail_status") if tag_record else None,
            "width": tag_record.get("width") if tag_record else None,
            "height": tag_record.get("height") if tag_record else None,
        }
        texture_candidates.append(texture_candidate)
        texture_candidate_by_path[texture_path] = texture_candidate

    materials: list[dict[str, Any]] = []
    for material_path in material_paths:
        material_dependencies = dependency_groups.get(material_path, [])
        shader_dependencies = sorted(
            {
                dependency["to_path"]
                for dependency in material_dependencies
                if dependency["dependency_type"] == "shader" and dependency.get("to_path")
            }
        )
        texture_dependencies = sorted(
            {
                dependency["to_path"]
                for dependency in material_dependencies
                if dependency["dependency_type"] == "texture" and dependency.get("to_path")
            }
        )
        texture_bindings = [
            texture_candidate_by_path.get(texture_path)
            or {
                "path": texture_path,
                "role": "texture",
                "status": "candidate",
                "tag_match": None,
                "tag_source": "dependency_only",
                "asset_id": None,
                "tags": [],
                "slot_roles": [],
                "license_status": "unknown",
                "thumbnail_status": None,
                "width": None,
                "height": None,
            }
            for texture_path in texture_dependencies
        ]
        materials.append(
            {
                "material_path": material_path,
                "primary_shader_path": shader_dependencies[0] if shader_dependencies else None,
                "shader_paths": shader_dependencies,
                "texture_paths": texture_dependencies,
                "texture_bindings": texture_bindings,
                "tagged_texture_count": sum(1 for texture in texture_bindings if texture.get("tags")),
                "untagged_texture_count": sum(1 for texture in texture_bindings if not texture.get("tags")),
                "slot_role_hints": sorted({slot for texture in texture_bindings for slot in texture.get("slot_roles", [])}),
                "dependency_count": len(material_dependencies),
                "dependency_types": sorted({dependency["dependency_type"] for dependency in material_dependencies}),
            }
        )

    return {
        "material_count": len(material_paths),
        "shader_count": len(shader_paths),
        "texture_count": len(texture_paths),
        "texture_tag_index_path": texture_tag_index_path,
        "texture_tag_index_status": texture_tag_index_status,
        "texture_tag_index_record_count": texture_tag_index_records,
        "texture_tagging_status": "required_for_slot_selection",
        "materials": materials[:100],
        "shader_candidates": [
            {
                "path": path,
                "role": "shader",
                "status": "candidate",
            }
            for path in shader_paths[:100]
        ],
        "texture_candidates": texture_candidates[:100],
        "selection_basis": [
            "shader paths come from resolved material dependency edges",
            "texture tag records are joined to texture paths so slot roles can be learned from evidence, not counts",
            "raw counts are not enough; keep shader and tagged texture candidates available to the training step",
        ],
    }


def file_record(path: Path, project: Path | None, root: Path, license_status: str, hash_files: bool) -> dict:
    meta_path = Path(str(path) + ".meta") if path.suffix.lower() != ".meta" else None
    guid = read_meta_guid(meta_path) if meta_path else None
    stat = path.stat()
    role = infer_role(path)
    record = {
        "role": role,
        "path": asset_path(path, project, root),
        "file_type": path.suffix.lower().lstrip(".") or "none",
        "unity_guid": guid,
        "meta_path": asset_path(meta_path, project, root) if meta_path and meta_path.exists() else None,
        "sha256": sha256_file(path) if hash_files and path.is_file() else None,
        "size_bytes": stat.st_size,
        "license_status": "inherits_source" if role != "texture" else license_status,
        "commit_policy": "metadata_only" if role not in {"texture", "mesh"} else "do_not_commit",
    }
    if role == "texture":
        record["importer"] = {"source": "unity_meta_if_available"}
    return record


def _safe_project_asset_path(project: Path, raw_path: str, label: str) -> Path:
    candidate = (project / raw_path).resolve()
    assets_root = (project / "Assets").resolve()
    try:
        candidate.relative_to(assets_root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay under the Unity Assets directory: {raw_path}") from exc
    return candidate


def load_shader_gui_policy(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("dependencies") if isinstance(payload, dict) else None
    if not isinstance(entries, dict):
        raise ValueError(f"shader GUI policy has no dependencies map: {path}")
    result: dict[str, dict[str, Any]] = {}
    for class_name, entry in entries.items():
        if not isinstance(class_name, str) or not isinstance(entry, dict):
            raise ValueError(f"shader GUI policy entry is invalid: {class_name!r}")
        result[class_name] = dict(entry)
    return result


def _class_index(project: Path | None) -> dict[str, list[str]]:
    if project is None:
        return {}
    roots = [project / "Assets", project / "Packages", project / "Library" / "PackageCache"]
    result: dict[str, list[str]] = defaultdict(list)
    for root in roots:
        if not root.is_dir():
            continue
        for source in root.rglob("*.cs"):
            if root.name == "Assets" and is_ignored(source, root):
                continue
            try:
                text = source.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            namespace = ""
            namespace_match = CS_NAMESPACE_RE.search(text)
            if namespace_match:
                namespace = namespace_match.group(1)
            for class_match in CS_CLASS_RE.finditer(text):
                simple_name = class_match.group(1)
                full_name = f"{namespace}.{simple_name}" if namespace else simple_name
                try:
                    relative = source.resolve().relative_to(project.resolve()).as_posix()
                except ValueError:
                    relative = source.resolve().as_posix()
                result[full_name].append(relative)
                result[simple_name].append(relative)
    return {name: sorted(set(paths)) for name, paths in result.items()}


def _project_has_package(project: Path | None, package_name: str) -> bool:
    if project is None:
        return False
    manifest_path = project / "Packages" / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return package_name in (manifest.get("dependencies") or {})


def _copy_allowed_shader_gui_dependency(
    class_name: str,
    policy: dict[str, Any] | None,
    source_project: Path | None,
    target_project: Path | None,
    dry_run: bool,
) -> dict[str, Any]:
    if policy is None:
        return {"action": "not_allowed", "reason": "no_explicit_policy"}
    if policy.get("allowed") is not True:
        return {"action": "not_allowed", "reason": "policy_not_explicitly_allowed"}
    license_status = str(policy.get("license_status") or "unknown")
    if license_status not in ALLOWED_SHADER_GUI_LICENSE_STATUSES:
        return {"action": "not_allowed", "reason": f"license_not_allowed:{license_status}"}
    source_path = policy.get("source_path")
    target_path = policy.get("target_path") or source_path
    if not isinstance(source_path, str) or not isinstance(target_path, str):
        return {"action": "not_allowed", "reason": "policy_requires_source_path_and_target_path"}
    if source_project is None or target_project is None:
        return {"action": "not_allowed", "reason": "source_and_target_projects_required"}
    source = _safe_project_asset_path(source_project, source_path, f"policy source path for {class_name}")
    target = _safe_project_asset_path(target_project, target_path, f"policy target path for {class_name}")
    if not source.exists():
        return {"action": "not_allowed", "reason": "policy_source_missing", "source_path": source_path}
    if target.exists():
        return {"action": "not_allowed", "reason": "policy_target_exists", "target_path": target_path}
    if dry_run:
        return {"action": "would_copy", "source_path": source_path, "target_path": target_path}
    target.parent.mkdir(parents=True, exist_ok=True)
    _ensure_folder_meta(target_project / "Assets", target.parent)
    if source.is_dir():
        shutil.copytree(source, target)
        source_meta = Path(str(source) + ".meta")
        target_meta = Path(str(target) + ".meta")
        if source_meta.is_file():
            shutil.copy2(source_meta, target_meta)
        else:
            write_generated_folder_meta(target_meta)
    else:
        shutil.copy2(source, target)
        source_meta = Path(str(source) + ".meta")
        target_meta = Path(str(target) + ".meta")
        if source_meta.is_file():
            shutil.copy2(source_meta, target_meta)
        else:
            write_generated_asset_meta(target_meta)
    return {"action": "copied", "source_path": source_path, "target_path": target_path, "license_status": license_status}


def shader_paths_for_integrity(
    asset_files: list[Path],
    dependencies: list[dict[str, Any]],
    manifest_project: Path | None,
    source_project: Path | None,
    selected_root: Path,
) -> list[Path]:
    paths = {path.resolve() for path in asset_files if infer_role(path) == "shader"}
    for dependency in dependencies:
        if dependency.get("dependency_type") != "shader" or not dependency.get("to_path"):
            continue
        project = manifest_project if dependency.get("status") in {"resolved", "resolved_shared"} else source_project
        candidate = _resolved_source_file(str(dependency["to_path"]), project, selected_root)
        if candidate is not None and candidate.is_file():
            paths.add(candidate.resolve())
    return sorted(paths, key=lambda path: path.as_posix().lower())


def material_paths_for_integrity(
    asset_files: list[Path],
    dependencies: list[dict[str, Any]],
    manifest_project: Path | None,
    source_project: Path | None,
    selected_root: Path,
) -> list[Path]:
    paths = {path.resolve() for path in asset_files if infer_role(path) == "material"}
    for dependency in dependencies:
        if dependency.get("dependency_type") != "material" or not dependency.get("to_path"):
            continue
        project = manifest_project if dependency.get("status") in {"resolved", "resolved_shared"} else source_project
        candidate = _resolved_source_file(str(dependency["to_path"]), project, selected_root)
        if candidate is not None and candidate.is_file():
            paths.add(candidate.resolve())
    return sorted(paths, key=lambda path: path.as_posix().lower())


def shader_custom_editor_report(
    shader_paths: list[Path],
    source_project: Path | None,
    target_project: Path | None,
    selected_root: Path,
    policy_path: Path | None,
    copy_dependencies: bool,
    dry_run: bool,
) -> dict[str, Any]:
    declarations: list[dict[str, str]] = []
    for shader_path in shader_paths:
        try:
            text = shader_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        owner = target_project or source_project
        declarations.extend(
            {
                "shader_path": asset_path(shader_path, owner, selected_root),
                "custom_editor": match.group(1),
            }
            for match in CUSTOM_EDITOR_RE.finditer(text)
        )
    declarations.sort(key=lambda row: (row["shader_path"], row["custom_editor"]))
    policy = load_shader_gui_policy(policy_path)
    source_classes = _class_index(source_project)
    target_classes = _class_index(target_project)
    copy_actions: dict[str, dict[str, Any]] = {}
    for class_name in sorted({row["custom_editor"] for row in declarations}):
        if class_name in target_classes:
            continue
        if copy_dependencies:
            copy_actions[class_name] = _copy_allowed_shader_gui_dependency(
                class_name,
                policy.get(class_name),
                source_project,
                target_project,
                dry_run,
            )
    if any(action.get("action") == "copied" for action in copy_actions.values()):
        target_classes = _class_index(target_project)

    records: list[dict[str, Any]] = []
    for declaration in declarations:
        class_name = declaration["custom_editor"]
        class_paths = target_classes.get(class_name, [])
        package_name = KNOWN_CUSTOM_EDITOR_PACKAGES.get(class_name)
        action = copy_actions.get(class_name)
        if class_paths:
            target_status = "copied_allowed" if action and action.get("action") == "copied" else "available"
        elif package_name and _project_has_package(target_project, package_name):
            target_status = "provided_by_package"
        else:
            target_status = "needs_manual_dependency"
        policy_entry = policy.get(class_name)
        records.append(
            {
                **declaration,
                "source_status": "available" if class_name in source_classes else "not_found_in_source_project",
                "source_class_paths": source_classes.get(class_name, []),
                "target_status": target_status,
                "target_class_paths": class_paths,
                "package": package_name,
                "license_status": str(policy_entry.get("license_status") or "unverified") if policy_entry else "unverified",
                "copy_action": action or {"action": "not_requested"},
            }
        )
    status_counts = Counter(record["target_status"] for record in records)
    return {
        "schema_version": "vfx_shader_custom_editor_report.v1",
        "policy_path": policy_path.as_posix() if policy_path else None,
        "copy_requested": copy_dependencies,
        "shader_count": len(shader_paths),
        "custom_editor_declaration_count": len(records),
        "target_status_counts": dict(sorted(status_counts.items())),
        "records": records,
    }


def _material_guid_duplicates(root: Path, project: Path | None, selected_root: Path) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for meta_path in iter_files(root):
        if meta_path.suffix.lower() != ".meta" or meta_path.with_suffix("").suffix.lower() != ".mat":
            continue
        guid = read_meta_guid(meta_path)
        if guid:
            groups[guid].append(asset_path(meta_path.with_suffix(""), project, selected_root))
    return [
        {"guid": guid, "material_paths": sorted(paths)}
        for guid, paths in sorted(groups.items())
        if len(paths) > 1
    ]


def material_integrity_report(
    material_files: list[Path],
    guid_map: dict[str, Path],
    dependencies: list[dict[str, Any]],
    project: Path | None,
    selected_root: Path,
) -> dict[str, Any]:
    slots: list[dict[str, Any]] = []
    errors: list[str] = []
    for material_path in material_files:
        try:
            text = material_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        material_asset_path = asset_path(material_path, project, selected_root)
        for slot_index, match in enumerate(MATERIAL_TEXTURE_SLOT_RE.finditer(text), start=1):
            attributes = match.group(1)
            guid_match = GUID_RE.search(attributes)
            slot: dict[str, Any] = {
                "material_path": material_asset_path,
                "slot_index": slot_index,
                "guid": None,
                "resolved_path": None,
                "resolved_role": None,
                "status": "unbound",
            }
            if guid_match is None:
                slot["status"] = "unbound" if re.search(r"\bfileID:\s*0\b", attributes) else "unity_builtin"
            else:
                guid = guid_match.group(1).lower()
                resolved = guid_map.get(guid)
                role = infer_role(resolved) if resolved is not None else "unknown"
                slot.update(
                    {
                        "guid": guid,
                        "resolved_path": asset_path(resolved, project, selected_root) if resolved else None,
                        "resolved_role": role,
                        "status": "resolved" if role == "texture" else "missing" if resolved is None else "wrong_asset_type",
                    }
                )
                if slot["status"] != "resolved":
                    errors.append(f"{material_asset_path} texture slot {slot_index}: {slot['status']}")
            slots.append(slot)

    audit_root = (project / "Assets") if project is not None else selected_root
    duplicates = _material_guid_duplicates(audit_root, project, selected_root)
    errors.extend(
        f"duplicate material GUID {row['guid']}: {', '.join(row['material_paths'])}"
        for row in duplicates
    )
    dependency_type_counts = Counter(str(dependency.get("dependency_type") or "unknown") for dependency in dependencies)
    dependency_status_counts = Counter(str(dependency.get("status") or "unknown") for dependency in dependencies)
    slot_status_counts = Counter(slot["status"] for slot in slots)
    return {
        "schema_version": "vfx_material_integrity_report.v1",
        "scope": "target_project_assets" if project is not None else "selected_source_root",
        "material_count": len(material_files),
        "guid_reference_summary": {
            "dependency_type_counts": dict(sorted(dependency_type_counts.items())),
            "dependency_status_counts": dict(sorted(dependency_status_counts.items())),
            "note": "Dependency types distinguish texture, shader, script, and other Unity GUID references; only m_Texture slots are a hard material texture gate.",
        },
        "m_texture_slots": slots,
        "m_texture_slot_status_counts": dict(sorted(slot_status_counts.items())),
        "material_guid_duplicates": duplicates,
        "gate": {
            "status": "failed" if errors else "passed",
            "error_count": len(errors),
            "errors": errors,
        },
    }


def _resolved_source_file(record_path: str, project: Path | None, root: Path) -> Path:
    path = Path(record_path)
    if path.is_absolute():
        return path
    if project is not None:
        return (project / path).resolve()
    return (root / path).resolve()


def build_local_texture_tag_index(
    texture_files: list[dict[str, Any]],
    project: Path | None,
    root: Path,
    output_path: Path,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for file in texture_files:
        relative_path = str(file["path"]).replace("\\", "/")
        texture_path = _resolved_source_file(relative_path, project, root)
        if not texture_path.exists():
            continue
        image_meta = read_image_metadata(texture_path)
        tagged = tag_texture_record(
            {
                "asset_id": hashlib.sha256(relative_path.encode("utf-8")).hexdigest(),
                "relative_path": relative_path,
                "asset_type": "texture",
                "extension": texture_path.suffix.lower(),
                "width": image_meta.get("width"),
                "height": image_meta.get("height"),
                "license_status": file.get("license_status", "unknown"),
                "thumbnail_status": None,
                "tags": [],
                "metrics": {},
            },
            project or root,
        )
        tagged["source_file_path"] = texture_path.as_posix()
        records.append(tagged)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return load_texture_tag_index(output_path)


def load_texture_tag_index(path: Path | None) -> dict[str, Any]:
    index = {
        "path": path.as_posix() if path is not None else None,
        "status": "unavailable",
        "record_count": 0,
        "by_asset_id": {},
        "by_relative_path": {},
        "by_basename": {},
    }
    if path is None:
        return index
    if not path.exists():
        index["status"] = "missing"
        return index

    basename_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    record_count = 0
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            normalized_path = str(record.get("relative_path") or "").replace("\\", "/")
            asset_id = str(record.get("asset_id") or "").strip()
            if asset_id:
                index["by_asset_id"][asset_id] = record
            if normalized_path:
                index["by_relative_path"][normalized_path] = record
                basename_buckets[Path(normalized_path).name].append(record)
            record_count += 1
    index["by_basename"] = {
        name: records[0]
        for name, records in basename_buckets.items()
        if len(records) == 1
    }
    index["record_count"] = record_count
    index["status"] = "loaded"
    return index


def _default_guid_cache_path(config: IngestConfig, source_project: Path | None) -> Path | None:
    if config.project_guid_cache is not None:
        return config.project_guid_cache.resolve()
    if source_project is None:
        return None
    digest = hashlib.sha256(source_project.resolve().as_posix().encode("utf-8")).hexdigest()[:16]
    return config.output_dir.resolve().parent / "guid_cache" / f"{digest}.json"


def build_source_ingest(config: IngestConfig) -> dict[str, Path]:
    if not config.source_path.exists():
        raise FileNotFoundError(f"source path does not exist: {config.source_path}")
    source_project = config.source_unity_project or infer_unity_project(config.source_path)
    source_project_guid_map = {}
    guid_cache_summary = None
    ignored_dependency_guids: set[str] = set()
    if source_project is not None:
        source_project_guid_map, guid_cache_summary = load_or_build_guid_map(
            source_project / "Assets",
            source_project,
            _default_guid_cache_path(config, source_project),
        )
    if config.copy_assets and config.copy_dependency_closure:
        initial_files = [path for path in iter_files(config.source_path) if path.suffix.lower() != ".meta"]
        _closure_files, ignored_dependency_guids = collect_dependency_closure(
            initial_files,
            source_project_guid_map,
            source_project=source_project,
            include_scripts=config.include_script_dependencies,
            max_depth=config.max_dependency_depth,
        )
    scan_root = copy_into_unity_project(config) if config.copy_assets else config.source_path.resolve()
    shared_dependency_report = None
    if config.copy_assets and config.copy_dependency_closure and config.dedupe_by == "sha256" and config.shared_dependency_store:
        report_path = config.output_dir.resolve() / "shared_dependency_report.json"
        if report_path.exists():
            try:
                shared_dependency_report = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                shared_dependency_report = {"error": "shared dependency report could not be parsed"}
    manifest_project = config.target_unity_project.resolve() if config.copy_assets and config.target_unity_project else source_project
    shared_guid_map: dict[str, Path] = {}
    if config.copy_assets and config.copy_dependency_closure and config.dedupe_by == "sha256" and config.shared_dependency_store and manifest_project is not None:
        shared_root = (manifest_project / config.shared_dependency_store).resolve()
        if shared_root.is_dir():
            shared_guid_map = scan_guid_map(shared_root, manifest_project)
    files = iter_files(scan_root)
    asset_files = [p for p in files if p.suffix.lower() != ".meta"]
    if not asset_files:
        raise ValueError(f"source path has no ingestible asset files: {config.source_path}")
    selected_guid_map = scan_guid_map(scan_root, manifest_project)
    project_guid_map = {}
    if config.resolve_project_guids and source_project is not None:
        project_guid_map = source_project_guid_map
    markers = extract_text_markers(asset_files)
    role_counts = Counter(infer_role(path) for path in asset_files)
    dependencies = dependency_records(
        asset_files,
        scan_root,
        selected_guid_map,
        project_guid_map,
        manifest_project,
        source_project,
        ignored_dependency_guids,
        shared_guid_map,
    )
    output_dir = config.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    material_asset_files = material_paths_for_integrity(
        asset_files,
        dependencies,
        manifest_project,
        source_project,
        scan_root,
    )
    integrity_project = manifest_project
    integrity_guid_map = (
        scan_guid_map(integrity_project / "Assets", integrity_project)
        if integrity_project is not None
        else selected_guid_map
    )
    material_integrity = material_integrity_report(
        material_asset_files,
        integrity_guid_map,
        dependencies,
        integrity_project,
        scan_root,
    )
    shader_custom_editor = shader_custom_editor_report(
        shader_paths_for_integrity(
            asset_files,
            dependencies,
            manifest_project,
            source_project,
            scan_root,
        ),
        source_project,
        manifest_project,
        scan_root,
        config.shader_gui_policy_path.resolve() if config.shader_gui_policy_path else None,
        config.copy_shader_gui_dependencies,
        config.dry_run,
    )
    integrity_report = {
        "schema_version": "vfx_ingest_integrity_report.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_id": config.source_id,
        "material_integrity": material_integrity,
        "shader_custom_editor": shader_custom_editor,
    }
    integrity_report_path = output_dir / "ingest_integrity_report.json"
    run_id = f"{config.source_id.lower()}_r001"
    candidate_id = f"{config.source_id.lower()}_candidate_001"
    source_sample_name = "source_sample.json"
    derived_name = "derived_vfxspec.json"
    training_name = "training_example.json"
    texture_tag_index_path: Path | None = None
    texture_tag_index_source: str | None = None
    texture_tag_index_error: str | None = None
    texture_tag_index: dict[str, Any] = {"status": "unavailable", "record_count": 0}
    manifest = {
        "schema_version": "source_manifest.v1",
        "source_id": config.source_id,
        "title": config.title,
        "effect_family": config.effect_family,
        "source_kind": config.source_kind,
        "ingest_status": "blocked" if material_integrity["gate"]["status"] == "failed" else "parameters_extracted",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "unity_context": {
            "project_path": manifest_project.as_posix() if manifest_project else None,
            "unity_version": read_unity_version(manifest_project),
            "render_pipeline": "URP" if read_urp_version(manifest_project) else "unknown",
            "pipeline_version": read_urp_version(manifest_project),
            "package_snapshot_path": "Packages/manifest.json" if manifest_project else None,
            "scene_path": None,
            "original_project_path": source_project.as_posix() if source_project else None,
            "original_source_path": config.source_path.resolve().as_posix(),
            "copied_source_path": scan_root.as_posix() if config.copy_assets else None,
        },
        "license": {
            "status": config.license_status,
            "owner": "user-owned local project",
            "source_url": None,
            "evidence_path": None,
            "notes": "Local training/reference only until the user confirms redistribution or broader training rights.",
        },
        "root": {
            "path": scan_root.as_posix(),
            "storage_policy": "local_only" if config.copy_assets else "repo_metadata_only",
            "relative_to": "target_unity_project" if config.copy_assets else "source_unity_project",
        },
        "files": [
            file_record(path, manifest_project, scan_root, config.license_status, config.hash_files)
            for path in asset_files
        ],
        "dependencies": dependencies,
        "links": {
            "source_sample_path": source_sample_name,
            "derived_vfxspec_path": derived_name,
            "render_run_id": run_id,
            "render_manifest_path": f"../../../runs/{run_id}/run_manifest.json",
            "feedback_path": f"../../../runs/{run_id}/feedback.jsonl",
            "training_example_path": training_name,
            "beads_id": config.beads_id,
        },
        "extraction": {
            "dependency_index_path": None,
            "texture_tag_index_path": None,
            "texture_tag_index_status": texture_tag_index.get("status"),
            "texture_tag_index_record_count": texture_tag_index.get("record_count"),
            "texture_tag_index_source": texture_tag_index_source,
            "texture_tag_index_error": texture_tag_index_error,
            "parameter_snapshot_path": source_sample_name,
            "feature_manifest_path": None,
            "tool_version": "vfx_source_ingest.v2",
            "integrity_report_path": integrity_report_path.as_posix(),
            "material_integrity_gate": material_integrity["gate"]["status"],
            "shader_custom_editor_status_counts": shader_custom_editor["target_status_counts"],
            "shader_gui_policy_path": config.shader_gui_policy_path.as_posix() if config.shader_gui_policy_path else None,
            "copy_shader_gui_dependencies": config.copy_shader_gui_dependencies,
            "copy_dependency_closure": config.copy_dependency_closure,
            "shared_dependency_pool": shared_dependency_report,
            "shared_dependency_store": config.shared_dependency_store,
            "shared_index_path": config.shared_index_path.as_posix() if config.shared_index_path else None,
            "dedupe_by": config.dedupe_by,
            "rewrite_guid_references": config.rewrite_guid_references,
            "dry_run": config.dry_run,
            "include_script_dependencies": config.include_script_dependencies,
            "copyable_dependency_extensions": sorted(COPYABLE_DEPENDENCY_EXTENSIONS),
            "guid_cache": guid_cache_summary,
        },
        "notes": [
            "Generated by workspace.tools.vfx_source_ingest.",
            "Source files are context for training, not visual success evidence.",
        ],
    }
    selected_file_paths = [record["path"] for record in manifest["files"]]
    prefab_paths = [record["path"] for record in manifest["files"] if record["role"] == "prefab"]
    material_paths = [record["path"] for record in manifest["files"] if record["role"] == "material"]
    texture_paths = [record["path"] for record in manifest["files"] if record["role"] == "texture"]
    shader_paths = [
        record["path"]
        for record in manifest["files"]
        if record["role"] in {"shader", "shader_include", "shadergraph", "shadersubgraph"}
    ]
    texture_file_records = [record for record in manifest["files"] if record["role"] == "texture"]
    texture_tag_index_path = config.texture_tag_index_path
    texture_tag_index_source = "config" if texture_tag_index_path is not None else None
    texture_tag_index_error = None
    texture_tag_index = None
    if texture_tag_index_path is not None:
        texture_tag_index = load_texture_tag_index(texture_tag_index_path)
    elif texture_file_records:
        local_texture_tag_index_path = output_dir / "texture_tags.jsonl"
        try:
            texture_tag_index = build_local_texture_tag_index(
                texture_file_records,
                manifest_project,
                scan_root,
                local_texture_tag_index_path,
            )
        except Exception as exc:
            texture_tag_index = None
            texture_tag_index_error = f"{type(exc).__name__}: {exc}"
        else:
            texture_tag_index_path = local_texture_tag_index_path
            texture_tag_index_source = "generated_local"
    if texture_tag_index is None:
        if DEFAULT_TEXTURE_TAG_INDEX.exists():
            texture_tag_index_path = DEFAULT_TEXTURE_TAG_INDEX
            texture_tag_index = load_texture_tag_index(texture_tag_index_path)
            texture_tag_index_source = "default_global"
        else:
            texture_tag_index = load_texture_tag_index(None)
            texture_tag_index_source = "unavailable"
    manifest["extraction"].update(
        {
            "texture_tag_index_path": texture_tag_index_path.as_posix() if texture_tag_index_path else None,
            "texture_tag_index_status": texture_tag_index.get("status"),
            "texture_tag_index_record_count": texture_tag_index.get("record_count"),
            "texture_tag_index_source": texture_tag_index_source,
            "texture_tag_index_error": texture_tag_index_error,
        }
    )
    material_selection = material_selection_summary(
        material_paths=material_paths,
        texture_paths=texture_paths,
        shader_paths=shader_paths,
        dependencies=dependencies,
        texture_tag_index=texture_tag_index,
    )
    source_sample = {
        "schema_version": "source_sample.v1",
        "sample_id": f"sample_{config.source_id.lower()}",
        "source_id": config.source_id,
        "purpose": "source_to_vfxspec_seed",
        "readiness": "blocked" if material_integrity["gate"]["status"] == "failed" else "needs_render",
        "inputs": {
            "source_manifest_path": "source_manifest.json",
            "selected_files": selected_file_paths,
            "prompt_path": None,
            "manual_notes_path": None,
        },
        "extracted": {
            "effect_family": config.effect_family,
            "component_summary": {
                "files": len(asset_files),
                "dependencies": len(dependencies),
                "missing_dependencies": sum(1 for dep in dependencies if dep["status"] == "missing"),
                "resolved_shared_dependencies": sum(1 for dep in dependencies if dep["status"] == "resolved_shared"),
                "external_dependencies": sum(1 for dep in dependencies if dep["status"] == "external"),
                "ignored_dependencies": sum(1 for dep in dependencies if dep["status"] == "ignored"),
                "builtin_dependencies": sum(1 for dep in dependencies if dep["dependency_type"] == "unity_builtin"),
                "m_texture_slot_count": len(material_integrity["m_texture_slots"]),
                "m_texture_unresolved_count": sum(
                    1
                    for slot in material_integrity["m_texture_slots"]
                    if slot["status"] in {"missing", "wrong_asset_type"}
                ),
                "duplicate_material_guid_count": len(material_integrity["material_guid_duplicates"]),
                **{role: count for role, count in sorted(role_counts.items())},
                **{name: int(count) for name, count in sorted(markers.items())},
            },
            "layers": [
                {
                    "role": "source_prefab_set",
                    "source_files": prefab_paths,
                    "status": "candidate",
                    "observations": [
                        "Prefab structure was indexed, but visual layer roles require rendering and human review."
                    ],
                }
            ] if prefab_paths else [],
            "timing": {
                "duration_seconds": None,
                "peak_time_seconds": None,
                "source": "not_extracted"
            },
            "shape_parameters": {
                "prefab_count": len(prefab_paths),
                "mesh_count": role_counts.get("mesh", 0),
                "trail_renderer_count": markers.get("trail_renderers", 0),
                "line_renderer_count": markers.get("line_renderers", 0),
            },
            "material_parameters": {
                "material_count": len(material_paths),
                "texture_count": len(texture_paths),
                "shader_count": len(shader_paths),
                "source_materials": material_paths[:100],
                "source_textures": texture_paths[:100],
                "source_shaders": shader_paths[:100],
            },
            "material_selection": material_selection,
            "performance_hints": {
                "particle_system_count": markers.get("particle_systems", 0),
                "particle_renderer_count": markers.get("particle_renderers", 0),
                "overdraw_risk": "unknown_until_rendered",
                "draw_call_risk": "unknown_until_unity_profiled",
            },
        },
        "derived": {
            "vfxspec_path": derived_name,
            "render_run_id": run_id,
            "candidate_id": candidate_id,
            "training_example_path": training_name,
        },
        "evidence": {
            "capture_manifest_path": f"../../../runs/{run_id}/run_manifest.json",
            "contact_sheet_path": None,
            "render_paths": [],
            "human_feedback_path": f"../../../runs/{run_id}/feedback.jsonl",
            "quality_gate": {
                "unity_verified": None,
                "visual_reviewed": False,
                "license_checked": config.license_status not in {"unknown", "blocked"},
            },
        },
        "boundaries": [
            "Parsed source data is not a visual success signal.",
            "Render capture and human feedback are required before training.",
            "Large source assets remain local unless license status explicitly allows committing.",
        ],
    }
    derived_vfxspec = {
        "schema_version": "vfxspec.v1",
        "effect_family": config.effect_family,
        "effect_type": config.effect_family,
        "adapter": {
            "name": f"{config.effect_family}.source_ingest.seed",
            "version": "0.1.0",
            "generator_family": "source_to_candidate",
            "specialized_metrics": [
                "source_dependency_completeness",
                "render_readability",
                "layer_role_clarity",
                "material_parameter_reusability",
            ],
        },
        "prompt": f"Derive a {config.effect_family} VFX candidate from Unity source files: {config.title}.",
        "negative_prompt": "Do not treat source-file existence as visual success. Do not train without render evidence and human feedback.",
        "reference": {
            "source_id": config.source_id,
            "case_id": f"sample_{config.source_id.lower()}",
            "frames": [],
        },
        "generation": {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "seed": 1,
            "generator": "source_ingest_seed",
            "generator_version": "0.1.0",
            "parent_candidate_id": None,
        },
        "layers": [
            {
                "role": "source_prefab_set",
                "status": "active",
                "topology": "source_derived_unknown",
                "shape_parameters": {
                    "source_manifest_path": "source_manifest.json",
                    "prefab_count": len(prefab_paths),
                    "particle_system_count": markers.get("particle_systems", 0),
                },
                "material_parameters": {
                    "material_count": len(material_paths),
                    "texture_count": len(texture_paths),
                    "shader_count": len(shader_paths),
                    "material_selection": material_selection,
                },
                "timing_parameters": {
                    "duration_seconds": None,
                    "peak_time_seconds": None,
                },
                "constraints": [
                    "Must render before training.",
                    "Must preserve source/license trace.",
                ],
            }
        ],
        "render_plan": {
            "unity_project": manifest_project.as_posix() if manifest_project else None,
            "scene": "unassigned",
            "camera": "Main Camera",
            "resolution": "1280x720",
            "time_points_seconds": [0.0, 0.08, 0.16, 0.24, 0.4],
        },
    }
    training_example = {
        "schema_version": "training_example.v1",
        "example_id": f"train_{config.source_id.lower()}",
        "run_id": run_id,
        "candidate_id": candidate_id,
        "inputs": {
            "prompt": derived_vfxspec["prompt"],
            "negative_prompt": derived_vfxspec["negative_prompt"],
            "reference_frames": [],
            "spec_path": derived_name,
            "render_manifest_path": f"../../../runs/{run_id}/run_manifest.json",
            "source_manifest_path": "source_manifest.json",
            "source_sample_path": source_sample_name,
            "material_selection": material_selection,
        },
        "outputs": {
            "render_paths": [],
            "features_path": None,
        },
        "label": {
            "decision": "unlabeled",
            "rank": None,
            "accepted_parts": [],
            "rejected_parts": [],
            "next_mutation": [
                "Render the copied/source-indexed effect before assigning training labels."
            ],
        },
    }
    paths = {
        "source_manifest": output_dir / "source_manifest.json",
        "source_sample": output_dir / source_sample_name,
        "derived_vfxspec": output_dir / derived_name,
        "training_example": output_dir / training_name,
        "ingest_integrity_report": integrity_report_path,
    }
    for key, payload in [
        ("source_manifest", manifest),
        ("source_sample", source_sample),
        ("derived_vfxspec", derived_vfxspec),
        ("training_example", training_example),
        ("ingest_integrity_report", integrity_report),
    ]:
        paths[key].write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if material_integrity["gate"]["status"] == "failed":
        first_error = material_integrity["gate"]["errors"][0]
        raise ValueError(
            f"ingest integrity gate failed: {first_error}; report: {integrity_report_path.as_posix()}"
        )
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create Unity VFX source-ingestion manifests.")
    parser.add_argument("--source", type=Path, required=True, help="Unity asset file or directory to ingest")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--effect-family", required=True)
    parser.add_argument("--source-kind", default="unity_effect_package")
    parser.add_argument("--source-unity-project", type=Path)
    parser.add_argument("--target-unity-project", type=Path)
    parser.add_argument("--copy-under", default="Assets/VFXSourceIngest/Trains")
    parser.add_argument("--copy-name")
    parser.add_argument("--copy-assets", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--license-status", default="local_reference_only")
    parser.add_argument("--beads-id")
    parser.add_argument("--hash-files", action="store_true")
    parser.add_argument("--resolve-project-guids", action="store_true")
    parser.add_argument(
        "--texture-tag-index-path",
        type=Path,
        help="Optional texture-tag JSONL index used to attach shader/texture slot evidence to material selection.",
    )
    parser.add_argument(
        "--copy-dependency-closure",
        action="store_true",
        help="When copying, recursively copy VFX asset dependencies resolved by source-project GUIDs.",
    )
    parser.add_argument(
        "--include-script-dependencies",
        action="store_true",
        help="Also copy script/assembly dependencies. Disabled by default to avoid compile failures.",
    )
    parser.add_argument("--max-dependency-depth", type=int, default=32)
    parser.add_argument(
        "--project-guid-cache",
        type=Path,
        default=None,
        help="Optional reusable cache for source-project GUID-to-asset mappings.",
    )
    parser.add_argument(
        "--shared-dependency-store",
        default=None,
        help="Target-project Assets-relative shared dependency directory, e.g. Assets/VFXSourceIngest/Shared.",
    )
    parser.add_argument(
        "--shared-index",
        type=Path,
        default=None,
        help="Optional target-project path for the shared SHA-256 dependency index.",
    )
    parser.add_argument("--dedupe-by", choices=["none", "sha256"], default="none")
    parser.add_argument(
        "--rewrite-guid-references",
        action="store_true",
        help="Rewrite copied YAML GUID references to canonical shared dependency GUIDs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan shared dependency reuse and GUID rewrites without copying or modifying target assets.",
    )
    parser.add_argument(
        "--shader-gui-policy",
        type=Path,
        default=None,
        help="JSON policy that explicitly allows licensed ShaderGUI dependency copies by CustomEditor class name.",
    )
    parser.add_argument(
        "--copy-shader-gui-dependencies",
        action="store_true",
        help="Copy only ShaderGUI dependencies explicitly allowed by --shader-gui-policy; otherwise record needs_manual_dependency.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = IngestConfig(
        source_path=args.source,
        output_dir=args.output_dir,
        source_id=args.source_id,
        title=args.title,
        effect_family=args.effect_family,
        source_kind=args.source_kind,
        source_unity_project=args.source_unity_project,
        target_unity_project=args.target_unity_project,
        copy_under=args.copy_under,
        copy_name=args.copy_name,
        copy_assets=args.copy_assets,
        overwrite=args.overwrite,
        license_status=args.license_status,
        beads_id=args.beads_id,
        hash_files=args.hash_files,
        resolve_project_guids=args.resolve_project_guids,
        texture_tag_index_path=args.texture_tag_index_path,
        copy_dependency_closure=args.copy_dependency_closure,
        include_script_dependencies=args.include_script_dependencies,
        max_dependency_depth=args.max_dependency_depth,
        shared_dependency_store=args.shared_dependency_store,
        shared_index_path=args.shared_index,
        dedupe_by=args.dedupe_by,
        rewrite_guid_references=args.rewrite_guid_references,
        dry_run=args.dry_run,
        project_guid_cache=args.project_guid_cache,
        shader_gui_policy_path=args.shader_gui_policy,
        copy_shader_gui_dependencies=args.copy_shader_gui_dependencies,
    )
    paths = build_source_ingest(config)
    print(json.dumps({key: path.as_posix() for key, path in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
