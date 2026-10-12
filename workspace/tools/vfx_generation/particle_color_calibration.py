"""Prepare fixed-asset legacy/independent color controls and tutorial layer probes."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image, ImageDraw

from .prefab_graph import assign_graph_id
from .prompt_execution_regression import _capture_metrics
from .procedure_prefab_graph import build_procedure_execution


NEUTRAL_MATERIAL = 'Assets/Generated/ParticleColorCalibrationAssetsR001/NeutralUrpParticles.mat'


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def neutral_gradient(fade: bool) -> dict:
    return {'mode': 'Blend', 'color_keys': [{'time': 0.0, 'rgb': [1.0] * 3}, {'time': 1.0, 'rgb': [1.0] * 3}],
            'alpha_keys': [{'time': 0.0, 'alpha': 1.0}, {'time': 1.0, 'alpha': 0.0 if fade else 1.0}]}


def single_layer(graph: dict, role: str) -> dict:
    keep = {node['node_id'] for node in graph['nodes'] if node['role'] in {'root', role}}
    graph['nodes'] = [node for node in graph['nodes'] if node['node_id'] in keep]
    for node in graph['nodes']:
        if node['role'] != 'root':
            node['sibling_index'] = 0
            node['hierarchy_path'] = f"GeneratedRoot[0]/{node['name']}[0]"
    for key in ('particle_systems', 'renderers'):
        graph['components'][key] = [row for row in graph['components'][key] if row['node_id'] in keep]
    return graph


def prepare(source: Path, output: Path, asset_root: str) -> Path:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(output)
    original = json.loads(source.read_text(encoding='utf-8'))
    variants = []
    for color_name, rgb in {'white': [1.0, 1.0, 1.0], 'gray': [0.5, 0.5, 0.5], 'blue': [0.18, 0.5, 1.0]}.items():
        for mode in ('legacy', 'independent'):
            graph = single_layer(copy.deepcopy(original), 'core')
            p = graph['components']['particle_systems'][0]['parameters']
            p.pop('material_color_mode', None)
            p.pop('color_over_lifetime_gradient', None)
            p.update(start_color_rgba=rgb + [1.0], end_color_rgba=rgb + [1.0],
                     start_delay_max=0.0, start_lifetime_max=0.25, duration_seconds=0.3,
                     start_rotation_max=0.0, start_size_x_max=2.0, start_size_y_max=2.0,
                     material_template_path=NEUTRAL_MATERIAL, texture_asset_path=None, texture_property_name=None)
            if mode == 'independent':
                p.update(material_color_mode='preserve_template', color_over_lifetime_gradient=neutral_gradient(False), end_color_rgba=[1.0] * 4)
            variants.append((f'{color_name}_{mode}', graph))
    for name in ('lightning_legacy_qfx', 'lightning_independent_qfx', 'lightning_independent_urp', 'lightning_core_only', 'lightning_support_only'):
        graph = copy.deepcopy(original)
        for p in (row['parameters'] for row in graph['components']['particle_systems']):
            p.pop('material_color_mode', None)
            p.pop('color_over_lifetime_gradient', None)
            if name != 'lightning_legacy_qfx':
                p.update(material_color_mode='preserve_template', color_over_lifetime_gradient=neutral_gradient(True), end_color_rgba=[1.0, 1.0, 1.0, 0.0])
            if name not in ('lightning_legacy_qfx', 'lightning_independent_qfx'):
                p.update(material_template_path=NEUTRAL_MATERIAL, texture_property_name='_BaseMap')
        if name.endswith('_only'):
            single_layer(graph, 'core' if name == 'lightning_core_only' else 'support')
        variants.append((name, graph))
    return write_batch(variants, output, asset_root, {'source_graph': str(source.resolve())})


def prepare_tutorial(procedure_path: Path, output: Path, asset_root: str, prompt: str) -> Path:
    spec = json.loads(procedure_path.read_text(encoding='utf-8'))
    graph, controls = build_procedure_execution(spec, prompt, 'lightning', 20260907)
    for row in graph['components']['particle_systems']:
        row['parameters'].update(material_template_path=NEUTRAL_MATERIAL,
                                 texture_asset_path='Assets/Epic Toon FX/Textures/lightning1.png', texture_property_name='_BaseMap')
    fixed = copy.deepcopy(graph)
    blend = copy.deepcopy(graph)
    for row in blend['components']['particle_systems']:
        row['parameters']['color_over_lifetime_gradient']['mode'] = 'Blend'
    transparent = copy.deepcopy(graph)
    for row in transparent['components']['particle_systems']:
        gradient = row['parameters']['color_over_lifetime_gradient']
        gradient['alpha_keys'] = [{'time': key['time'], 'alpha': key['rgb'][0]} for key in gradient['color_keys']]
        gradient['color_keys'] = [{'time': 0.0, 'rgb': [1.0] * 3}, {'time': 1.0, 'rgb': [1.0] * 3}]
        row['parameters']['end_color_rgba'] = [1.0] * 4
    manifest = write_batch([('tutorial_fixed', fixed), ('tutorial_blend_control', blend), ('alpha_only_control', transparent)],
                       output.resolve(), asset_root, {'source_procedure': str(procedure_path.resolve()), 'prompt': prompt, 'execution_controls': controls,
                       'expected_initial_phase': 'bright',
                       'material_recipe': {'selection': 'explicit_calibrated_probe_not_automatic_asset_ranking', 'template': NEUTRAL_MATERIAL,
                                           'shader': 'Universal Render Pipeline/Particles/Unlit', 'reference_run': 'particle_color_calibration_r002'}},
                       background=[0.22, 0.22, 0.22, 1.0])
    write(output.resolve() / 'source_procedure_snapshot.json', spec)
    return manifest


def write_batch(variants: list[tuple[str, dict]], output: Path, asset_root: str, provenance: dict, background: list[float] | None = None) -> Path:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(output)
    cases, compiles, renders = [], [], []
    for name, graph in variants:
        graph['asset_bindings']['materials'] = sorted({row['parameters']['material_template_path'] for row in graph['components']['particle_systems']})
        graph['condition']['prompt'] = provenance.get('prompt', f'color calibration {name}; diagnostic only')
        graph['provenance']['source_run_id'] = output.name
        graph = assign_graph_id(graph)
        root = output / name
        graph_path = root / 'graph.json'
        prefab = f'{asset_root}/{name}/GeneratedRoot.prefab'
        write(graph_path, graph)
        cases.append({'case_id': name, 'prefab_path': prefab, 'graph_path': str(graph_path), 'compile_result_path': str(root / 'compile_result.json'),
                      'readback_result_path': str(root / 'readback_result.json'), 'readback_graph_path': str(root / 'readback.json'), 'capture_manifest_path': str(root / 'capture_manifest.json')})
        compiles.append({'graph_path': str(graph_path), 'output_prefab_path': prefab, 'result_path': str(root / 'compile_result.json')})
        renders.append({'candidate_id': name, 'random_seed_key': 'particle_color_calibration_20260907', 'prefab_path': prefab,
                        'capture_dir': str(root / 'captures'), 'capture_manifest_path': str(root / 'capture_manifest.json'), 'material_timeline_path': str(root / 'material_timeline.json'),
                        'source_script_fidelity': 'generated_graph_no_source_scripts', 'capture_category': 'lightning',
                        'force_orthographic': True, 'forced_camera_view': 'front', 'forced_orthographic_size': 3.2})
    manifest = output / 'calibration_manifest.json'
    write(manifest, {'run_id': output.name, **provenance, 'cases': cases,
                     'training_eligibility': {'controller_sft': False, 'positive_generation_supervision': False}})
    write(output / 'compile_request.json', {'requests': compiles})
    write(output / 'render_requests.json', {'schema_version': 'effectdemo_source_render_requests.v1', 'run_id': output.name,
          'scene': 'ParticleColorCalibration', 'camera': 'CalibrationCamera', 'width': 640, 'height': 480, 'background_color_rgba': background, 'sampling_mode': 'adaptive_runtime',
          'sampling': {'target_intervals': 24, 'short_effect_target_intervals': 24, 'min_interval_seconds': 0.005, 'max_interval_seconds': 0.01,
                       'max_duration_seconds': 0.4, 'include_zero': True, 'duration_sources': ['particle_system']}, 'requests': renders})
    return manifest


def finalize(manifest_path: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if 'source_procedure' in manifest:
        return finalize_tutorial(manifest_path)
    audit = json.loads((manifest_path.parent / 'color_api_audit.json').read_text(encoding='utf-8'))
    api_cases = {row['case_id']: row for row in audit['cases']}
    rows = {}
    for item in manifest['cases']:
        row = _capture_metrics(Path(item['capture_manifest_path']))
        capture = json.loads(Path(item['capture_manifest_path']).read_text(encoding='utf-8'))
        row['declared_frame_count'] = len(capture['frames'])
        row['decoded_frame_count'] = sum(frame['valid'] and (Path(capture['capture_root']) / frame['path']).is_file() for frame in capture['frames'])
        row['compile_pass'] = json.loads(Path(item['compile_result_path']).read_text(encoding='utf-8'))['status'] == 'pass'
        row['readback_pass'] = json.loads(Path(item['readback_result_path']).read_text(encoding='utf-8'))['status'] == 'pass'
        row['particles'] = api_cases[item['case_id']]['particles']
        rows[item['case_id']] = row
    products = {}
    for name in ('white', 'gray', 'blue'):
        for mode in ('legacy', 'independent'):
            particle = rows[f'{name}_{mode}']['particles'][0]
            tint = next(value['rgba'] for value in particle['material_colors'] if value['name'] == '_BaseColor')
            products[f'{name}_{mode}'] = [round(a * b, 6) for a, b in zip(particle['initial_vertex_color_product'], tint)]
    def close(left: list[float], right: list[float]) -> bool:
        return all(abs(a - b) < 0.0001 for a, b in zip(left, right))
    gates = {
        'compile_and_readback': all(row['compile_pass'] and row['readback_pass'] for row in rows.values()),
        'target_pipeline_verified': all(row['target_pipeline_match'] for row in rows.values()),
        'all_captures_usable': all(capture_is_usable(row) for row in rows.values()),
        'gray_legacy_cubed': close(products['gray_legacy'], [0.125, 0.125, 0.125, 1.0]),
        'gray_independent_applied_once': close(products['gray_independent'], [0.5, 0.5, 0.5, 1.0]),
        'blue_independent_applied_once': close(products['blue_independent'], [0.18, 0.5, 1.0, 1.0]),
        'white_identity_unchanged': close(products['white_legacy'], products['white_independent']),
        'gray_pixels_brighter': rows['gray_independent']['peak']['mean_foreground_rgb'][0] > rows['gray_legacy']['peak']['mean_foreground_rgb'][0] * 1.5,
        'urp_core_visible': rows['lightning_core_only']['peak']['visible_pixels'] > 64 and rows['lightning_core_only']['material_error_frames'] == 0,
    }
    sheet = Image.new('RGB', (1280, 510 * ((len(rows) + 1) // 2)), '#090b10')
    draw = ImageDraw.Draw(sheet)
    for index, (name, row) in enumerate(rows.items()):
        x, y = (index % 2) * 640, (index // 2) * 510
        if row['peak'].get('path'):
            with Image.open(row['peak']['path']) as image:
                sheet.paste(image.convert('RGB').resize((640, 480)), (x, y + 30))
        draw.text((x + 12, y + 8), name, fill='white')
    sheet.save(manifest_path.parent / 'contact_sheet.png')
    result = manifest_path.parent / 'calibration_report.json'
    write(result, {'run_id': manifest['run_id'], 'status': 'pass_color_execution_only' if all(gates.values()) else 'failed',
                  'unity_version': audit['unity_version'], 'color_space': audit['color_space'], 'gates': gates,
                  'initial_vertex_times_material_rgba': products, 'cases': rows,
                  'training_eligibility': manifest['training_eligibility'],
                  'limitations': ['Independent material/color calibration does not establish complete tutorial reproduction or professional quality.',
                                  'QFX template additionally reads TEXCOORD0.z, TEXCOORD1.xy, Noise and Emission inputs; Pos/Color/UV alone does not establish their fidelity.']})
    return result


def signed_pixel_counts(rgb: np.ndarray) -> tuple[int, int]:
    rgb = rgb.astype(np.float32)
    background = np.median(np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1])), axis=0)
    return int(((rgb - background).max(axis=2) > 16).sum()), int(((background - rgb).mean(axis=2) > 16).sum())


def capture_is_usable(row: dict) -> bool:
    count = row.get('valid_frame_count', 0)
    return bool(row.get('image_sequence_eligible')) and row.get('material_error_frames') == 0 and count > 0 and count == row.get('decoded_frame_count') == row.get('declared_frame_count')


def prepare_evidence_checks(manifest_path: Path) -> Path:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    output = manifest_path.parent
    requests, compiles, roundtrip_cases = [], [], []
    renders = json.loads((output / 'render_requests.json').read_text(encoding='utf-8'))
    for item in manifest['cases']:
        root = output / item['case_id'] / 'source_roundtrip'
        graph_path, report_path = root / 'source_graph.json', root / 'source_export_report.json'
        prefab = str(PurePosixPath(item['prefab_path']).parent.parent / 'SourceRoundtrip' / item['case_id'] / 'GeneratedRoot.prefab')
        requests.append({'candidate_id': item['case_id'], 'prefab_path': item['prefab_path'], 'graph_path': str(graph_path), 'report_path': str(report_path)})
        compiles.append({'graph_path': str(graph_path), 'output_prefab_path': prefab, 'result_path': str(root / 'compile_result.json')})
        roundtrip_cases.append({'case_id': item['case_id'], 'prefab_path': prefab, 'graph_path': str(graph_path),
                               'readback_graph_path': str(root / 'readback.json'), 'readback_result_path': str(root / 'readback_result.json')})
        for request in renders['requests']:
            if request['candidate_id'] == item['case_id']:
                request.update(prefab_path=prefab, capture_dir=str(root / 'captures'), capture_manifest_path=str(root / 'capture_manifest.json'), material_timeline_path=str(root / 'material_timeline.json'))
    write(output / 'source_export_request.json', {'schema_version': 'vfx_prefab_graph_source_export_requests.v1', 'source_dataset_id': 'generated_color_fidelity_probes_not_external_training_sources', 'requests': requests})
    write(output / 'source_recompile_request.json', {'requests': compiles})
    write(output / 'source_roundtrip_manifest.json', {'cases': roundtrip_cases})
    write(output / 'source_roundtrip_render_requests.json', renders)
    fixed = next(row for row in manifest['cases'] if row['case_id'] == 'tutorial_fixed')
    graph = json.loads(Path(fixed['graph_path']).read_text(encoding='utf-8'))
    graph['components']['particle_systems'][0]['parameters']['color_over_lifetime_gradient']['color_keys'][1]['rgb'] = [0.3, 0.4, 0.5]
    write(output / 'middle_key_negative_graph.json', assign_graph_id(graph))
    return output / 'source_export_request.json'


def finalize_tutorial(manifest_path: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    rows = {}
    sheet = Image.new('RGB', (1280, 150 * len(manifest['cases'])), '#242424')
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(manifest['cases']):
        capture = json.loads(Path(item['capture_manifest_path']).read_text(encoding='utf-8'))
        frames = []
        for frame in capture['frames']:
            if not frame['valid']:
                continue
            path = Path(capture['capture_root']) / frame['path']
            with Image.open(path) as image:
                bright, dark = signed_pixel_counts(np.asarray(image.convert('RGB')))
            frames.append({'time': frame['simulation_elapsed_seconds'], 'bright_pixels': bright, 'dark_pixels': dark, 'path': str(path)})
        phases = []
        for frame in frames:
            phase = 'black' if frame['dark_pixels'] > 64 and frame['bright_pixels'] < 64 else 'bright' if frame['bright_pixels'] > 64 else 'background'
            if not phases or phases[-1] != phase:
                phases.append(phase)
        rows[item['case_id']] = {'pipeline_verified': capture['render_pipeline_verified'], 'pipeline_instance': capture['render_pipeline_instance_type'],
                                'valid_frames': len(frames), 'max_dark_pixels': max((frame['dark_pixels'] for frame in frames), default=0), 'phases': phases,
                                'capture_usable': capture_is_usable({'image_sequence_eligible': capture.get('image_sequence_training_eligible', False),
                                    'material_error_frames': capture.get('material_render_error_frame_count'), 'valid_frame_count': capture.get('valid_frame_count'),
                                    'decoded_frame_count': len(frames), 'declared_frame_count': len(capture['frames'])}),
                                'frames': frames, 'compile_pass': json.loads(Path(item['compile_result_path']).read_text(encoding='utf-8'))['status'] == 'pass',
                                'readback_pass': json.loads(Path(item['readback_result_path']).read_text(encoding='utf-8'))['status'] == 'pass'}
        for column, target in enumerate([0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.24, 0.30]):
            frame = min(frames, key=lambda value: abs(value['time'] - target))
            with Image.open(frame['path']) as image:
                sheet.paste(image.convert('RGB').resize((160, 120)), (column * 160, index * 150 + 30))
            draw.text((column * 160 + 5, index * 150 + 17), f"{frame['time']:.3f}s", fill='white')
        draw.text((5, index * 150 + 2), item['case_id'], fill='white')
    fixed = rows['tutorial_fixed']
    phases = fixed['phases']
    gates = {'compile_and_readback': all(row['compile_pass'] and row['readback_pass'] for row in rows.values()),
             'all_captures_usable': all(row['capture_usable'] for row in rows.values()),
             'actual_urp': all(row['pipeline_verified'] and row['pipeline_instance'] == 'UnityEngine.Rendering.Universal.UniversalRenderPipeline' for row in rows.values()),
             'fixed_has_visible_black': fixed['max_dark_pixels'] > 64,
             'alpha_only_does_not_create_black': rows['alpha_only_control']['max_dark_pixels'] < 16,
             'bright_black_bright': any(phases[i:i + 3] == ['bright', 'black', 'bright'] for i in range(len(phases) - 2))}
    if manifest.get('expected_initial_phase') == 'bright':
        gates['starts_bright'] = bool(phases) and phases[0] == 'bright'
    sheet.save(manifest_path.parent / 'temporal_contact_sheet.png')
    result = manifest_path.parent / 'tutorial_color_report.json'
    write(result, {'run_id': manifest['run_id'], 'status': 'pass_tutorial_color_mechanism_only' if all(gates.values()) else 'failed',
                  'gates': gates, 'cases': rows, 'training_eligibility': manifest['training_eligibility'],
                  'limits': ['Key times, alpha values, placement and Billboard mapping are engineering hypotheses, not recovered source settings.',
                             'Source Stretched Billboard, multi-emission context, original texture authoring and qi Mask are not fully reproduced.',
                             'Explicit calibrated URP template is not an automatic asset-ranking result.']})
    return result


def compare_roundtrip(manifest_path: Path) -> Path:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    rows = []
    for item in manifest['cases']:
        root = manifest_path.parent / item['case_id'] / 'source_roundtrip'
        source = json.loads((root / 'source_export_report.json').read_text(encoding='utf-8'))
        compiled = json.loads((root / 'compile_result.json').read_text(encoding='utf-8'))
        readback = json.loads((root / 'readback_result.json').read_text(encoding='utf-8'))
        original = json.loads(Path(item['capture_manifest_path']).read_text(encoding='utf-8'))
        replay = json.loads((root / 'capture_manifest.json').read_text(encoding='utf-8'))
        differences = []
        schedule_matches = len(original['frames']) == len(replay['frames'])
        for before, after in zip(original['frames'], replay['frames']):
            schedule_matches &= abs(before['simulation_elapsed_seconds'] - after['simulation_elapsed_seconds']) < 0.0001
            with Image.open(Path(original['capture_root']) / before['path']) as a, Image.open(Path(replay['capture_root']) / after['path']) as b:
                diff = np.abs(np.asarray(a.convert('RGBA'), dtype=np.int16) - np.asarray(b.convert('RGBA'), dtype=np.int16))
                differences.append({'maximum_channel_difference': int(diff.max()), 'mean_absolute_difference': float(diff.mean())})
        gates = {
            'source_export': source['status'] == 'pass' and source['reconstruction_status'] == 'reconstructable',
            'source_recompile': compiled['status'] == 'pass',
            'source_readback': readback['status'] == 'pass' and not readback['differences'],
            'same_simulation_schedule': bool(schedule_matches),
            'actual_urp': original.get('render_pipeline_verified') is True and replay.get('render_pipeline_verified') is True
                and original.get('render_pipeline_instance_type') == replay.get('render_pipeline_instance_type') == 'UnityEngine.Rendering.Universal.UniversalRenderPipeline',
            'valid_frames': all(frame['valid'] for frame in original['frames'] + replay['frames']),
            'pixel_identical': bool(differences) and all(row['maximum_channel_difference'] == 0 for row in differences),
        }
        rows.append({'case_id': item['case_id'], 'gates': gates, 'compared_frame_count': len(differences),
                     'maximum_channel_difference': max((row['maximum_channel_difference'] for row in differences), default=None),
                     'maximum_mean_absolute_difference': max((row['mean_absolute_difference'] for row in differences), default=None)})
    result = manifest_path.parent / 'source_roundtrip_pixel_report.json'
    write(result, {'scope': 'generated_color_probe_source_roundtrip_not_external_prefab_generalization',
                  'status': 'pass' if all(all(row['gates'].values()) for row in rows) else 'failed', 'cases': rows,
                  'training_eligibility': {'controller_sft': False, 'positive_generation_supervision': False}})
    return result


def prepare_repeatability(manifest_path: Path) -> Path:
    root = manifest_path.resolve().parent
    request = json.loads((root / 'render_requests.json').read_text(encoding='utf-8'))
    original = next(row for row in request['requests'] if row['candidate_id'] == 'tutorial_blend_control')
    replay_request = json.loads((root / 'source_roundtrip_render_requests.json').read_text(encoding='utf-8'))
    replay = next(row for row in replay_request['requests'] if row['candidate_id'] == 'tutorial_blend_control')
    request['requests'] = []
    for name, source in [('original_a', original), ('original_b', original), ('source_recompiled', replay)]:
        row = copy.deepcopy(source)
        directory = root / 'repeatability' / name
        row.update(candidate_id=name, capture_dir=str(directory / 'captures'), capture_manifest_path=str(directory / 'capture_manifest.json'), material_timeline_path=str(directory / 'material_timeline.json'))
        request['requests'].append(row)
    path = root / 'repeatability_render_requests.json'
    write(path, request)
    return path


def finalize_repeatability(manifest_path: Path) -> Path:
    root = manifest_path.resolve().parent
    captures = {name: json.loads((root / 'repeatability' / name / 'capture_manifest.json').read_text(encoding='utf-8'))
                for name in ('original_a', 'original_b', 'source_recompiled')}
    captures['previous_original'] = json.loads((root / 'tutorial_blend_control/capture_manifest.json').read_text(encoding='utf-8'))
    rows = []
    for left, right in [('original_a', 'original_b'), ('original_a', 'source_recompiled'), ('original_b', 'source_recompiled'), ('previous_original', 'original_a')]:
        a, b = captures[left], captures[right]
        maxima, means = [], []
        for fa, fb in zip(a['frames'], b['frames']):
            with Image.open(Path(a['capture_root']) / fa['path']) as ia, Image.open(Path(b['capture_root']) / fb['path']) as ib:
                delta = np.abs(np.asarray(ia.convert('RGBA'), dtype=np.int16) - np.asarray(ib.convert('RGBA'), dtype=np.int16))
                maxima.append(int(delta.max()))
                means.append(float(delta.mean()))
        rows.append({'left': left, 'right': right, 'compared_frames': len(maxima), 'maximum_channel_difference': max(maxima), 'maximum_mean_absolute_difference': max(means)})
    path = root / 'repeatability_report.json'
    write(path, {'scope': 'blend_capture_repeatability_diagnostic', 'comparisons': rows, 'positive_training_eligible': False})
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-graph', type=Path)
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--asset-root')
    parser.add_argument('--finalize', type=Path)
    parser.add_argument('--finalize-tutorial', type=Path)
    parser.add_argument('--prepare-evidence-checks', type=Path)
    parser.add_argument('--compare-roundtrip', type=Path)
    parser.add_argument('--tutorial-procedure', type=Path)
    parser.add_argument('--prompt', default='风格化蓝白纵向闪电，持续0.3秒')
    args = parser.parse_args()
    if args.compare_roundtrip:
        print(compare_roundtrip(args.compare_roundtrip))
    elif args.prepare_evidence_checks:
        print(prepare_evidence_checks(args.prepare_evidence_checks))
    elif args.finalize_tutorial:
        print(finalize_tutorial(args.finalize_tutorial))
    elif args.finalize:
        print(finalize(args.finalize))
    elif args.tutorial_procedure and args.output_root and args.asset_root:
        print(prepare_tutorial(args.tutorial_procedure, args.output_root, args.asset_root, args.prompt))
    elif args.source_graph and args.output_root and args.asset_root:
        print(prepare(args.source_graph, args.output_root, args.asset_root))
    else:
        parser.error('Provide --finalize or all of --source-graph, --output-root and --asset-root.')


if __name__ == '__main__':
    main()
