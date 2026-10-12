(function (root) {
  'use strict';

  const architectureIds = new Set(['architecture', 'start', 'flow', 'spec', 'evidence',
    'inputs', 'tools', 'roles', 'automation', 'transfer', 'status', 'next']);

  function viewForHash(hash) {
    return architectureIds.has(hash.replace(/^#/, '')) ? 'architecture' : 'report';
  }

  function readFrames(manifest) {
    if (manifest.capture_mode !== 'play_mode_runtime' || manifest.render_pipeline_verified !== true) {
      throw new Error('捕获记录未通过真实运行管线校验');
    }
    if (!Array.isArray(manifest.frames) || !manifest.frames.length) {
      throw new Error('捕获记录没有帧');
    }
    let previousTime = -1;
    return manifest.frames.map(frame => {
      const time = frame.capture_time_seconds;
      if (frame.valid !== true || !Number.isFinite(time) || time < 0 || time <= previousTime ||
          typeof frame.path !== 'string' || !/^[a-zA-Z0-9_.-]+\.png$/.test(frame.path)) {
        throw new Error('捕获帧无效、时间顺序异常或图片路径不合法');
      }
      previousTime = time;
      return {time, path: frame.path};
    });
  }

  function frameAtTime(frames, time) {
    let low = 0;
    let high = frames.length - 1;
    while (low < high) {
      const middle = Math.ceil((low + high) / 2);
      if (frames[middle].time <= time) low = middle;
      else high = middle - 1;
    }
    return low;
  }

  function advancePlayback(time, delta, speed, duration, loop) {
    const next = time + delta * speed;
    if (next < duration) return {time: next, ended: false};
    return loop && duration > 0
      ? {time: next % duration, ended: false}
      : {time: duration, ended: true};
  }

  const api = {readFrames, frameAtTime, advancePlayback, viewForHash};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document === 'undefined') return;
  root.VfxReportPlayer = api;

  const report = document.getElementById('report');
  if (!report) return;
  const architecture = document.getElementById('architecture');
  const image = document.getElementById('report-frame');
  const player = document.getElementById('report-player');
  const status = document.getElementById('report-player-status');
  const playButton = document.getElementById('report-play');
  const playIcon = playButton.querySelector('img');
  const slider = document.getElementById('report-seek');
  const speed = document.getElementById('report-speed');
  const loop = document.getElementById('report-loop');
  const retry = document.getElementById('report-retry');
  const caseSelect = document.getElementById('report-case-select');
  const timeOutput = document.getElementById('report-time');
  const frameOutput = document.getElementById('report-frame-number');
  const controls = [...document.querySelectorAll('[data-replay-control]')];
  const previous = document.getElementById('report-previous');
  const next = document.getElementById('report-next-frame');
  const captureBase = 'data/vfx_generation/generated/tutorial_lightning_fixed_color_r003/';
  const variants = {
    tutorial_fixed: {title: '亮黑亮切换', note: '离散颜色键保留可见的黑色形体，0.3 秒寿命结束后消失。'},
    tutorial_blend_control: {title: '连续渐变', note: '使用相同颜色键的连续插值对照。跨次捕获仍有小幅像素差异，重复性待校准。'},
    alpha_only_control: {title: '透明度对照', note: '仅降低透明度时显露的是背景，不会产生黑色遮盖形体。'}
  };
  let frames = [];
  let loadedImages = [];
  let index = 0;
  let time = 0;
  let running = false;
  let requestId = 0;
  let requestController;
  let raf = 0;
  let clock = 0;

  function setPlaybackButton() {
    const label = running ? '暂停' : '播放';
    playButton.title = label;
    playButton.setAttribute('aria-label', label);
    playIcon.src = `vfx_guide_assets/icons/${running ? 'pause' : 'play'}.svg`;
  }

  function stop() {
    running = false;
    cancelAnimationFrame(raf);
    setPlaybackButton();
    if (player.dataset.state === 'ready') status.textContent = '已暂停';
  }

  function renderFrame(target) {
    index = Math.max(0, Math.min(frames.length - 1, target));
    const frame = frames[index];
    image.src = loadedImages[index].src;
    image.alt = `${variants[caseSelect.value].title}，Unity 实录 ${frame.time.toFixed(2)} 秒`;
    slider.value = index;
    slider.setAttribute('aria-valuetext', `${frame.time.toFixed(2)} 秒，第 ${index + 1} 帧`);
    timeOutput.textContent = `${frame.time.toFixed(2)} / ${frames.at(-1).time.toFixed(2)} 秒`;
    frameOutput.textContent = `${index + 1} / ${frames.length} 帧`;
    previous.disabled = index === 0;
    next.disabled = index === frames.length - 1;
  }

  function seek(target) {
    if (player.dataset.state !== 'ready') return;
    stop();
    renderFrame(target);
    time = frames[index].time;
  }

  function tick(now) {
    if (!running) return;
    const state = advancePlayback(time, (now - clock) / 1000, Number(speed.value), frames.at(-1).time, loop.checked);
    clock = now;
    time = state.time;
    renderFrame(frameAtTime(frames, time));
    if (state.ended) {
      stop();
      status.textContent = '播放结束';
    } else raf = requestAnimationFrame(tick);
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const item = new Image();
      const timer = setTimeout(() => {
        item.onload = item.onerror = null;
        reject(new Error('图片载入超时'));
      }, 15000);
      item.onload = () => { clearTimeout(timer); resolve(item); };
      item.onerror = () => { clearTimeout(timer); reject(new Error('图片载入失败')); };
      item.src = url;
    });
  }

  async function loadCase() {
    stop();
    const token = ++requestId;
    requestController?.abort();
    const controller = new AbortController();
    requestController = controller;
    const timeout = setTimeout(() => controller.abort(), 15000);
    const caseId = caseSelect.value;
    player.dataset.state = 'loading';
    player.setAttribute('aria-busy', 'true');
    image.hidden = true;
    retry.hidden = true;
    controls.forEach(control => { control.disabled = true; });
    status.textContent = '正在载入 Unity 实录';
    timeOutput.textContent = '载入中';
    frameOutput.textContent = '';
    document.getElementById('report-case-note').textContent = variants[caseId].note;
    document.getElementById('report-manifest-link').href = `${captureBase}${caseId}/capture_manifest.json`;
    const phaseNames = caseId === 'tutorial_fixed'
      ? ['起始', '黑形体', '再亮', '结束后']
      : ['起始', '变化阶段', '后续阶段', '结束后'];
    document.querySelectorAll('[data-report-time]').forEach((button, phaseIndex) => {
      button.textContent = `${Number(button.dataset.reportTime).toFixed(2)} 秒 · ${phaseNames[phaseIndex]}`;
    });
    try {
      const response = await fetch(`${captureBase}${caseId}/capture_manifest.json`, {
        cache: 'no-store', signal: controller.signal
      });
      if (!response.ok) throw new Error(`捕获记录请求失败（${response.status}）`);
      const nextFrames = readFrames(await response.json());
      clearTimeout(timeout);
      const images = await Promise.all(nextFrames.map(frame => loadImage(`${captureBase}${caseId}/captures/${frame.path}`)));
      if (token !== requestId) return;
      frames = nextFrames;
      loadedImages = images;
      slider.max = frames.length - 1;
      time = frames[0].time;
      controls.forEach(control => { control.disabled = false; });
      player.dataset.state = 'ready';
      image.hidden = false;
      renderFrame(0);
      status.textContent = '已暂停';
    } catch (error) {
      if (token !== requestId) return;
      player.dataset.state = 'error';
      status.textContent = `实录未载入：${error.message}。`;
      timeOutput.textContent = '暂无实录';
      retry.hidden = false;
    } finally {
      clearTimeout(timeout);
      if (token === requestId) player.setAttribute('aria-busy', 'false');
    }
  }

  playButton.addEventListener('click', () => {
    if (running) return stop();
    if (player.dataset.state !== 'ready') return;
    if (index === frames.length - 1) seek(0);
    running = true;
    clock = performance.now();
    status.textContent = '正在播放';
    setPlaybackButton();
    raf = requestAnimationFrame(tick);
  });
  previous.addEventListener('click', () => seek(index - 1));
  next.addEventListener('click', () => seek(index + 1));
  document.getElementById('report-reset').addEventListener('click', () => seek(0));
  slider.addEventListener('input', () => seek(Number(slider.value)));
  speed.addEventListener('change', () => { clock = performance.now(); });
  caseSelect.addEventListener('change', loadCase);
  retry.addEventListener('click', loadCase);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
  document.querySelectorAll('[data-report-time]').forEach(button => {
    button.addEventListener('click', () => seek(frameAtTime(frames, Number(button.dataset.reportTime))));
  });

  document.getElementById('report-copy').addEventListener('click', async () => {
    const path = document.getElementById('report-prefab-path').textContent.trim();
    const message = document.getElementById('report-copy-status');
    try {
      await navigator.clipboard.writeText(path);
      message.textContent = '已复制 Prefab 路径';
    } catch {
      message.textContent = '剪贴板不可用，Prefab 路径保留在下方';
    }
  });

  let wasArchitecture = false;
  function applyRoute() {
    const showArchitecture = viewForHash(location.hash) === 'architecture';
    report.hidden = showArchitecture;
    architecture.hidden = !showArchitecture;
    document.body.classList.toggle('report-mode', !showArchitecture);
    document.querySelectorAll('[data-guide-view]').forEach(link => {
      const selected = link.dataset.guideView === (showArchitecture ? 'architecture' : 'report');
      if (selected) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    if (showArchitecture) stop();
    const target = document.getElementById(location.hash.slice(1));
    requestAnimationFrame(() => {
      if (target && (showArchitecture ? architecture : report).contains(target)) {
        target.scrollIntoView({behavior: 'instant', block: 'start'});
      } else if (showArchitecture !== wasArchitecture || !location.hash) window.scrollTo(0, 0);
      wasArchitecture = showArchitecture;
    });
  }
  window.addEventListener('hashchange', applyRoute);
  applyRoute();
  loadCase();
})(typeof window !== 'undefined' ? window : globalThis);
