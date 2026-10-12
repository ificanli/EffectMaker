from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from .blender_script import SCRIPT

DEFAULT_TIMEOUT = 300


def _valid_preview(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size == 0:
            return False
        with Image.open(path) as image:
            if image.format != "PNG":
                return False
            image.load()
            extrema = image.convert("RGB").getextrema()
            return any(low != high for low, high in extrema)
    except (OSError, ValueError):
        return False


def run_blender(asset: Path, preview_dir: Path, blender: str = "blender", *, timeout: int = DEFAULT_TIMEOUT,
                asset_id: str = "asset") -> dict:
    preview_dir.mkdir(parents=True, exist_ok=True)
    published_dir = preview_dir / asset_id
    staged_dir = Path(tempfile.mkdtemp(prefix=f".{asset_id}.tmp-", dir=preview_dir))
    try:
        with tempfile.TemporaryDirectory(prefix="model-index-") as temp:
            script = Path(temp) / "extract.py"
            script.write_text(SCRIPT, encoding="utf-8")
            command = [blender, "--background", "--factory-startup", "--python", str(script), "--",
                       str(asset), str(staged_dir), asset_id]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as error:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise TimeoutError(f"Blender timed out after {timeout}s") from error
        marker = "MODEL_INDEX_RESULT:"
        payload = next((line[len(marker):] for line in stdout.splitlines() if line.startswith(marker)), None)
        if process.returncode != 0:
            raise RuntimeError((stderr or stdout).strip() or f"Blender exit {process.returncode}")
        if payload is None:
            detail = "\n".join(part.strip() for part in (stderr, stdout) if part and part.strip())
            raise RuntimeError(detail or "Blender output did not contain MODEL_INDEX_RESULT")
        data = json.loads(payload)
        expected = {view: staged_dir / f"{asset_id}-{view}.png"
                    for view in ("front", "side", "perspective")}
        if not all(_valid_preview(path) for path in expected.values()):
            raise RuntimeError("Blender did not produce three valid nonblank PNG previews")
        backup = preview_dir / f".{asset_id}.old"
        if backup.exists():
            shutil.rmtree(backup)
        if published_dir.exists():
            os.replace(published_dir, backup)
        try:
            os.replace(staged_dir, published_dir)
        except Exception:
            if backup.exists() and not published_dir.exists():
                os.replace(backup, published_dir)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        data["previews"] = {view: str(published_dir / path.name) for view, path in expected.items()}
        return data
    finally:
        if staged_dir.exists():
            shutil.rmtree(staged_dir)
