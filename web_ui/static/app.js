// AutoAnime Shorts - Web UI Client Controller
document.addEventListener("DOMContentLoaded", () => {
  let currentStoryData = null;
  let activeJobInterval = null;
  let activeMode = "pre_generate";

  // Navigation Tabs
  const navBtns = document.querySelectorAll(".nav-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  navBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      navBtns.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(tabId).classList.add("active");

      if (tabId === "vault-tab") loadVaultStories();
      if (tabId === "upload-tab") loadUploadQueue();
      if (tabId === "settings-tab") loadSettings();
    });
  });

  // Mode Selection
  const modeChips = document.querySelectorAll(".mode-chip");
  const basePromptGroup = document.getElementById("base-prompt-group");
  const modeBadge = document.getElementById("mode-badge");
  const btnGenPrompts = document.getElementById("btn-generate-prompts");

  modeChips.forEach(chip => {
    chip.addEventListener("click", () => {
      modeChips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      activeMode = chip.getAttribute("data-mode");

      const modeTitles = {
        full_auto: "Full Auto Mode (Instant)",
        pre_generate: "Pre-Generate & Review",
        semi_manual: "Semi-Manual (AI Enhanced)",
        manual: "Manual Scripting"
      };
      modeBadge.textContent = modeTitles[activeMode] || activeMode;

      if (activeMode === "semi_manual") {
        basePromptGroup.style.display = "block";
      } else {
        basePromptGroup.style.display = "none";
      }

      if (activeMode === "full_auto") {
        btnGenPrompts.innerHTML = `<span class="btn-icon">⚡</span> Generate & Render Full Auto`;
      } else {
        btnGenPrompts.innerHTML = `<span class="btn-icon">✨</span> Generate Story & Prompts`;
      }
    });
  });

  // Duration Slider & Exact Scenes Sync
  const durationSlider = document.getElementById("duration-slider");
  const durationVal = document.getElementById("duration-val");
  const exactScenesInput = document.getElementById("exact-scenes-input");

  durationSlider.addEventListener("input", (e) => {
    const mins = parseFloat(e.target.value);
    const scenes = Math.max(5, Math.min(120, Math.round((mins * 60) / 7.5)));
    exactScenesInput.value = scenes;
    durationVal.textContent = `${mins.toFixed(1)} mins (${scenes} scenes)`;
  });

  exactScenesInput.addEventListener("input", (e) => {
    const sc = parseInt(e.target.value) || 20;
    const estMins = ((sc * 7.5) / 60).toFixed(1);
    durationVal.textContent = `${estMins} mins (${sc} scenes)`;
  });

  // Voice Preview Button
  const btnPreviewVoice = document.getElementById("btn-preview-voice");
  const voicePreviewPlayer = document.getElementById("voice-preview-player");
  const voiceSelect = document.getElementById("voice-select");

  btnPreviewVoice.addEventListener("click", async () => {
    const chosenVoice = voiceSelect.value;
    btnPreviewVoice.disabled = true;
    btnPreviewVoice.textContent = "⏳ Loading...";

    try {
      const res = await fetch("/api/tts/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice: chosenVoice })
      });
      const data = await res.json();
      if (data.status === "success" && data.audio_url) {
        voicePreviewPlayer.src = data.audio_url;
        voicePreviewPlayer.play();
        btnPreviewVoice.textContent = "🔊 Playing...";
        voicePreviewPlayer.onended = () => {
          btnPreviewVoice.disabled = false;
          btnPreviewVoice.textContent = "▶ Preview Voice";
        };
      } else {
        alert("Preview error: " + (data.detail || "Could not generate sample"));
        btnPreviewVoice.disabled = false;
        btnPreviewVoice.textContent = "▶ Preview Voice";
      }
    } catch (err) {
      alert("Error generating preview: " + err);
      btnPreviewVoice.disabled = false;
      btnPreviewVoice.textContent = "▶ Preview Voice";
    }
  });

  // 24/7 Autopilot Continuous Mode Controller
  const autopilotToggle = document.getElementById("autopilot-toggle");
  const autopilotActivePanel = document.getElementById("autopilot-active-panel");
  const autopilotCounter = document.getElementById("autopilot-counter");
  const autopilotStatusBadge = document.getElementById("autopilot-status-badge");
  const autopilotCooldownSelect = document.getElementById("autopilot-cooldown-select");

  async function updateAutopilotState(enabled) {
    try {
      const res = await fetch("/api/autopilot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: enabled,
          cooldown: parseInt(autopilotCooldownSelect.value) || 15,
          duration_mins: parseFloat(durationSlider.value) || 3.0,
          voice: voiceSelect.value
        })
      });
      const data = await res.json();
      if (enabled) {
        autopilotActivePanel.style.display = "block";
        showProgressBanner("♾️ 24/7 Autopilot Mode Active - Producing continuous video stream...", 10);
      } else {
        autopilotActivePanel.style.display = "none";
      }
    } catch (e) {
      console.error("Autopilot toggle error:", e);
    }
  }

  autopilotToggle.addEventListener("change", (e) => {
    updateAutopilotState(e.target.checked);
  });

  autopilotCooldownSelect.addEventListener("change", () => {
    if (autopilotToggle.checked) {
      updateAutopilotState(true);
    }
  });

  // Poll Autopilot Status
  setInterval(async () => {
    if (!autopilotToggle.checked) return;
    try {
      const res = await fetch("/api/autopilot");
      const data = await res.json();
      if (data.stats) {
        autopilotCounter.textContent = data.stats.videos_created || 0;
        const stateLabels = {
          generating_story: "Writing Story...",
          running: "Rendering Video...",
          cooldown: `Cooldown (${data.cooldown}s)...`,
          idle: "Active"
        };
        autopilotStatusBadge.textContent = stateLabels[data.stats.state] || data.stats.state;
      }
    } catch (err) {}
  }, 2500);

  // Generate Prompts / Story Button
  btnGenPrompts.addEventListener("click", async () => {
    const genre = document.getElementById("genre-select").value;
    const duration = parseFloat(durationSlider.value);
    const exactScenes = parseInt(exactScenesInput.value) || 20;
    const basePrompt = document.getElementById("base-prompt-input").value;

    btnGenPrompts.disabled = true;
    btnGenPrompts.innerHTML = `<span class="spinner"></span> Generating Narrative...`;

    try {
      const res = await fetch("/api/prompts/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: activeMode,
          genre_id: genre,
          duration_mins: duration,
          exact_scenes: exactScenes,
          base_prompt: basePrompt
        })
      });

      const data = await res.json();
      if (data.status === "success") {
        currentStoryData = data.story;
        renderStoryReview(currentStoryData);

        // If in Full Auto mode, immediately trigger render without user approval
        if (activeMode === "full_auto") {
          setTimeout(() => {
            document.getElementById("btn-approve-render").click();
          }, 800);
        }
      } else {
        alert("Generation failed: " + (data.detail || "Unknown error"));
      }
    } catch (err) {
      alert("Error contacting local server: " + err);
    } finally {
      btnGenPrompts.disabled = false;
      if (activeMode === "full_auto") {
        btnGenPrompts.innerHTML = `<span class="btn-icon">⚡</span> Generate & Render Full Auto`;
      } else {
        btnGenPrompts.innerHTML = `<span class="btn-icon">✨</span> Generate Story & Prompts`;
      }
    }
  });

  // Render Story Review & Scene Cards
  function renderStoryReview(story) {
    document.getElementById("review-empty-state").style.display = "none";
    document.getElementById("review-content").style.display = "block";
    document.getElementById("btn-approve-render").disabled = false;

    document.getElementById("story-title-input").value = story.title || "";
    document.getElementById("review-genre-badge").textContent = story.genre || "Anime Story";
    document.getElementById("story-logline-text").textContent = story.logline || "";
    document.getElementById("story-protagonist").textContent = story.protagonist || "N/A";
    document.getElementById("story-deuteragonist").textContent = story.deuteragonist || "N/A";
    document.getElementById("story-conflict").textContent = story.core_conflict || "N/A";
    document.getElementById("story-twist").textContent = story.climax_twist || "N/A";

    const scenesList = document.getElementById("scenes-list");
    scenesList.innerHTML = "";
    document.getElementById("scene-count-badge").textContent = (story.scenes || []).length;

    (story.scenes || []).forEach((sc, idx) => {
      const card = document.createElement("div");
      card.className = "scene-card";
      card.innerHTML = `
        <div class="scene-header">
          <span class="scene-badge">SCENE ${(sc.scene_number || idx + 1).toString().padStart(2, '0')}</span>
          <span class="scene-tag">[${(sc.mood || 'suspense').toUpperCase()}] • ${sc.motion_type || 'zoom_in'}</span>
        </div>
        <textarea class="scene-narration-box" rows="2" data-index="${idx}" data-field="narration" placeholder="Spoken narration text...">${sc.narration || ""}</textarea>
        <textarea class="scene-prompt-box" rows="2" data-index="${idx}" data-field="image_prompt" placeholder="Anime image prompt...">${sc.image_prompt || ""}</textarea>
      `;
      scenesList.appendChild(card);
    });
  }

  // Approve & Render Video
  const btnApprove = document.getElementById("btn-approve-render");
  btnApprove.addEventListener("click", async () => {
    if (!currentStoryData) return;

    // Harvest any user edits made in the scene review cards
    currentStoryData.title = document.getElementById("story-title-input").value;
    currentStoryData.voice = document.getElementById("voice-select")?.value || "am_michael";
    const narrationBoxes = document.querySelectorAll(".scene-narration-box");
    const promptBoxes = document.querySelectorAll(".scene-prompt-box");

    narrationBoxes.forEach(box => {
      const idx = parseInt(box.getAttribute("data-index"));
      if (currentStoryData.scenes[idx]) {
        currentStoryData.scenes[idx].narration = box.value;
      }
    });

    promptBoxes.forEach(box => {
      const idx = parseInt(box.getAttribute("data-index"));
      if (currentStoryData.scenes[idx]) {
        currentStoryData.scenes[idx].image_prompt = box.value;
      }
    });

    btnApprove.disabled = true;
    showProgressBanner("Starting production pipeline...", 5);

    try {
      const res = await fetch("/api/pipeline/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ story_data: currentStoryData })
      });

      const data = await res.json();
      if (data.status === "success") {
        pollJobStatus();
      } else {
        alert("Render start failed: " + (data.detail || "Error"));
        hideProgressBanner();
        btnApprove.disabled = false;
      }
    } catch (e) {
      alert("Error communicating with backend: " + e);
      hideProgressBanner();
      btnApprove.disabled = false;
    }
  });

  // Polling Job Status
  function pollJobStatus() {
    if (activeJobInterval) clearInterval(activeJobInterval);
    activeJobInterval = setInterval(async () => {
      try {
        const res = await fetch("/api/pipeline/status");
        const job = await res.json();

        if (job.status === "running") {
          showProgressBanner(job.stage || "Processing...", job.progress || 10);
        } else if (job.status === "completed") {
          clearInterval(activeJobInterval);
          hideProgressBanner();
          btnApprove.disabled = false;
          showVideoModal(job);
        } else if (job.status === "failed") {
          clearInterval(activeJobInterval);
          hideProgressBanner();
          btnApprove.disabled = false;
          alert("Pipeline Error: " + (job.error || "Unknown"));
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 1200);
  }

  function showProgressBanner(stage, percent) {
    const banner = document.getElementById("progress-banner");
    banner.style.display = "block";
    document.getElementById("progress-stage").textContent = stage;
    document.getElementById("progress-percent").textContent = `${percent}%`;
    document.getElementById("progress-bar-fill").style.width = `${percent}%`;
  }

  function hideProgressBanner() {
    document.getElementById("progress-banner").style.display = "none";
  }

  // Completion Video Modal
  window.closeVideoModal = () => {
    document.getElementById("video-complete-modal").style.display = "none";
    const vid = document.getElementById("player-video");
    vid.pause();
    vid.src = "";
  };

  let completedPackage = null;

  function showVideoModal(job) {
    const modal = document.getElementById("video-complete-modal");
    modal.style.display = "flex";

    const vid = document.getElementById("player-video");
    vid.src = job.video_url || "";
    vid.play().catch(() => {});

    document.getElementById("completed-video-title").textContent = job.story_title || "Generated Video";
    
    completedPackage = job.package || {};
    document.getElementById("completed-video-desc").textContent = completedPackage.description || "";

    const tagCloud = document.getElementById("completed-hashtags");
    tagCloud.innerHTML = "";
    (completedPackage.hashtags || []).forEach(t => {
      const sp = document.createElement("span");
      sp.className = "tag-badge";
      sp.textContent = t;
      tagCloud.appendChild(sp);
    });

    document.getElementById("completed-comment").textContent = completedPackage.pinned_comment || "No comment prompt.";
  }

  // Dispatch Upload from Modal
  document.getElementById("btn-dispatch-upload").addEventListener("click", async () => {
    if (!completedPackage || !completedPackage.video_path) {
      alert("No active video package available.");
      return;
    }

    const platforms = [];
    if (document.getElementById("up-yt").checked) platforms.push("youtube_shorts");
    if (document.getElementById("up-tt").checked) platforms.push("tiktok");
    if (document.getElementById("up-ig").checked) platforms.push("instagram_reels");

    const btn = document.getElementById("btn-dispatch-upload");
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Dispatching Uploads...`;

    try {
      const res = await fetch("/api/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          story_id: completedPackage.story_id,
          video_path: completedPackage.video_path,
          title: completedPackage.title,
          description: completedPackage.description,
          hashtags: completedPackage.hashtags,
          pinned_comment: completedPackage.pinned_comment,
          platforms: platforms
        })
      });
      const data = await res.json();
      alert("Upload Dispatched! Status: " + (data.result?.status || "Processed"));
      closeVideoModal();
    } catch (e) {
      alert("Upload failed: " + e);
    } finally {
      btn.disabled = false;
      btn.innerHTML = `🚀 Approve & Publish Video`;
    }
  });

  // Load Story Vault
  async function loadVaultStories() {
    const tbody = document.getElementById("vault-table-body");
    tbody.innerHTML = `<tr><td colspan="8" class="text-center">Loading Story Vault records...</td></tr>`;

    try {
      const res = await fetch("/api/stories?limit=30");
      const stories = await res.json();
      if (!stories || stories.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="padding: 30px; color: var(--text-muted);">No stories recorded yet. Generate your first video!</td></tr>`;
        return;
      }

      tbody.innerHTML = "";
      stories.forEach(s => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>#${s.id}</strong></td>
          <td><strong>${escapeHtml(s.title)}</strong></td>
          <td><span class="badge">${escapeHtml(s.genre)}</span></td>
          <td style="max-width: 280px; font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(s.logline)}</td>
          <td style="max-width: 200px; font-size: 0.78rem; color: #a5b4fc;">${escapeHtml(s.climax_twist || 'N/A')}</td>
          <td><span class="badge ${s.upload_status === 'uploaded' ? 'badge-accent' : ''}">${escapeHtml(s.upload_status)}</span></td>
          <td style="font-size: 0.75rem; color: var(--text-muted);">${(s.created_at || '').substring(0, 16)}</td>
          <td>
            ${s.video_url ? `<a href="${s.video_url}" target="_blank" class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;">▶ Watch</a>` : ''}
            <button onclick="deleteStory(${s.id})" class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.75rem; color: var(--danger-color);">✕</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="color: var(--danger-color);">Failed to load vault: ${e}</td></tr>`;
    }
  }

  document.getElementById("btn-refresh-vault").addEventListener("click", loadVaultStories);

  window.deleteStory = async (id) => {
    if (!confirm(`Delete story #${id} from vault?`)) return;
    await fetch(`/api/stories/${id}`, { method: "DELETE" });
    loadVaultStories();
  };

  // Load Social Upload Queue
  async function loadUploadQueue() {
    const queue = document.getElementById("upload-queue-container");
    queue.innerHTML = "<p>Loading uploads...</p>";

    try {
      const res = await fetch("/api/stories?limit=20");
      const stories = await res.json();
      queue.innerHTML = "";

      const videos = stories.filter(s => s.video_url);
      if (videos.length === 0) {
        queue.innerHTML = `<div class="empty-state"><div class="empty-icon">🚀</div><h3>No Videos in Queue</h3><p>Render a video from the Create tab to manage uploads here.</p></div>`;
        return;
      }

      videos.forEach(s => {
        const item = document.createElement("div");
        item.className = "card";
        item.style.marginBottom = "16px";
        item.innerHTML = `
          <div style="display: flex; gap: 18px; align-items: flex-start;">
            <video src="${s.video_url}" style="width: 120px; height: 180px; object-fit: cover; border-radius: 8px; background: #000;" controls></video>
            <div style="flex: 1;">
              <h3 style="font-size: 1.1rem; margin-bottom: 6px;">${escapeHtml(s.title)}</h3>
              <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 8px;">${escapeHtml(s.logline)}</p>
              <div style="font-size: 0.8rem; color: #38bdf8; margin-bottom: 12px;">${escapeHtml(s.hashtags || '')}</div>
              <div style="display: flex; gap: 10px; align-items: center;">
                <span class="badge ${s.upload_status === 'uploaded' ? 'badge-accent' : ''}">Status: ${escapeHtml(s.upload_status)}</span>
                <button onclick="dispatchManualUpload(${s.id}, '${escapeHtml(s.video_path)}', '${escapeHtml(s.title)}')" class="btn btn-primary" style="padding: 6px 14px; font-size: 0.8rem; width: auto;">
                  Upload Now
                </button>
              </div>
            </div>
          </div>
        `;
        queue.appendChild(item);
      });
    } catch (e) {
      queue.innerHTML = `<p style="color: var(--danger-color);">Error loading upload queue: ${e}</p>`;
    }
  }

  window.dispatchManualUpload = async (id, videoPath, title) => {
    try {
      const res = await fetch("/api/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          story_id: id,
          video_path: videoPath,
          title: title,
          description: title,
          hashtags: ["#animestory", "#shorts", "#fyp"],
          platforms: ["youtube_shorts", "tiktok"]
        })
      });
      alert("Upload dispatched!");
      loadUploadQueue();
    } catch (e) {
      alert("Upload error: " + e);
    }
  };

  // Load Settings
  async function loadSettings() {
    try {
      const res = await fetch("/api/config");
      const cfg = await res.json();
      document.getElementById("setting-auto-upload").checked = cfg.auto_upload || false;
      document.getElementById("setting-resolution").value = cfg.video_resolution || "576x1024";
      document.getElementById("setting-tts").value = cfg.tts_backend || "kokoro";
      if (document.getElementById("setting-voice")) {
        document.getElementById("setting-voice").value = cfg.tts_voice || "am_michael";
      }
      if (document.getElementById("voice-select")) {
        document.getElementById("voice-select").value = cfg.tts_voice || "am_michael";
      }
      document.getElementById("setting-bgm-vol").value = cfg.bgm_volume || 0.18;
      document.getElementById("setting-bgm-vol-text").textContent = `${cfg.bgm_volume || 0.18} (Auto-ducked)`;
    } catch (e) {
      console.error("Failed to load settings:", e);
    }
  }

  document.getElementById("setting-bgm-vol").addEventListener("input", (e) => {
    document.getElementById("setting-bgm-vol-text").textContent = `${e.target.value} (Auto-ducked)`;
  });

  document.getElementById("btn-save-settings").addEventListener("click", async () => {
    const payload = {
      auto_upload: document.getElementById("setting-auto-upload").checked,
      video_resolution: document.getElementById("setting-resolution").value,
      tts_backend: document.getElementById("setting-tts").value,
      tts_voice: document.getElementById("setting-voice")?.value || "am_michael",
      bgm_volume: parseFloat(document.getElementById("setting-bgm-vol").value)
    };

    try {
      await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      alert("Settings saved successfully!");
    } catch (e) {
      alert("Failed to save settings: " + e);
    }
  });

  function escapeHtml(text) {
    if (!text) return "";
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
});
