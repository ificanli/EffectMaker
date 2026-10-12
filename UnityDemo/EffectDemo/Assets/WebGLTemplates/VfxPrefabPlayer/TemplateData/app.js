(function () {
  "use strict";

  var unityInstance = null;
  var catalog = [];
  var currentId = "";
  var runtime = { paused: false, speed: 1, elapsed: 0, liveParticles: 0, activeRenderers: 0, materialSlots: 0, webglMaterialStateChanges: 0 };
  var reviews = [];
  var pointerState = null;
  var query = new URLSearchParams(window.location.search);
  var embedMode = query.get("embed") === "1";
  var expectedParentOrigin = query.get("parentOrigin") || "";
  // An iframe's first parent message can race the Unity loader. Persist its intended
  // catalog item in the URL so the player can apply it after the catalog arrives.
  var requestedExternalSelectionId = query.get("catalogId") || "";

  function isAllowedReviewParent(origin) {
    if (!embedMode || !expectedParentOrigin || origin !== expectedParentOrigin) return false;
    try {
      var parent = new URL(expectedParentOrigin);
      return parent.protocol === window.location.protocol && parent.hostname === window.location.hostname;
    } catch (error) {
      return false;
    }
  }

  function applyExternalSelection() {
    if (!requestedExternalSelectionId || !unityInstance) return;
    var matched = catalog.some(function (entry) { return entry.id === requestedExternalSelectionId; });
    if (!matched) return;
    currentId = requestedExternalSelectionId;
    renderCatalog();
    renderDetails();
    send("SelectEffect", requestedExternalSelectionId);
    window.setTimeout(function () { send("FitView", ""); }, 320);
  }

  function reportExternalSelection() {
    if (!embedMode || !expectedParentOrigin || window.parent === window) return;
    window.parent.postMessage({ type: "vfx-web-selected", catalogId: currentId }, expectedParentOrigin);
  }

  var elements = {
    statusDot: document.querySelector("#status-dot"),
    statusLabel: document.querySelector("#status-label"),
    loadingOverlay: document.querySelector("#loading-overlay"),
    loadingPercent: document.querySelector("#loading-percent"),
    progressBar: document.querySelector("#progress-bar"),
    warningBanner: document.querySelector("#warning-banner"),
    catalogCount: document.querySelector("#catalog-count"),
    prefabList: document.querySelector("#prefab-list"),
    searchInput: document.querySelector("#search-input"),
    categorySelect: document.querySelector("#category-select"),
    effectName: document.querySelector("#effect-name"),
    effectCategory: document.querySelector("#effect-category"),
    effectPlayability: document.querySelector("#effect-playability"),
    effectParticleSystems: document.querySelector("#effect-particle-systems"),
    effectRenderers: document.querySelector("#effect-renderers"),
    effectDuration: document.querySelector("#effect-duration"),
    effectSpeed: document.querySelector("#effect-speed"),
    effectPath: document.querySelector("#effect-path"),
    effectSource: document.querySelector("#effect-source"),
    particleCount: document.querySelector("#particle-count"),
    rendererCount: document.querySelector("#renderer-count"),
    materialChangeCount: document.querySelector("#material-change-count"),
    elapsedTime: document.querySelector("#elapsed-time"),
    pauseButton: document.querySelector("#pause-button"),
    canvas: document.querySelector("#unity-canvas"),
    libraryPanel: document.querySelector("#library-panel"),
    trainingLinkStatus: document.querySelector("#training-link-status"),
    sourceScriptFidelity: document.querySelector("#source-script-fidelity"),
    trainingRunId: document.querySelector("#training-run-id"),
    trainingCandidateId: document.querySelector("#training-candidate-id"),
    trainingCaseId: document.querySelector("#training-case-id"),
    trainingMaterialChanges: document.querySelector("#training-material-changes"),
    materialKeyTimes: document.querySelector("#material-key-times"),
    reviewerInput: document.querySelector("#reviewer-input"),
    decisionSelect: document.querySelector("#decision-select"),
    dynamicQualityInput: document.querySelector("#dynamic-quality-input"),
    dynamicQualityOutput: document.querySelector("#dynamic-quality-output"),
    rhythmQualityInput: document.querySelector("#rhythm-quality-input"),
    rhythmQualityOutput: document.querySelector("#rhythm-quality-output"),
    styleMatchSelect: document.querySelector("#style-match-select"),
    reviewSummaryInput: document.querySelector("#review-summary-input"),
    saveReviewButton: document.querySelector("#save-review-button"),
    exportReviewsButton: document.querySelector("#export-reviews-button"),
    reviewCount: document.querySelector("#review-count"),
  };

  function refreshIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
      document.documentElement.classList.add("icons-ready");
    }
  }

  function setStatus(label, state) {
    elements.statusLabel.textContent = label;
    elements.statusDot.className = "status-dot is-" + state;
  }

  function send(method, value) {
    if (!unityInstance) {
      showBanner("Unity 运行时尚未就绪。", "warning");
      return;
    }
    unityInstance.SendMessage("VfxWebPlayer", method, value == null ? "" : String(value));
  }

  function currentEntry() {
    return catalog.find(function (entry) { return entry.id === currentId; }) || null;
  }

  function rebuildCategories() {
    var selected = elements.categorySelect.value;
    var categories = Array.from(new Set(catalog.map(function (entry) { return entry.category; }))).sort();
    elements.categorySelect.innerHTML = "";
    var all = document.createElement("option");
    all.value = "all";
    all.textContent = "全部";
    elements.categorySelect.appendChild(all);
    categories.forEach(function (category) {
      var option = document.createElement("option");
      option.value = category;
      option.textContent = category;
      elements.categorySelect.appendChild(option);
    });
    elements.categorySelect.value = categories.indexOf(selected) >= 0 ? selected : "all";
  }

  function renderCatalog() {
    var query = elements.searchInput.value.trim().toLowerCase();
    var category = elements.categorySelect.value;
    var filtered = catalog.filter(function (entry) {
      var matchesCategory = category === "all" || entry.category === category;
      var haystack = (entry.name + " " + entry.assetPath + " " + entry.sourcePath).toLowerCase();
      return matchesCategory && (!query || haystack.indexOf(query) >= 0);
    });

    elements.catalogCount.textContent = filtered.length + " / " + catalog.length + " 项";
    elements.prefabList.innerHTML = "";

    if (!filtered.length) {
      var empty = document.createElement("div");
      empty.className = "empty-list";
      empty.textContent = "没有匹配的 Prefab";
      elements.prefabList.appendChild(empty);
      return;
    }

    filtered.forEach(function (entry) {
      var row = document.createElement("button");
      row.type = "button";
      row.className = "prefab-row" + (entry.id === currentId ? " is-active" : "");
      row.setAttribute("role", "option");
      row.setAttribute("aria-selected", entry.id === currentId ? "true" : "false");

      var copy = document.createElement("span");
      var name = document.createElement("strong");
      name.textContent = entry.name;
      var meta = document.createElement("small");
      meta.textContent = entry.category + " · " + entry.rendererCount + " renderers";
      copy.appendChild(name);
      copy.appendChild(meta);

      var count = document.createElement("span");
      count.className = "row-count";
      count.textContent = entry.particleSystemCount + " PS";

      row.appendChild(copy);
      row.appendChild(count);
      row.addEventListener("click", function () {
        currentId = entry.id;
        renderCatalog();
        renderDetails();
        send("SelectEffect", entry.id);
        window.setTimeout(function () { send("FitView", ""); }, 320);
        elements.libraryPanel.classList.remove("is-open");
      });
      elements.prefabList.appendChild(row);
    });
  }

  function renderDetails() {
    var entry = currentEntry();
    if (!entry) return;

    elements.effectName.textContent = entry.name;
    elements.effectCategory.textContent = entry.category;
    elements.effectPlayability.textContent = entry.playability === "direct" ? "可直接播放" : "需要上下文";
    elements.effectPlayability.className = "badge status-badge " + (entry.playability === "direct" ? "is-direct" : "is-context");
    elements.effectParticleSystems.textContent = String(entry.particleSystemCount);
    elements.effectRenderers.textContent = String(entry.rendererCount);
    elements.effectDuration.textContent = Number(entry.suggestedDuration || 0).toFixed(1) + "s";
    elements.effectSpeed.textContent = Number(runtime.speed || 1).toFixed(runtime.speed % 1 ? 2 : 0) + "×";
    elements.effectPath.textContent = entry.assetPath || "-";
    elements.effectSource.textContent = entry.sourcePath || entry.assetPath || "-";
    renderTrainingLink(entry);
  }

  function renderTrainingLink(entry) {
    var linked = Boolean(entry.candidateId && entry.runId);
    elements.trainingLinkStatus.textContent = linked ? "已关联训练候选" : "未关联训练候选";
    elements.trainingLinkStatus.className = "badge status-badge " + (linked ? "is-direct" : "is-context");
    elements.trainingRunId.textContent = entry.runId || "-";
    elements.trainingCandidateId.textContent = entry.candidateId || "-";
    elements.trainingCaseId.textContent = entry.trainingCaseId || "-";
    elements.trainingMaterialChanges.textContent = String(entry.materialChangeCount || 0);

    var fidelity = entry.sourceScriptFidelity || "unknown";
    elements.sourceScriptFidelity.textContent = fidelity === "source_scripts_excluded"
      ? "源脚本未带入"
      : fidelity === "no_ignored_script_dependencies"
        ? "无忽略脚本依赖"
      : fidelity === "source_scripts_captured" || fidelity === "complete"
        ? "源脚本已覆盖"
        : "脚本状态未知";
    elements.sourceScriptFidelity.className = "badge " + (fidelity === "source_scripts_excluded" ? "is-warning" : "");

    elements.materialKeyTimes.innerHTML = "";
    var keyTimes = Array.isArray(entry.materialKeyTimes) ? entry.materialKeyTimes : [];
    keyTimes.slice(0, 12).forEach(function (time) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "key-time-button";
      button.textContent = Number(time).toFixed(2) + "s";
      button.title = "重播并暂停到材质变化时间点";
      button.addEventListener("click", function () { send("ReplayAt", Number(time).toFixed(4)); });
      elements.materialKeyTimes.appendChild(button);
    });
    if (!keyTimes.length) {
      var empty = document.createElement("span");
      empty.className = "key-time-empty";
      empty.textContent = linked ? "没有已记录的材质变化点" : "等待材质时间线";
      elements.materialKeyTimes.appendChild(empty);
    }
    updateReviewAvailability();
  }

  function renderRuntime() {
    elements.particleCount.textContent = String(runtime.liveParticles || 0);
    elements.rendererCount.textContent = String(runtime.activeRenderers || 0);
    elements.materialChangeCount.textContent = String(runtime.webglMaterialStateChanges || 0);
    elements.elapsedTime.textContent = Number(runtime.elapsed || 0).toFixed(2);
    elements.effectSpeed.textContent = Number(runtime.speed || 1).toFixed(runtime.speed % 1 ? 2 : 0) + "×";

    elements.pauseButton.innerHTML = runtime.paused
      ? '<i data-lucide="play" aria-hidden="true"></i><span class="icon-fallback">▶</span>'
      : '<i data-lucide="pause" aria-hidden="true"></i><span class="icon-fallback">Ⅱ</span>';
    elements.pauseButton.title = runtime.paused ? "继续" : "暂停";
    elements.pauseButton.setAttribute("aria-label", runtime.paused ? "继续" : "暂停");
    refreshIcons();

    document.querySelectorAll("#speed-control button").forEach(function (button) {
      button.classList.toggle("is-active", Number(button.dataset.speed) === Number(runtime.speed));
    });
  }

  function updateReviewAvailability() {
    var entry = currentEntry();
    var linked = Boolean(entry && entry.runId && entry.candidateId);
    var complete = Boolean(elements.reviewerInput.value.trim() && elements.reviewSummaryInput.value.trim());
    elements.saveReviewButton.disabled = !(linked && complete);
    elements.exportReviewsButton.disabled = reviews.length === 0;
    elements.reviewCount.textContent = String(reviews.length);
  }

  function makeFeedbackRecord() {
    var entry = currentEntry();
    if (!entry || !entry.runId || !entry.candidateId) return null;
    var record = {
      schema_version: "human_feedback.v1",
      run_id: entry.runId,
      candidate_id: entry.candidateId,
      training_case_id: entry.trainingCaseId || null,
      reviewed_at: new Date().toISOString(),
      reviewer: elements.reviewerInput.value.trim(),
      decision: elements.decisionSelect.value,
      mutation_allowed: elements.decisionSelect.value !== "reject" && elements.decisionSelect.value !== "not_visible",
      style_match_decision: elements.styleMatchSelect.value,
      scores: {
        dynamic_quality: Number(elements.dynamicQualityInput.value),
        rhythm_quality: Number(elements.rhythmQualityInput.value),
      },
      trace: {
        spec_path: entry.specPath || null,
        render_manifest_path: entry.renderManifestPath || null,
        render_paths: [],
        seed: entry.hasSeed ? Number(entry.seed) : null,
        generator: entry.generator || null,
        generator_version: entry.generatorVersion || null,
        render_status: entry.materialTimelineStatus || "unknown",
        material_timeline_path: entry.materialTimelinePath || null,
      },
      feedback: {
        summary: elements.reviewSummaryInput.value.trim(),
        accepted_parts: [],
        rejected_parts: [],
        reject_reasons: [],
        next_mutation: [],
      },
      web_review_context: {
        web_prefab_id: entry.id,
        web_prefab_path: entry.assetPath,
        source_prefab_path: entry.sourcePath,
        observed_time_seconds: Number(runtime.elapsed || 0),
        paused: Boolean(runtime.paused),
        speed: Number(runtime.speed || 1),
        background: runtime.background || null,
        yaw: Number(runtime.yaw || 0),
        pitch: Number(runtime.pitch || 0),
        distance: Number(runtime.distance || 0),
        material_state_fingerprint: runtime.materialStateFingerprint || null,
        webgl_material_state_changes: Number(runtime.webglMaterialStateChanges || 0),
        truth_material_change_count: Number(entry.materialChangeCount || 0),
        source_script_fidelity: entry.sourceScriptFidelity || "unknown",
        evidence_role: "dynamic_human_review_only",
      },
    };
    if (entry.effectFamily) record.effect_family = entry.effectFamily;
    return record;
  }

  function saveReview() {
    var record = makeFeedbackRecord();
    if (!record) {
      showBanner("当前 Prefab 没有关联训练候选。", "warning");
      return;
    }
    reviews.push(record);
    elements.reviewSummaryInput.value = "";
    updateReviewAvailability();
    showBanner("动态评价已记录。", "success");
  }

  function exportReviews() {
    if (!reviews.length) return;
    var text = reviews.map(function (record) { return JSON.stringify(record); }).join("\n") + "\n";
    var blob = new Blob([text], { type: "application/x-ndjson;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var anchor = document.createElement("a");
    var entry = currentEntry();
    anchor.href = url;
    anchor.download = "vfx_web_feedback_" + ((entry && entry.runId) || "review") + ".jsonl";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function showBanner(message, type) {
    if (!message) return;
    elements.warningBanner.textContent = message;
    elements.warningBanner.classList.add("is-visible");
    if (type !== "error") {
      window.setTimeout(function () {
        elements.warningBanner.classList.remove("is-visible");
      }, 5000);
    }
  }

  function handleUnityEvent(raw) {
    var event;
    try {
      event = typeof raw === "string" ? JSON.parse(raw) : raw;
    } catch (error) {
      showBanner("Unity 返回了无法解析的数据。", "error");
      return;
    }

    if (event.type === "catalog") {
      catalog = Array.isArray(event.catalog) ? event.catalog : [];
      rebuildCategories();
      renderCatalog();
      window.setTimeout(applyExternalSelection, 0);
      return;
    }

    if (event.type === "selection" && event.selection) {
      currentId = event.selection.id;
      renderCatalog();
      renderDetails();
      reportExternalSelection();
      if (requestedExternalSelectionId && currentId !== requestedExternalSelectionId) {
        window.setTimeout(applyExternalSelection, 0);
      }
      return;
    }

    if (event.type === "runtime" && event.runtime) {
      runtime = event.runtime;
      renderRuntime();
      return;
    }

    if (event.type === "error") {
      showBanner(event.message || "Unity 运行时错误。", "error");
      setStatus("运行时错误", "error");
    }
  }

  function bindControls() {
    elements.searchInput.addEventListener("input", renderCatalog);
    elements.categorySelect.addEventListener("change", renderCatalog);
    elements.reviewerInput.addEventListener("input", updateReviewAvailability);
    elements.reviewSummaryInput.addEventListener("input", updateReviewAvailability);
    elements.dynamicQualityInput.addEventListener("input", function () {
      elements.dynamicQualityOutput.textContent = elements.dynamicQualityInput.value;
    });
    elements.rhythmQualityInput.addEventListener("input", function () {
      elements.rhythmQualityOutput.textContent = elements.rhythmQualityInput.value;
    });
    elements.saveReviewButton.addEventListener("click", saveReview);
    elements.exportReviewsButton.addEventListener("click", exportReviews);

    document.querySelector("#replay-button").addEventListener("click", function () {
      send("Replay", "");
      window.setTimeout(function () { send("FitView", ""); }, 320);
    });
    elements.pauseButton.addEventListener("click", function () {
      send("SetPaused", String(!runtime.paused));
    });
    document.querySelector("#fit-button").addEventListener("click", function () { send("FitView", ""); });
    document.querySelector("#reset-view-button").addEventListener("click", function () { send("ResetView", ""); });

    document.querySelectorAll("#speed-control button").forEach(function (button) {
      button.addEventListener("click", function () {
        send("SetTimeScale", button.dataset.speed);
      });
    });

    document.querySelectorAll("#background-control .swatch").forEach(function (button) {
      button.addEventListener("click", function () {
        document.querySelectorAll("#background-control .swatch").forEach(function (item) {
          item.classList.remove("is-active");
        });
        button.classList.add("is-active");
        send("SetBackground", button.dataset.color);
      });
    });

    document.querySelector("#fullscreen-button").addEventListener("click", function () {
      if (unityInstance) unityInstance.SetFullscreen(1);
    });
    document.querySelector("#library-toggle").addEventListener("click", function () {
      elements.libraryPanel.classList.add("is-open");
    });
    document.querySelector("#library-close").addEventListener("click", function () {
      elements.libraryPanel.classList.remove("is-open");
    });

    elements.canvas.addEventListener("pointerdown", function (event) {
      pointerState = { id: event.pointerId, x: event.clientX, y: event.clientY };
      elements.canvas.setPointerCapture(event.pointerId);
    });
    elements.canvas.addEventListener("pointermove", function (event) {
      if (!pointerState || pointerState.id !== event.pointerId) return;
      var deltaX = event.clientX - pointerState.x;
      var deltaY = event.clientY - pointerState.y;
      pointerState.x = event.clientX;
      pointerState.y = event.clientY;
      send("Orbit", deltaX.toFixed(2) + "," + deltaY.toFixed(2));
    });
    function releasePointer(event) {
      if (pointerState && pointerState.id === event.pointerId) pointerState = null;
    }
    elements.canvas.addEventListener("pointerup", releasePointer);
    elements.canvas.addEventListener("pointercancel", releasePointer);
    elements.canvas.addEventListener("wheel", function (event) {
      event.preventDefault();
      send("Zoom", String(event.deltaY));
    }, { passive: false });
  }

  window.vfxWebPlayer = {
    attachUnity: function (instance) {
      unityInstance = instance;
      elements.loadingOverlay.classList.add("is-hidden");
      setStatus("运行时已连接", "ready");
      window.setTimeout(function () { send("RequestState", ""); }, 100);
      window.setTimeout(applyExternalSelection, 150);
    },
    failLoading: function (message) {
      setStatus("载入失败", "error");
      showBanner(String(message), "error");
    },
    setLoadingProgress: function (progress) {
      var percent = Math.round(Math.max(0, Math.min(1, progress)) * 100);
      elements.loadingPercent.textContent = percent + "%";
      elements.progressBar.style.width = percent + "%";
    },
    onUnityEvent: handleUnityEvent,
    showBanner: showBanner,
    getReviewRecords: function () { return reviews.slice(); },
    makeFeedbackRecord: makeFeedbackRecord,
  };

  if (embedMode) document.body.classList.add("vfx-web-embed");
  window.addEventListener("message", function (event) {
    if (!isAllowedReviewParent(event.origin)) return;
    var message = event.data;
    if (!message || message.type !== "vfx-web-select" || typeof message.catalogId !== "string") return;
    requestedExternalSelectionId = message.catalogId;
    applyExternalSelection();
  });
  bindControls();
  updateReviewAvailability();
  refreshIcons();
  window.addEventListener("load", refreshIcons);
}());
