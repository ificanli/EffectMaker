import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from workspace.tools.resource_vectors.cli import main
from workspace.tools.resource_vectors.encoder import (
    ModelUnavailableError,
    TransformersClipEncoder,
    _feature_tensor,
)


class FakeEncoder:
    model_id = "test/fake-clip"
    revision = "local-test"

    def encode_images(self, paths):
        return np.asarray([
            [1.0, 0.0] if "red" in Path(path).name else [0.0, 1.0]
            for path in paths
        ], dtype=np.float32)

    def encode_text(self, text):
        return np.asarray([1.0, 0.0] if "red" in text else [0.0, 1.0], dtype=np.float32)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root = base / "resource"
        self.output = base / "vectors"
        self.root.mkdir()
        Image.new("RGB", (8, 8), "red").save(self.root / "red.png")
        Image.new("RGB", (8, 8), "blue").save(self.root / "blue.png")

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    @patch("workspace.tools.resource_vectors.cli.TransformersClipEncoder", return_value=FakeEncoder())
    def test_build_and_search_commands(self, _encoder):
        code, text, error = self.run_cli(
            "build-sample", "--root", str(self.root), "--output", str(self.output),
            "--limit", "64", "--json",
        )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(text)["count"], 2)
        self.assertTrue((self.output / "sample.jsonl").is_file())

        code, text, error = self.run_cli(
            "search-text", "red flame", "--output", str(self.output), "--json"
        )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(text)[0]["relative_path"], "red.png")

        code, text, error = self.run_cli(
            "search-image", "blue.png", "--root", str(self.root),
            "--output", str(self.output), "--json",
        )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(text)[0]["relative_path"], "blue.png")

    @patch("workspace.tools.resource_vectors.cli.TransformersClipEncoder", return_value=FakeEncoder())
    def test_build_all_uses_separate_resumable_output(self, _encoder):
        code, text, error = self.run_cli(
            "build-all", "--root", str(self.root), "--output", str(self.output),
            "--batch-size", "1", "--limit", "2", "--json",
        )
        self.assertEqual((code, error), (0, ""))
        summary = json.loads(text)
        self.assertEqual(summary["indexed"], 2)
        self.assertEqual(summary["batches"], 2)
        self.assertTrue((self.output / "progress.jsonl").is_file())
        self.assertTrue((self.output / "checkpoint" / "identity.json").is_file())

    def test_model_failure_is_clear_blocked_message_without_traceback(self):
        blocked = ModelUnavailableError(
            "model unavailable locally; rerun with --allow-model-download when network access is approved"
        )
        with patch("workspace.tools.resource_vectors.cli.TransformersClipEncoder", side_effect=blocked):
            code, _text, error = self.run_cli(
                "build-sample", "--root", str(self.root), "--output", str(self.output)
            )
        self.assertEqual(code, 3)
        self.assertTrue((self.output / "sample.jsonl").is_file())
        self.assertEqual(len((self.output / "sample.jsonl").read_text(encoding="utf-8").splitlines()), 2)
        self.assertIn("blocked:", error)
        self.assertIn("--allow-model-download", error)
        self.assertNotIn("Traceback", error)

    def test_feature_tensor_supports_transformers_model_output(self):
        tensor = __import__("torch").tensor([[1.0, 2.0]])

        class Output:
            pooler_output = tensor

        self.assertIs(_feature_tensor(Output()), tensor)
        self.assertIs(_feature_tensor(tensor), tensor)

    @patch("workspace.tools.resource_vectors.encoder.AutoProcessor.from_pretrained")
    @patch("workspace.tools.resource_vectors.encoder.AutoModel.from_pretrained")
    def test_model_loading_is_local_only_unless_download_is_explicit(self, model, processor):
        model.side_effect = OSError("not cached")
        with self.assertRaises(ModelUnavailableError):
            TransformersClipEncoder("openai/clip-vit-base-patch32")
        self.assertTrue(model.call_args.kwargs["local_files_only"])

        model.reset_mock(side_effect=True)
        model.return_value = model
        processor.return_value = processor
        TransformersClipEncoder("openai/clip-vit-base-patch32", allow_download=True)
        self.assertFalse(model.call_args.kwargs["local_files_only"])
        self.assertFalse(processor.call_args.kwargs["local_files_only"])


if __name__ == "__main__":
    unittest.main()
