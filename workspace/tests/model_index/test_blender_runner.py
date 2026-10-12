import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from workspace.tools.model_index.blender_runner import run_blender


class RunnerTests(unittest.TestCase):
    def test_parses_marked_json(self):
        with tempfile.TemporaryDirectory() as temp:
            asset, previews = Path(temp) / "a.obj", Path(temp) / "previews"
            asset.write_text("o a")

            def communicate(timeout):
                staged = Path(run.call_args.args[0][-2])
                paths = {}
                for view in ("front", "side", "perspective"):
                    path = staged / f"abc-{view}.png"
                    image = Image.new("RGB", (2, 2), "white")
                    image.putpixel((0, 0), (0, 0, 0))
                    image.save(path)
                    paths[view] = str(path)
                return 'MODEL_INDEX_RESULT:' + json.dumps({"vertex_count": 2, "previews": paths}) + '\n', ""

            process = type("Proc", (), {"returncode": 0, "communicate": Mock(side_effect=communicate)})()
            with patch("workspace.tools.model_index.blender_runner.subprocess.Popen", return_value=process) as run:
                result = run_blender(asset, previews, "blender", asset_id="abc")
        self.assertEqual(result["vertex_count"], 2)
        command = run.call_args.args[0]
        self.assertEqual(command[0], "blender")
        self.assertIn("--background", command)
        self.assertEqual(command[-1], "abc")
        self.assertEqual(Path(command[-2]).parent, previews)
        self.assertTrue(Path(command[-2]).name.startswith(".abc.tmp-"))

    def test_success_atomically_publishes_complete_preview_set(self):
        with tempfile.TemporaryDirectory() as temp:
            asset, previews = Path(temp) / "a.obj", Path(temp) / "previews"
            asset.write_text("o a")

            def communicate(timeout):
                command = run.call_args.args[0]
                staged = Path(command[-2])
                for index, view in enumerate(("front", "side", "perspective")):
                    image = Image.new("RGB", (2, 2), "white")
                    image.putpixel((index % 2, index // 2), (0, 0, 0))
                    image.save(staged / f"abc-{view}.png")
                payload = {"previews": {view: str(staged / f"abc-{view}.png")
                                        for view in ("front", "side", "perspective")}}
                return "MODEL_INDEX_RESULT:" + json.dumps(payload), ""

            process = type("Proc", (), {"returncode": 0, "communicate": Mock(side_effect=communicate)})()
            with patch("workspace.tools.model_index.blender_runner.subprocess.Popen", return_value=process) as run:
                result = run_blender(asset, previews, "blender", asset_id="abc")
            published = previews / "abc"
            self.assertTrue(published.is_dir())
            self.assertEqual(set(result["previews"]), {"front", "side", "perspective"})
            self.assertTrue(all(Path(path).parent == published for path in result["previews"].values()))
            self.assertEqual(list(previews.glob(".abc.tmp-*")), [])

    def test_timeout_cleans_staged_previews_without_replacing_published(self):
        with tempfile.TemporaryDirectory() as temp:
            previews = Path(temp) / "previews"
            published = previews / "abc"
            published.mkdir(parents=True)
            marker = published / "old.png"
            marker.write_bytes(b"old")
            proc = type("Proc", (), {"terminate": Mock(), "kill": Mock(), "wait": Mock()})()
            proc.communicate = Mock(side_effect=subprocess.TimeoutExpired(["blender"], 1))
            with patch("workspace.tools.model_index.blender_runner.subprocess.Popen", return_value=proc):
                with self.assertRaises(TimeoutError):
                    run_blender(Path("a.obj"), previews, timeout=1, asset_id="abc")
            self.assertEqual(marker.read_bytes(), b"old")
            self.assertEqual(list(previews.glob(".abc.tmp-*")), [])

    def test_timeout_is_terminated(self):
        proc = type("Proc", (), {"terminate": Mock(), "kill": Mock(), "wait": Mock()})()
        proc.communicate = Mock(side_effect=subprocess.TimeoutExpired(["blender"], 1))
        with patch("workspace.tools.model_index.blender_runner.subprocess.Popen", return_value=proc):
            with self.assertRaises(TimeoutError):
                run_blender(Path("a.obj"), Path("p"), timeout=1, asset_id="a")
        proc.terminate.assert_called_once()

    def test_missing_marker_preserves_blender_diagnostics(self):
        process = subprocess.CompletedProcess([], 0, "Blender stdout diagnostic", "Error: Version 6100 unsupported")
        process.communicate = Mock(return_value=(process.stdout, process.stderr))
        with patch("workspace.tools.model_index.blender_runner.subprocess.Popen", return_value=process):
            with self.assertRaisesRegex(RuntimeError, "Version 6100 unsupported"):
                run_blender(Path("a.obj"), Path("p"), asset_id="a")

    def test_nonzero_exit_is_error(self):
        process = subprocess.CompletedProcess([], 1, "", "bad")
        process.communicate = Mock(return_value=("", "bad"))
        process.wait = Mock()
        with patch("workspace.tools.model_index.blender_runner.subprocess.Popen", return_value=process):
            with self.assertRaises(RuntimeError):
                run_blender(Path("a.obj"), Path("p"), asset_id="a")


if __name__ == "__main__":
    unittest.main()
