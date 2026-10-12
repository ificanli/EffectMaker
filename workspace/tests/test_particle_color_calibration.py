import unittest
import json
import tempfile
from pathlib import Path

import numpy as np

from workspace.tools.vfx_generation import particle_color_calibration as calibration


class ParticleColorCalibrationTests(unittest.TestCase):
    def test_roundtrip_requests_use_absolute_files_and_distinct_prefab_targets(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            graph = {'components': {'particle_systems': [{'parameters': {'color_over_lifetime_gradient': {'color_keys': [{'rgb': [1, 1, 1]}, {'rgb': [0, 0, 0]}]}}}]}}
            graph_path = root / 'graph.json'
            graph_path.write_text(json.dumps(graph), encoding='utf-8')
            prefab = 'Assets/Generated/ArbitraryRoot/tutorial_fixed/GeneratedRoot.prefab'
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'cases': [{'case_id': 'tutorial_fixed', 'prefab_path': prefab, 'graph_path': str(graph_path)}]}), encoding='utf-8')
            (root / 'render_requests.json').write_text(json.dumps({'requests': [{'candidate_id': 'tutorial_fixed'}]}), encoding='utf-8')
            result = calibration.prepare_evidence_checks(manifest.relative_to(Path.cwd()))
            request = json.loads(result.read_text(encoding='utf-8'))['requests'][0]
            self.assertTrue(Path(request['graph_path']).is_absolute())
            self.assertTrue(Path(request['report_path']).is_absolute())
            target = json.loads((root / 'source_recompile_request.json').read_text(encoding='utf-8'))['requests'][0]['output_prefab_path']
            self.assertNotEqual(target, prefab)
            self.assertIn('/SourceRoundtrip/', target)

    def test_visible_black_is_distinct_from_transparent_background(self) -> None:
        self.assertTrue(hasattr(calibration, 'signed_pixel_counts'))
        clear = np.full((16, 16, 3), 128, dtype=np.uint8)
        black = clear.copy()
        black[6:10, 6:10] = 0
        self.assertEqual(calibration.signed_pixel_counts(clear), (0, 0))
        self.assertEqual(calibration.signed_pixel_counts(black), (0, 16))

    def test_bright_foreground_is_not_a_black_phase(self) -> None:
        self.assertTrue(hasattr(calibration, 'signed_pixel_counts'))
        bright = np.full((16, 16, 3), 128, dtype=np.uint8)
        bright[6:10, 6:10] = 255
        self.assertEqual(calibration.signed_pixel_counts(bright), (16, 0))

    def test_error_or_incomplete_capture_cannot_pass_color_calibration(self) -> None:
        self.assertTrue(hasattr(calibration, 'capture_is_usable'))
        good = {'image_sequence_eligible': True, 'material_error_frames': 0, 'valid_frame_count': 5, 'decoded_frame_count': 5, 'declared_frame_count': 5}
        self.assertTrue(calibration.capture_is_usable(good))
        for override in ({'material_error_frames': 1}, {'image_sequence_eligible': False}, {'decoded_frame_count': 4}, {'valid_frame_count': 0}):
            self.assertFalse(calibration.capture_is_usable({**good, **override}))
