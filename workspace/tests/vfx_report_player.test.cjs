const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const player = require('../vfx_guide_assets/report_player.js');

const manifestPath = path.resolve(__dirname,
  '../data/vfx_generation/generated/tutorial_lightning_fixed_color_r003/tutorial_fixed/capture_manifest.json');
const readManifest = () => JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

test('uses real capture timestamps and relative frame filenames, never the Windows capture root', () => {
  const frames = player.readFrames(readManifest());
  assert.equal(frames.length, 41);
  assert.equal(frames[0].time, 0);
  assert.equal(frames[0].path, 'frame_000_0_000.png');
  assert.ok(Math.abs(frames.at(-1).time - 0.4) < 1e-6);
});

test('rejects missing, invalid, unverified, and out-of-order evidence without silently dropping frames', () => {
  const mutations = [
    m => { m.frames = []; },
    m => { m.render_pipeline_verified = false; },
    m => { m.capture_mode = 'synthetic'; },
    m => { m.frames[3].valid = false; },
    m => { m.frames[3].capture_time_seconds = -1; },
    m => { m.frames[3].capture_time_seconds = 0; },
    m => { m.frames[3].path = '../secret.png'; },
    m => { m.frames[3].path = 'https://example.com/frame.png'; },
  ];
  for (const mutate of mutations) {
    const manifest = readManifest();
    mutate(manifest);
    assert.throws(() => player.readFrames(manifest));
  }
});

test('frame selection follows nonuniform capture times and clamps to either end', () => {
  const frames = [{time: 0}, {time: 0.01}, {time: 0.06}, {time: 0.4}];
  assert.equal(player.frameAtTime(frames, -1), 0);
  assert.equal(player.frameAtTime(frames, 0.04), 1);
  assert.equal(player.frameAtTime(frames, 0.06), 2);
  assert.equal(player.frameAtTime(frames, 3), 3);
});

test('quarter speed changes wall time only, not displayed capture time', () => {
  const state = player.advancePlayback(0, 0.4, 0.25, 0.4, false);
  assert.equal(state.time, 0.1);
  assert.equal(state.ended, false);
});

test('normal playback stops on the final evidence frame; only explicit looping wraps', () => {
  assert.deepEqual(player.advancePlayback(0.3, 1, 1, 0.4, false), {time: 0.4, ended: true});
  const looped = player.advancePlayback(0.3, 0.2, 1, 0.4, true);
  assert.ok(Math.abs(looped.time - 0.1) < 1e-9);
  assert.equal(looped.ended, false);
});

test('report routes are isolated and every original architecture deep link still resolves', () => {
  assert.equal(player.viewForHash(''), 'report');
  assert.equal(player.viewForHash('#report-case'), 'report');
  assert.equal(player.viewForHash('#report-next'), 'report');
  for (const id of ['architecture', 'start', 'flow', 'spec', 'evidence', 'inputs',
    'tools', 'roles', 'automation', 'transfer', 'status', 'next']) {
    assert.equal(player.viewForHash('#' + id), 'architecture');
  }
  assert.equal(player.viewForHash('#missing'), 'report');
});

test('all three replay variants reference existing evidence, not an invented animation', () => {
  for (const caseId of ['tutorial_fixed', 'tutorial_blend_control', 'alpha_only_control']) {
    const folder = path.resolve(path.dirname(manifestPath), '..', caseId);
    const manifest = JSON.parse(fs.readFileSync(path.join(folder, 'capture_manifest.json'), 'utf8'));
    for (const frame of player.readFrames(manifest)) {
      assert.ok(fs.existsSync(path.join(folder, 'captures', frame.path)), frame.path);
    }
  }
});
