const stateEls = {
  systemStatus: document.getElementById("system-status"),
  streamIndicator: document.getElementById("stream-indicator"),
  streamStatus: document.getElementById("stream-status"),
  clock: document.getElementById("hud-clock"),
  currentTask: document.getElementById("current-task"),
  currentModel: document.getElementById("current-model"),
  currentAgent: document.getElementById("current-agent"),
  currentService: document.getElementById("current-service"),
  currentTool: document.getElementById("current-tool"),
  currentComplexity: document.getElementById("current-complexity"),
  focusPlanMode: document.getElementById("focus-plan-mode"),
  focusSubtasks: document.getElementById("focus-subtasks"),
  focusTools: document.getElementById("focus-tools"),
  focusHotEvent: document.getElementById("focus-hot-event"),
  diagWorker: document.getElementById("diag-worker"),
  diagReady: document.getElementById("diag-ready"),
  diagQueue: document.getElementById("diag-queue"),
  diagEvent: document.getElementById("diag-event"),
  queuePending: document.getElementById("queue-pending"),
  queueProgress: document.getElementById("queue-progress"),
  queueCompleted: document.getElementById("queue-completed"),
  queueFailed: document.getElementById("queue-failed"),
  eventStream: document.getElementById("event-stream"),
  eventFocus: document.getElementById("event-focus"),
  clearFocus: document.getElementById("clear-focus"),
  graphCanvas: document.getElementById("graph-canvas"),
  secondBrainGraphCanvas: document.getElementById("second-brain-graph-canvas"),
  metricTotal: document.getElementById("metric-total"),
  metricCompleted: document.getElementById("metric-completed"),
  metricFailed: document.getElementById("metric-failed"),
  metricFallbacks: document.getElementById("metric-fallbacks"),
  metricTools: document.getElementById("metric-tools"),
  metricToolFailures: document.getElementById("metric-tool-failures"),
  metricAvgDuration: document.getElementById("metric-avg-duration"),
  metricLastType: document.getElementById("metric-last-type"),
  lastUpdated: document.getElementById("last-updated"),
  recentTasks: document.getElementById("recent-tasks"),
  notesCount: document.getElementById("notes-count"),
  notesList: document.getElementById("notes-list"),
  notesSearch: document.getElementById("notes-search"),
  notesSearchButton: document.getElementById("notes-search-button"),
  notesNewButton: document.getElementById("notes-new-button"),
  routineCurrent: document.getElementById("routine-current"),
  routineNext: document.getElementById("routine-next"),
  routineList: document.getElementById("routine-list"),
  voiceToggle: document.getElementById("voice-toggle"),
  voiceStatus: document.getElementById("voice-status"),
  voiceTranscript: document.getElementById("voice-transcript"),
  taskForm: document.getElementById("task-form"),
  taskInput: document.getElementById("task-input"),
  clearEvents: document.getElementById("clear-events"),
  eventLimit: document.getElementById("event-limit"),
  eventLimitValue: document.getElementById("event-limit-value"),
  eventFilters: document.getElementById("event-filters"),
  taskDrawer: document.getElementById("task-drawer"),
  closeDrawer: document.getElementById("close-drawer"),
  drawerTaskId: document.getElementById("drawer-task-id"),
  drawerStatus: document.getElementById("drawer-status"),
  drawerAgent: document.getElementById("drawer-agent"),
  drawerModel: document.getElementById("drawer-model"),
  drawerFolder: document.getElementById("drawer-folder"),
  drawerUpdatedAt: document.getElementById("drawer-updated-at"),
  drawerInput: document.getElementById("drawer-input"),
  drawerTimeline: document.getElementById("drawer-timeline"),
  drawerTimelineCount: document.getElementById("drawer-timeline-count"),
  drawerPlayback: document.getElementById("drawer-playback"),
  drawerPlaybackValue: document.getElementById("drawer-playback-value"),
  drawerSummary: document.getElementById("drawer-summary"),
  drawerMemoryStatus: document.getElementById("drawer-memory-status"),
  drawerMemorySummary: document.getElementById("drawer-memory-summary"),
  drawerMemoryNotes: document.getElementById("drawer-memory-notes"),
  drawerMemoryCaptures: document.getElementById("drawer-memory-captures"),
  noteDrawer: document.getElementById("note-drawer"),
  closeNoteDrawer: document.getElementById("close-note-drawer"),
  noteDrawerTitle: document.getElementById("note-drawer-title"),
  noteDrawerCategory: document.getElementById("note-drawer-category"),
  noteDrawerUpdated: document.getElementById("note-drawer-updated"),
  noteDrawerId: document.getElementById("note-drawer-id"),
  noteDrawerTags: document.getElementById("note-drawer-tags"),
  noteDrawerLinks: document.getElementById("note-drawer-links"),
  noteDrawerBody: document.getElementById("note-drawer-body"),
  noteDrawerSource: document.getElementById("note-drawer-source"),
  noteEditButton: document.getElementById("note-edit-button"),
  drawerBackdrop: document.getElementById("drawer-backdrop"),
  graphModal: document.getElementById("graph-modal"),
  graphModalHost: document.getElementById("graph-modal-host"),
  graphModalTitle: document.getElementById("graph-modal-title"),
  graphModalClose: document.getElementById("graph-modal-close"),
  graphModalReset: document.getElementById("graph-modal-reset"),
  noteEditorModal: document.getElementById("note-editor-modal"),
  noteEditorTitle: document.getElementById("note-editor-title"),
  noteEditorName: document.getElementById("note-editor-name"),
  noteEditorCategory: document.getElementById("note-editor-category"),
  noteEditorTags: document.getElementById("note-editor-tags"),
  noteEditorBody: document.getElementById("note-editor-body"),
  noteEditorSave: document.getElementById("note-editor-save"),
  noteEditorClose: document.getElementById("note-editor-close"),
};

const clientState = {
  snapshot: null,
  filter: "all",
  focusedTaskId: null,
  eventLimit: Number(stateEls.eventLimit?.value || 40),
  socket: null,
  pollInterval: null,
  wsEnabled: Boolean(window.OFFICEOS_ENABLE_WS),
  wsEverOpened: false,
  wsFailures: 0,
  selectedTimeline: [],
  selectedNodeId: null,
  graphViewport: {
    "graph-canvas": { x: 0, y: 0, scale: 1 },
    "second-brain-graph-canvas": { x: 0, y: 0, scale: 1 },
  },
  expandedGraph: null,
  graphSignatures: {
    "graph-canvas": null,
    "second-brain-graph-canvas": null,
  },
  activeNote: null,
  notesMode: "recent",
  voice: {
    armed: false,
    listening: false,
    recognition: null,
    audioContext: null,
    analyser: null,
    stream: null,
    clapMonitor: null,
    clapCooldownUntil: 0,
  },
};

function formatDateTime(value) {
  if (!value) return "Unknown";
  const date = new Date(typeof value === "number" ? value * 1000 : value);
  return Number.isNaN(date.getTime()) ? "Unknown" : date.toLocaleString();
}

function formatTime(value) {
  if (!value) return "Unknown";
  const date = new Date(typeof value === "number" ? value * 1000 : value);
  return Number.isNaN(date.getTime()) ? "Unknown" : date.toLocaleTimeString();
}

function tickClock() {
  stateEls.clock.textContent = new Date().toLocaleTimeString();
}

function updateVoiceStatus(label, live = false) {
  if (stateEls.voiceStatus) stateEls.voiceStatus.textContent = label;
  if (stateEls.voiceTranscript) stateEls.voiceTranscript.classList.toggle("live", live);
}

function speakText(text) {
  if (!("speechSynthesis" in window) || !text) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.0;
  utterance.pitch = 0.95;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

async function submitVoiceTask(input) {
  await fetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });
  stateEls.taskInput.value = input;
  stateEls.voiceTranscript.textContent = `Heard: "${input}"\n\nMission submitted to OfficeOS.`;
  speakText("Mission received.");
  await loadSnapshot();
}

function stopSpeechRecognition() {
  const voice = clientState.voice;
  if (voice.recognition) {
    try {
      voice.recognition.onend = null;
      voice.recognition.stop();
    } catch {}
    voice.recognition = null;
  }
}

function setVoiceIdle(message = "Jarvis armed. Clap once to wake.") {
  clientState.voice.listening = false;
  stopSpeechRecognition();
  updateVoiceStatus(clientState.voice.armed ? "Clap Armed" : "Standby", false);
  if (stateEls.voiceToggle) {
    stateEls.voiceToggle.textContent = clientState.voice.armed ? "Disarm Clap Wake" : "Arm Clap Wake";
  }
  if (stateEls.voiceTranscript) stateEls.voiceTranscript.textContent = message;
}

function stopClapMonitor() {
  const voice = clientState.voice;
  if (voice.clapMonitor) {
    window.cancelAnimationFrame(voice.clapMonitor);
    voice.clapMonitor = null;
  }
  if (voice.stream) {
    voice.stream.getTracks().forEach((track) => track.stop());
    voice.stream = null;
  }
  if (voice.audioContext) {
    voice.audioContext.close().catch(() => {});
    voice.audioContext = null;
  }
  voice.analyser = null;
}

function disarmVoiceMode(message = "Voice wake disarmed.") {
  const voice = clientState.voice;
  voice.armed = false;
  voice.listening = false;
  stopSpeechRecognition();
  stopClapMonitor();
  updateVoiceStatus("Standby", false);
  if (stateEls.voiceToggle) stateEls.voiceToggle.textContent = "Arm Clap Wake";
  if (stateEls.voiceTranscript) stateEls.voiceTranscript.textContent = message;
}

function startSpeechRecognition() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    stateEls.voiceTranscript.textContent = "This browser does not support Web Speech recognition.";
    return;
  }
  const recognition = new Recognition();
  recognition.lang = "en-US";
  recognition.continuous = true;
  recognition.interimResults = true;
  clientState.voice.recognition = recognition;
  clientState.voice.listening = true;
  updateVoiceStatus("Listening", true);
  stateEls.voiceTranscript.textContent = "Jarvis awake. Speak your mission now.";
  speakText("Jarvis online.");

  recognition.onresult = async (event) => {
    let finalText = "";
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const transcript = event.results[i][0].transcript.trim();
      if (event.results[i].isFinal) finalText += `${transcript} `;
      else interim += `${transcript} `;
    }
    const preview = finalText || interim || "Listening...";
    stateEls.voiceTranscript.textContent = `Jarvis heard:\n${preview}`;

    if (finalText.trim()) {
      const cleaned = finalText.trim();
      if (/\b(stop voice|voice off|jarvis stop)\b/i.test(cleaned)) {
        setVoiceIdle("Jarvis standing by.");
        return;
      }
      await submitVoiceTask(cleaned);
      setVoiceIdle("Mission sent. Clap once to wake Jarvis again.");
    }
  };

  recognition.onerror = (event) => {
    stateEls.voiceTranscript.textContent = `Voice error: ${event.error}`;
    setVoiceIdle("Jarvis hit a voice error. Clap to try again.");
  };

  recognition.onend = () => {
    if (clientState.voice.armed && clientState.voice.listening) {
      setVoiceIdle("Jarvis standing by.");
    }
  };

  recognition.start();
}

async function startClapMonitor() {
  const voice = clientState.voice;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) return;
    const audioContext = new AudioContextCtor();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);
    const buffer = new Uint8Array(analyser.frequencyBinCount);

    voice.stream = stream;
    voice.audioContext = audioContext;
    voice.analyser = analyser;

    const loop = () => {
      if (!voice.armed || !voice.analyser) return;
      analyser.getByteFrequencyData(buffer);
      const peak = Math.max(...buffer);
      const average = buffer.reduce((sum, value) => sum + value, 0) / Math.max(buffer.length, 1);
      const now = Date.now();
      if (peak > 220 && average > 45 && now > voice.clapCooldownUntil) {
        voice.clapCooldownUntil = now + 1500;
        if (!voice.listening) startSpeechRecognition();
        else setVoiceIdle("Jarvis listening stopped by clap.");
      }
      voice.clapMonitor = window.requestAnimationFrame(loop);
    };
    voice.clapMonitor = window.requestAnimationFrame(loop);
    setVoiceIdle("Jarvis armed. Clap once to wake.");
  } catch (error) {
    console.error(error);
    disarmVoiceMode("Microphone permission is required for clap wake.");
  }
}

async function armVoiceMode() {
  if (clientState.voice.armed) {
    disarmVoiceMode();
    return;
  }
  clientState.voice.armed = true;
  updateVoiceStatus("Arming", false);
  stateEls.voiceTranscript.textContent = "Requesting microphone access for clap wake...";
  await startClapMonitor();
}

function setText(el, value, fallback = "None") {
  if (!el) return;
  el.textContent = value || fallback;
}

function safeStringify(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function normalizeTaskId(taskId) {
  if (typeof taskId === "string" && taskId.endsWith(".json")) {
    return taskId.slice(0, -5);
  }
  return taskId;
}

function matchesFilter(event, filter) {
  if (filter === "all") return true;
  if (filter === "warning" || filter === "error") return event.level === filter;
  if (filter === "tool") return String(event.type || "").includes("tool");
  if (filter === "model") return String(event.type || "").includes("model") || String(event.data?.model || "").length > 0;
  return true;
}

function eventBelongsToTask(event, taskId) {
  if (!taskId) return true;
  return event?.data?.task_id === taskId;
}

function summarizeEvent(event) {
  const data = event.data || {};
  if (data.tool_name && data.stage) return `${data.tool_name} -> ${data.stage}`;
  if (data.service && data.model) return `${data.service} -> ${data.model}`;
  if (data.agent) return `${event.type} -> ${data.agent}`;
  if (data.model) return `${event.type} -> ${data.model}`;
  if (data.subtask_id) return `subtask ${data.subtask_id}`;
  return event.description || event.type || "event";
}

function groupEvents(events) {
  const groups = [];
  events.forEach((event) => {
    const summary = summarizeEvent(event);
    const previous = groups[groups.length - 1];
    if (previous && previous.key === `${event.type}:${summary}`) {
      previous.events.push(event);
    } else {
      groups.push({
        key: `${event.type}:${summary}`,
        type: event.type,
        summary,
        events: [event],
      });
    }
  });
  return groups;
}

function renderEvents(events) {
  const filtered = events
    .slice(-clientState.eventLimit)
    .filter((event) => eventBelongsToTask(event, clientState.focusedTaskId))
    .filter((event) => matchesFilter(event, clientState.filter))
    .reverse();

  const groups = groupEvents(filtered);
  stateEls.eventStream.innerHTML = "";
  stateEls.eventFocus.textContent = clientState.focusedTaskId
    ? `Focused on ${clientState.focusedTaskId}`
    : "Mission-wide feed";

  if (!groups.length) {
    stateEls.eventStream.innerHTML = `<div class="event-item info"><div class="event-description">No events match the active filter.</div></div>`;
    return;
  }

  groups.forEach((group) => {
    const wrapper = document.createElement("div");
    wrapper.className = "event-group";

    const head = document.createElement("button");
    head.type = "button";
    head.className = "event-group-head";
    head.innerHTML = `
      <div class="event-group-title">
        <span class="pill">${group.type || "event"}</span>
        <span>${group.summary}</span>
      </div>
      <div class="event-group-count">${group.events.length} signal${group.events.length === 1 ? "" : "s"}</div>
    `;

    const body = document.createElement("div");
    body.className = "event-group-body";
    if (group.events.length > 3) {
      body.classList.add("collapsed");
    }

    head.addEventListener("click", () => {
      body.classList.toggle("collapsed");
    });

    group.events.forEach((event) => {
      const item = document.createElement("div");
      item.className = `event-item ${event.level || "info"}`;
      item.innerHTML = `
        <div class="event-meta">
          <span>${event.type || "event"}</span>
          <span>${formatTime(event.timestamp)}</span>
        </div>
        <div class="event-description">${event.description || "No description"}</div>
        <div class="event-data muted">${safeStringify(event.data || {})}</div>
      `;
      body.appendChild(item);
    });

    wrapper.appendChild(head);
    wrapper.appendChild(body);
    stateEls.eventStream.appendChild(wrapper);
  });
}

function openTaskDrawer() {
  closeNoteDrawer();
  stateEls.taskDrawer.classList.add("open");
  stateEls.drawerBackdrop.classList.add("open");
}

function closeTaskDrawer() {
  stateEls.taskDrawer.classList.remove("open");
  if (!stateEls.noteDrawer.classList.contains("open")) {
    stateEls.drawerBackdrop.classList.remove("open");
  }
}

function openNoteDrawer() {
  closeTaskDrawer();
  stateEls.noteDrawer.classList.add("open");
  stateEls.drawerBackdrop.classList.add("open");
}

function closeNoteDrawer() {
  stateEls.noteDrawer.classList.remove("open");
  if (!stateEls.taskDrawer.classList.contains("open")) {
    stateEls.drawerBackdrop.classList.remove("open");
  }
}

function openNoteEditor(note = null) {
  clientState.activeNote = note;
  stateEls.noteEditorTitle.textContent = note ? `Edit ${note.title || note.note_id}` : "New Note";
  stateEls.noteEditorName.value = note?.title || "";
  stateEls.noteEditorCategory.value = note?.category || "general";
  stateEls.noteEditorTags.value = (note?.tags || []).join(", ");
  stateEls.noteEditorBody.value = note?.body || "";
  stateEls.noteEditorModal.classList.add("open");
}

function closeNoteEditor() {
  stateEls.noteEditorModal.classList.remove("open");
}

function openGraphModal(panelId, title) {
  if (clientState.expandedGraph?.panelId === panelId) return;
  if (clientState.expandedGraph) closeGraphModal();
  const panel = document.getElementById(panelId);
  if (!panel) return;
  const svg = panel.querySelector("svg");
  if (!svg) return;
  const placeholder = document.createComment(`graph-placeholder:${panelId}`);
  panel.parentNode?.insertBefore(placeholder, panel);
  clientState.expandedGraph = {
    panelId,
    title,
    placeholder,
    svg,
  };
  stateEls.graphModalTitle.textContent = title || "Graph";
  stateEls.graphModalHost.appendChild(panel);
  stateEls.graphModal.classList.add("open");
}

function closeGraphModal() {
  if (!clientState.expandedGraph) return;
  const { placeholder, panelId } = clientState.expandedGraph;
  const panel = document.getElementById(panelId);
  if (panel && placeholder?.parentNode) {
    placeholder.parentNode.insertBefore(panel, placeholder);
    placeholder.remove();
  }
  stateEls.graphModal.classList.remove("open");
  clientState.expandedGraph = null;
}

function renderDrawerTimeline() {
  const timeline = clientState.selectedTimeline || [];
  const max = Math.max(1, timeline.length || 1);
  const playbackCount = Math.min(Number(stateEls.drawerPlayback.value || max), max);
  const visibleTimeline = timeline.slice(0, playbackCount);

  stateEls.drawerPlayback.max = String(max);
  stateEls.drawerPlayback.value = String(playbackCount);
  stateEls.drawerPlaybackValue.textContent = timeline.length
    ? `${visibleTimeline.length}/${timeline.length} events`
    : "Full trace";
  stateEls.drawerTimelineCount.textContent = `${visibleTimeline.length}/${timeline.length} events`;

  const counts = {};
  visibleTimeline.forEach((event) => {
    counts[event.type] = (counts[event.type] || 0) + 1;
  });

  stateEls.drawerSummary.innerHTML = "";
  Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .forEach(([type, count]) => {
      const marker = document.createElement("div");
      marker.className = "timeline-marker";
      marker.textContent = `${type} x${count}`;
      stateEls.drawerSummary.appendChild(marker);
    });

  stateEls.drawerTimeline.innerHTML = "";
  visibleTimeline.slice().reverse().forEach((event) => {
    const item = document.createElement("div");
    item.className = "drawer-timeline-item";
    item.innerHTML = `
      <div class="event-meta">
        <span>${event.type || "event"}</span>
        <span>${formatTime(event.timestamp)}</span>
      </div>
      <div class="event-description">${event.description || "No description"}</div>
      <div class="event-data muted">${safeStringify(event.data || {})}</div>
    `;
    stateEls.drawerTimeline.appendChild(item);
  });

  if (!timeline.length) {
    stateEls.drawerTimeline.innerHTML = `<div class="drawer-timeline-item">No timeline events recorded for this task yet.</div>`;
  }
}

function renderTaskMemory(memoryWorkflow) {
  const memory = memoryWorkflow || {};
  const noteTitles = memory.note_titles || [];
  const captures = memory.captures || [];

  stateEls.drawerMemoryStatus.textContent = memory.used
    ? `${memory.notes_used_count || noteTitles.length} notes consulted`
    : captures.length
      ? `${captures.length} notes captured`
      : "No memory data";
  stateEls.drawerMemorySummary.textContent = memory.summary || "No second-brain activity recorded for this task yet.";

  stateEls.drawerMemoryNotes.innerHTML = "";
  if (noteTitles.length) {
    const notesCard = document.createElement("div");
    notesCard.className = "drawer-memory-card";
    notesCard.innerHTML = `
      <div class="drawer-memory-title">Notes Consulted</div>
      <div>${noteTitles.join(", ")}</div>
    `;
    stateEls.drawerMemoryNotes.appendChild(notesCard);
  }

  stateEls.drawerMemoryCaptures.innerHTML = "";
  if (captures.length) {
    captures.forEach((capture) => {
      const card = document.createElement("div");
      card.className = "drawer-memory-card";
      card.innerHTML = `
        <div class="drawer-memory-title">${capture.channel || "Capture"}</div>
        <div>${capture.title || capture.note_id || "Untitled note"}</div>
        <div class="muted">${capture.category || "general"}</div>
      `;
      stateEls.drawerMemoryCaptures.appendChild(card);
    });
  }
}

async function loadTaskDetail(taskId) {
  const response = await fetch(`/api/task/${encodeURIComponent(taskId)}`);
  if (!response.ok) throw new Error("Failed to load task detail");

  const record = await response.json();
  const task = record.task || {};
  clientState.selectedTimeline = record.timeline || [];
  clientState.focusedTaskId = normalizeTaskId(task.task_id || taskId);

  setText(stateEls.drawerTaskId, normalizeTaskId(task.task_id || taskId), "Unknown task");
  setText(stateEls.drawerStatus, task.status, "Unknown");
  setText(stateEls.drawerAgent, task.agent, "Unknown");
  setText(stateEls.drawerModel, task.model, "Unknown");
  setText(stateEls.drawerFolder, record.folder, "Unknown");
  stateEls.drawerUpdatedAt.textContent = formatDateTime(record.updated_at);
  stateEls.drawerInput.textContent = task.input || task.original_input || "No task input captured.";
  renderTaskMemory(record.memory_workflow || task.memory_workflow || {});
  stateEls.drawerPlayback.max = String(Math.max(1, clientState.selectedTimeline.length || 1));
  stateEls.drawerPlayback.value = String(Math.max(1, clientState.selectedTimeline.length || 1));
  renderDrawerTimeline();
  if (clientState.snapshot) renderEvents(clientState.snapshot.events || []);
  openTaskDrawer();
}

async function loadNoteDetail(noteId) {
  const response = await fetch(`/api/note/${encodeURIComponent(noteId)}`);
  if (!response.ok) throw new Error("Failed to load note detail");

  const note = await response.json();
  clientState.activeNote = note;
  clientState.selectedNodeId = note.note_id;
  setText(stateEls.noteDrawerTitle, note.title, "Unknown note");
  setText(stateEls.noteDrawerCategory, note.category, "General");
  stateEls.noteDrawerUpdated.textContent = formatDateTime(note.updated_at);
  setText(stateEls.noteDrawerId, note.note_id, "Unknown note");
  setText(stateEls.noteDrawerSource, note.source_type || note.path || "Manual note");
  stateEls.noteDrawerBody.innerHTML = renderNoteBody(note.body);
  stateEls.noteDrawerTags.innerHTML = (note.tags || [])
    .map((tag) => `<span class="pill">${tag}</span>`)
    .join("");

  const links = note.links || [];
  const backlinks = note.backlinks || [];
  stateEls.noteDrawerLinks.innerHTML = `
    <div><strong>Links</strong>: ${links.length ? links.join(", ") : "None"}</div>
    <div><strong>Backlinks</strong>: ${backlinks.length ? backlinks.join(", ") : "None"}</div>
  `;
  stateEls.noteDrawerBody.querySelectorAll("[data-note-link]").forEach((link) => {
    link.addEventListener("click", () => {
      loadNoteDetail(link.dataset.noteLink).catch((error) => console.error(error));
    });
  });
  openNoteDrawer();
}

async function searchNotes(query = "") {
  const url = query.trim() ? `/api/notes?query=${encodeURIComponent(query.trim())}&limit=12` : "/api/notes?limit=12";
  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to search notes");
  return response.json();
}

async function saveNoteFromEditor() {
  const payload = {
    title: stateEls.noteEditorName.value.trim(),
    content: stateEls.noteEditorBody.value,
    category: stateEls.noteEditorCategory.value.trim() || "general",
    tags: stateEls.noteEditorTags.value
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
    note_id: clientState.activeNote?.note_id || null,
  };
  const response = await fetch("/api/notes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to save note");
  const saved = await response.json();
  closeNoteEditor();
  await loadSnapshot();
  await loadNoteDetail(saved.note_id || payload.note_id || payload.title);
}

function renderRecentTasks(tasks) {
  stateEls.recentTasks.innerHTML = "";
  tasks.forEach((task) => {
    const normalizedTaskId = normalizeTaskId(task.task_id);
    const item = document.createElement("button");
    item.type = "button";
    item.className = "task-item";
    item.innerHTML = `
      <div class="task-meta">
        <span>${task.status || "unknown"}</span>
        <span>${task.task_type || "unknown"}</span>
      </div>
      <div>${normalizedTaskId}</div>
      <div class="muted">Agent: ${task.agent || "unknown"} | Model: ${task.model || "unknown"}</div>
    `;
    item.addEventListener("click", () => {
      loadTaskDetail(normalizedTaskId).catch((error) => console.error(error));
    });
    stateEls.recentTasks.appendChild(item);
  });
}

function renderRoutine(routine) {
  setText(stateEls.routineCurrent, routine.current_block?.title, "No active block");
  setText(stateEls.routineNext, routine.next_block?.title, "No upcoming block");
  stateEls.routineList.innerHTML = "";
  (routine.blocks || []).forEach((block) => {
    const item = document.createElement("div");
    item.className = "routine-item";
    item.innerHTML = `
      <div class="task-meta">
        <span>${block.category || "general"}</span>
        <span>${block.start || "--"} - ${block.end || "--"}</span>
      </div>
      <div>${block.title || "Untitled block"}</div>
      <div class="muted">${block.notes || ""}</div>
    `;
    stateEls.routineList.appendChild(item);
  });
}

function renderNotes(notesSnapshot) {
  const notes = notesSnapshot?.recent || notesSnapshot?.notes || notesSnapshot?.results || [];
  stateEls.notesCount.textContent = `${notesSnapshot?.count ?? notes.length} notes`;
  stateEls.notesList.innerHTML = "";

  notes.forEach((note) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "task-item";
    item.innerHTML = `
      <div class="task-meta">
        <span>${note.category || note.source || "general"}</span>
        <span>${note.links_count || 0} links</span>
        <span>${note.backlinks_count || 0} backlinks</span>
      </div>
      <div>${note.title || note.note_id}</div>
      <div class="muted">${note.note_id}</div>
      <div class="note-tags">${(note.tags || []).map((tag) => `<span class="pill">${tag}</span>`).join("")}</div>
    `;
    item.addEventListener("click", () => {
      loadNoteDetail(note.note_id).catch((error) => console.error(error));
    });
    stateEls.notesList.appendChild(item);
  });

  if (!notes.length) {
    stateEls.notesList.innerHTML = `<div class="event-item info"><div class="event-description">No notes captured yet. Save a note to start building your second brain.</div></div>`;
  }
}

function getSvgPoint(svg, clientX, clientY) {
  const point = svg.createSVGPoint();
  point.x = clientX;
  point.y = clientY;
  const ctm = svg.getScreenCTM();
  return ctm ? point.matrixTransform(ctm.inverse()) : { x: clientX, y: clientY };
}

function truncateLabel(label, max = 18) {
  return label.length > max ? `${label.slice(0, max)}...` : label;
}

function renderNoteBody(body) {
  const escaped = escapeHtml(body || "No note body captured.");
  return escaped
    .replace(/\[\[([^\]]+)\]\]/g, (_match, noteTitle) => {
      const title = noteTitle.trim();
      return `<button type="button" class="wiki-link" data-note-link="${escapeHtml(title)}">[[${escapeHtml(title)}]]</button>`;
    })
    .replace(/\n/g, "<br>");
}

function graphSignature(graph) {
  const nodes = (graph.nodes || []).map((node) => `${node.id}:${node.type}:${node.status || ""}`).sort().join("|");
  const edges = (graph.edges || []).map((edge) => `${edge.source}>${edge.target}:${edge.label || ""}`).sort().join("|");
  return `${nodes}::${edges}`;
}

function computeForceLayout(nodes, edges, width, height) {
  const placed = nodes.map((node, index) => ({
    id: node.id,
    x: width / 2 + Math.cos((index / Math.max(nodes.length, 1)) * Math.PI * 2) * Math.min(width, height) * 0.24,
    y: height / 2 + Math.sin((index / Math.max(nodes.length, 1)) * Math.PI * 2) * Math.min(width, height) * 0.24,
    vx: 0,
    vy: 0,
    type: node.type,
  }));
  const byId = Object.fromEntries(placed.map((node) => [node.id, node]));

  for (let i = 0; i < 120; i += 1) {
    for (let a = 0; a < placed.length; a += 1) {
      for (let b = a + 1; b < placed.length; b += 1) {
        const first = placed[a];
        const second = placed[b];
        let dx = second.x - first.x;
        let dy = second.y - first.y;
        const distance = Math.sqrt(dx * dx + dy * dy) || 0.1;
        const force = 2200 / (distance * distance);
        dx /= distance;
        dy /= distance;
        first.vx -= dx * force;
        first.vy -= dy * force;
        second.vx += dx * force;
        second.vy += dy * force;
      }
    }

    edges.forEach((edge) => {
      const source = byId[edge.source];
      const target = byId[edge.target];
      if (!source || !target) return;
      let dx = target.x - source.x;
      let dy = target.y - source.y;
      const distance = Math.sqrt(dx * dx + dy * dy) || 0.1;
      const desired = edge.label === "captured_as" ? 115 : 90;
      const force = (distance - desired) * 0.008;
      dx /= distance;
      dy /= distance;
      source.vx += dx * force;
      source.vy += dy * force;
      target.vx -= dx * force;
      target.vy -= dy * force;
    });

    placed.forEach((node) => {
      const centerPull = node.type === "task_record" ? 0.015 : 0.009;
      node.vx += (width / 2 - node.x) * centerPull;
      node.vy += (height / 2 - node.y) * centerPull;
      node.vx *= 0.82;
      node.vy *= 0.82;
      node.x = Math.max(44, Math.min(width - 44, node.x + node.vx));
      node.y = Math.max(44, Math.min(height - 44, node.y + node.vy));
    });
  }

  return Object.fromEntries(placed.map((node) => [node.id, { x: node.x, y: node.y }]));
}

function getNodeRadius(node) {
  if (node.type === "task" || node.type === "task_record") return 26;
  if (node.type === "agent") return 18;
  if (node.type === "note") return 16;
  return 14;
}

function getNodeColors(node) {
  if (node.type === "task" || node.type === "task_record") {
    return { fill: "rgba(255,159,67,0.22)", stroke: "rgba(255,190,108,0.95)" };
  }
  if (node.type === "agent") {
    return { fill: "rgba(110,243,255,0.18)", stroke: "rgba(110,243,255,0.9)" };
  }
  if (node.type === "note") {
    return { fill: "rgba(125,255,143,0.2)", stroke: "rgba(125,255,143,0.9)" };
  }
  return { fill: "rgba(110,243,255,0.12)", stroke: "rgba(110,243,255,0.75)" };
}

function describeNode(node) {
  if (node.type === "note") return node.category || "note";
  if (node.type === "task_record") return node.status || "task";
  if (node.type === "task") return node.status || "live";
  if (node.type === "agent") return node.model || "agent";
  return node.type || "node";
}

function computeLinearLayout(nodes) {
  const positions = {};
  const centerX = 350;
  let subtaskIndex = 0;
  let toolIndex = 0;

  nodes.forEach((node) => {
    if (node.type === "task") {
      positions[node.id] = { x: centerX, y: 62 };
    } else if (node.type === "task_record") {
      positions[node.id] = { x: centerX, y: 70 };
    } else if (node.type === "agent") {
      positions[node.id] = { x: centerX, y: 180 };
    } else if (node.type === "subtask") {
      positions[node.id] = { x: centerX + (subtaskIndex * 170 - 170), y: 300 };
      subtaskIndex += 1;
    } else if (node.type === "tool") {
      positions[node.id] = { x: centerX + (toolIndex * 160 - 80), y: 250 };
      toolIndex += 1;
    } else if (node.type === "note") {
      positions[node.id] = { x: centerX + (toolIndex * 150 - 150), y: 280 };
      toolIndex += 1;
    } else {
      positions[node.id] = { x: centerX, y: 180 };
    }
  });

  return positions;
}

function applyViewport(svg, layer, viewportKey) {
  const viewport = clientState.graphViewport[viewportKey];
  layer.setAttribute("transform", `translate(${viewport.x} ${viewport.y}) scale(${viewport.scale})`);
}

function resetGraphViewport(viewportKey) {
  clientState.graphViewport[viewportKey] = { x: 0, y: 0, scale: 1 };
  if (clientState.snapshot) {
    renderGraph(clientState.snapshot.agent_graph || { nodes: [], edges: [] }, stateEls.graphCanvas);
    renderGraph(clientState.snapshot.second_brain_graph || { nodes: [], edges: [] }, stateEls.secondBrainGraphCanvas);
  }
}

function attachGraphInteractions(svg, layer, viewportKey) {
  if (svg.dataset.interactiveReady === viewportKey) {
    applyViewport(svg, layer, viewportKey);
    return;
  }

  let dragState = null;
  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    const viewport = clientState.graphViewport[viewportKey];
    const delta = event.deltaY < 0 ? 1.12 : 0.9;
    viewport.scale = Math.max(0.55, Math.min(2.8, viewport.scale * delta));
    applyViewport(svg, layer, viewportKey);
  });

  svg.addEventListener("pointerdown", (event) => {
    if (event.target.closest(".graph-node")) return;
    dragState = {
      id: event.pointerId,
      point: getSvgPoint(svg, event.clientX, event.clientY),
      viewport: { ...clientState.graphViewport[viewportKey] },
    };
    svg.setPointerCapture(event.pointerId);
  });

  svg.addEventListener("pointermove", (event) => {
    if (!dragState || dragState.id !== event.pointerId) return;
    const point = getSvgPoint(svg, event.clientX, event.clientY);
    const viewport = clientState.graphViewport[viewportKey];
    viewport.x = dragState.viewport.x + (point.x - dragState.point.x);
    viewport.y = dragState.viewport.y + (point.y - dragState.point.y);
    applyViewport(svg, layer, viewportKey);
  });

  const stopDrag = (event) => {
    if (dragState && dragState.id === event.pointerId) {
      dragState = null;
      try {
        svg.releasePointerCapture(event.pointerId);
      } catch {}
    }
  };

  svg.addEventListener("pointerup", stopDrag);
  svg.addEventListener("pointercancel", stopDrag);
  svg.dataset.interactiveReady = viewportKey;
  applyViewport(svg, layer, viewportKey);
}

function setGraphSelection(svg, nodeId) {
  svg.querySelectorAll(".graph-node").forEach((node) => {
    const isActive = node.dataset.nodeId === nodeId;
    node.classList.toggle("active", isActive);
    node.classList.toggle("dimmed", Boolean(nodeId) && !isActive);
  });
  svg.querySelectorAll(".graph-edge").forEach((edge) => {
    const isConnected = edge.dataset.source === nodeId || edge.dataset.target === nodeId;
    edge.classList.toggle("dimmed", Boolean(nodeId) && !isConnected);
  });
}

function handleGraphNodeClick(node) {
  clientState.selectedNodeId = node.id;
  if (node.type === "task" || node.type === "task_record") {
    loadTaskDetail(String(node.id).replace(/^task:/, "")).catch((error) => console.error(error));
    return;
  }
  if (node.type === "note") {
    loadNoteDetail(node.id).catch((error) => console.error(error));
  }
}

function renderGraph(graph, svg = stateEls.graphCanvas, options = {}) {
  svg.innerHTML = "";
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const viewportKey = svg.id;
  const stage = svg.closest(".graph-stage");
  const updated = Boolean(options.updated);

  if (!nodes.length) {
    svg.innerHTML = `<text x="50%" y="50%" text-anchor="middle" fill="rgba(232,246,255,0.55)" font-size="18">Awaiting live task topology...</text>`;
    return;
  }

  if (stage) {
    stage.classList.toggle("graph-updated", updated);
    if (updated) {
      window.setTimeout(() => stage.classList.remove("graph-updated"), 1200);
    }
  }

  const layer = document.createElementNS("http://www.w3.org/2000/svg", "g");
  svg.appendChild(layer);
  const positions = svg === stateEls.secondBrainGraphCanvas
    ? computeForceLayout(nodes, edges, 700, 360)
    : computeLinearLayout(nodes);

  edges.forEach((edge) => {
    const from = positions[edge.source];
    const to = positions[edge.target];
    if (!from || !to) return;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.classList.add("graph-edge", "entering");
    if (updated) path.classList.add("live-pulse");
    path.dataset.source = edge.source;
    path.dataset.target = edge.target;
    const curve = svg === stateEls.secondBrainGraphCanvas ? 26 : 14;
    const midX = (from.x + to.x) / 2;
    const midY = (from.y + to.y) / 2 - curve;
    path.setAttribute("d", `M ${from.x} ${from.y} Q ${midX} ${midY} ${to.x} ${to.y}`);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", edge.label === "captured_as" ? "rgba(125,255,143,0.34)" : "rgba(110,243,255,0.34)");
    path.setAttribute("stroke-width", edge.label === "captured_as" ? "2.4" : "1.8");
    path.setAttribute("stroke-dasharray", edge.label === "contains" ? "5 5" : "0");
    layer.appendChild(path);
  });

  nodes.forEach((node, index) => {
    const { x, y } = positions[node.id];
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.classList.add("graph-node", "entering");
    group.classList.add(index % 3 === 0 ? "float-a" : index % 3 === 1 ? "float-b" : "float-c");
    group.dataset.nodeId = node.id;
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    const labelBg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    const sublabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    const shine = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    const radius = getNodeRadius(node);
    const colors = getNodeColors(node);
    const primaryLabel = truncateLabel(node.label || node.id, 20);
    const secondaryLabel = truncateLabel(describeNode(node), 18);

    circle.setAttribute("cx", x);
    circle.setAttribute("cy", y);
    circle.setAttribute("r", String(radius));
    circle.setAttribute("fill", colors.fill);
    circle.setAttribute("stroke", node.fallback_used ? "rgba(255,93,108,0.92)" : colors.stroke);
    circle.setAttribute("stroke-width", "2.2");

    shine.setAttribute("cx", String(x - radius * 0.28));
    shine.setAttribute("cy", String(y - radius * 0.34));
    shine.setAttribute("r", String(Math.max(4, radius * 0.34)));
    shine.setAttribute("fill", "rgba(255,255,255,0.2)");

    label.setAttribute("x", x);
    label.setAttribute("y", y + radius + 20);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", "graph-node-label");
    label.textContent = primaryLabel;

    sublabel.setAttribute("x", x);
    sublabel.setAttribute("y", y + radius + 34);
    sublabel.setAttribute("text-anchor", "middle");
    sublabel.setAttribute("fill", "rgba(135,168,187,0.9)");
    sublabel.setAttribute("font-size", "9");
    sublabel.textContent = secondaryLabel;

    const labelWidth = Math.max(primaryLabel.length * 7.1, secondaryLabel.length * 6.1) + 18;
    labelBg.setAttribute("x", String(x - labelWidth / 2));
    labelBg.setAttribute("y", String(y + radius + 8));
    labelBg.setAttribute("width", String(labelWidth));
    labelBg.setAttribute("height", "34");
    labelBg.setAttribute("rx", "10");
    labelBg.setAttribute("class", "graph-node-label-bg");

    group.appendChild(circle);
    group.appendChild(shine);
    group.appendChild(labelBg);
    group.appendChild(label);
    group.appendChild(sublabel);
    group.addEventListener("click", (event) => {
      event.stopPropagation();
      handleGraphNodeClick(node);
      setGraphSelection(svg, node.id);
    });
    layer.appendChild(group);
  });

  svg.onclick = () => {
    clientState.selectedNodeId = null;
    setGraphSelection(svg, null);
  };
  attachGraphInteractions(svg, layer, viewportKey);
  setGraphSelection(svg, clientState.selectedNodeId);
}

function renderSnapshot(snapshot) {
  clientState.snapshot = snapshot;
  const state = snapshot.state || {};
  const queue = snapshot.queue || {};
  const metrics = state.metrics || {};
  const focus = snapshot.focus || {};
  const diagnostics = snapshot.diagnostics || {};

  setText(stateEls.systemStatus, (state.status || "idle").toUpperCase());
  setText(stateEls.currentTask, normalizeTaskId(state.current_task), "No active task");
  setText(stateEls.currentModel, state.current_model, "No model");
  setText(stateEls.currentAgent, state.current_agent, "Idle");
  setText(stateEls.currentService, state.current_external_service, "None");
  setText(stateEls.currentTool, state.current_tool, "None");
  setText(stateEls.currentComplexity, state.current_classification?.complexity, "Unknown");
  setText(stateEls.focusPlanMode, focus.plan_mode, "Idle");
  stateEls.focusSubtasks.textContent = String(focus.active_subtasks ?? 0);
  stateEls.focusTools.textContent = String(focus.selected_tools ?? 0);
  setText(stateEls.focusHotEvent, focus.hottest_events?.[0] ? `${focus.hottest_events[0].type} x${focus.hottest_events[0].count}` : null, "Awaiting telemetry");
  setText(stateEls.diagWorker, diagnostics.worker_connected ? "Connected" : "Disconnected", "Unknown");
  setText(stateEls.diagReady, diagnostics.ready ? "Ready" : "Attention", "Unknown");
  setText(
    stateEls.diagQueue,
    diagnostics.in_progress_count ? `${diagnostics.in_progress_count} in progress` : diagnostics.queue_active ? "Pending work" : "Idle",
    "Unknown"
  );
  setText(stateEls.diagEvent, diagnostics.latest_event_at ? formatTime(diagnostics.latest_event_at) : "No signal", "No signal");
  stateEls.diagWorker.className = `strip-value ${diagnostics.worker_connected ? "ready" : "error"}`;
  stateEls.diagReady.className = `strip-value ${diagnostics.ready ? "ready" : diagnostics.stale_in_progress?.length ? "error" : "warn"}`;
  stateEls.diagQueue.className = `strip-value ${diagnostics.queue_active ? "warn" : "ready"}`;
  stateEls.diagEvent.className = "strip-value";

  stateEls.queuePending.textContent = queue.pending ?? 0;
  stateEls.queueProgress.textContent = queue.in_progress ?? 0;
  stateEls.queueCompleted.textContent = queue.completed ?? 0;
  stateEls.queueFailed.textContent = queue.failed ?? 0;

  stateEls.metricTotal.textContent = metrics.tasks_total ?? 0;
  stateEls.metricCompleted.textContent = metrics.tasks_completed ?? 0;
  stateEls.metricFailed.textContent = metrics.tasks_failed ?? 0;
  stateEls.metricFallbacks.textContent = metrics.fallback_events ?? 0;
  stateEls.metricTools.textContent = metrics.tool_calls_total ?? 0;
  stateEls.metricToolFailures.textContent = metrics.tool_failures ?? 0;
  stateEls.metricAvgDuration.textContent = `${(metrics.average_duration_s ?? 0).toFixed(2)}s`;
  setText(stateEls.metricLastType, metrics.last_task_type, "Unknown");
  stateEls.lastUpdated.textContent = metrics.updated_at ? `Updated ${formatTime(metrics.updated_at)}` : "No data";

  renderEvents(snapshot.events || []);
  renderRecentTasks(snapshot.recent_tasks || []);
  renderNotes(snapshot.notes || { recent: [], count: 0 });
  renderRoutine(snapshot.routine || { blocks: [] });
  const agentGraph = snapshot.agent_graph || { nodes: [], edges: [] };
  const brainGraph = snapshot.second_brain_graph || { nodes: [], edges: [] };
  const agentSignature = graphSignature(agentGraph);
  const brainSignature = graphSignature(brainGraph);
  const agentUpdated = clientState.graphSignatures["graph-canvas"] && clientState.graphSignatures["graph-canvas"] !== agentSignature;
  const brainUpdated =
    clientState.graphSignatures["second-brain-graph-canvas"] &&
    clientState.graphSignatures["second-brain-graph-canvas"] !== brainSignature;
  clientState.graphSignatures["graph-canvas"] = agentSignature;
  clientState.graphSignatures["second-brain-graph-canvas"] = brainSignature;

  renderGraph(agentGraph, stateEls.graphCanvas, { updated: agentUpdated });
  renderGraph(brainGraph, stateEls.secondBrainGraphCanvas, { updated: brainUpdated });
}

async function loadSnapshot() {
  const response = await fetch("/api/snapshot");
  if (!response.ok) throw new Error("Failed to load HUD snapshot");
  renderSnapshot(await response.json());
}

function setStreamMode(mode, label) {
  stateEls.streamStatus.textContent = label;
  stateEls.streamIndicator.classList.toggle("live", mode === "live");
}

function disableWebSocket(reason) {
  clientState.wsEnabled = false;
  clientState.wsFailures = 0;
  if (clientState.socket) {
    try {
      clientState.socket.close();
    } catch {}
    clientState.socket = null;
  }
  setStreamMode("poll", reason || "POLL MODE");
  startPolling();
}

function startPolling() {
  if (clientState.pollInterval) return;
  setStreamMode("poll", "POLL MODE");
  loadSnapshot().catch((error) => console.error(error));
  clientState.pollInterval = window.setInterval(() => {
    loadSnapshot().catch((error) => console.error(error));
  }, 2000);
}

function stopPolling() {
  if (!clientState.pollInterval) return;
  window.clearInterval(clientState.pollInterval);
  clientState.pollInterval = null;
}

function connectWebSocket() {
  if (!clientState.wsEnabled) {
    startPolling();
    return;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws`);
  clientState.socket = socket;
  clientState.wsEverOpened = false;

  socket.addEventListener("open", () => {
    clientState.wsEverOpened = true;
    clientState.wsFailures = 0;
    stopPolling();
    setStreamMode("live", "LIVE LINK");
  });

  socket.addEventListener("message", (event) => {
    try {
      renderSnapshot(JSON.parse(event.data));
    } catch (error) {
      console.error(error);
    }
  });

  socket.addEventListener("close", () => {
    if (!clientState.wsEnabled) return;
    clientState.socket = null;
    if (!clientState.wsEverOpened) {
      clientState.wsFailures += 1;
      if (clientState.wsFailures >= 1) {
        disableWebSocket("POLL ONLY");
        return;
      }
    }
    setStreamMode("poll", "RECONNECTING");
    startPolling();
    window.setTimeout(() => {
      if (clientState.wsEnabled) connectWebSocket();
    }, 1500);
  });

  socket.addEventListener("error", () => {
    if (!clientState.wsEverOpened) {
      disableWebSocket("POLL ONLY");
      return;
    }
    socket.close();
  });
}

stateEls.taskForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = stateEls.taskInput.value.trim();
  if (!input) return;
  await fetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });
  stateEls.taskInput.value = "";
  await loadSnapshot();
});

stateEls.notesSearchButton.addEventListener("click", async () => {
  const result = await searchNotes(stateEls.notesSearch.value);
  clientState.notesMode = stateEls.notesSearch.value.trim() ? "search" : "recent";
  renderNotes(result);
});

stateEls.notesSearch.addEventListener("keydown", async (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    const result = await searchNotes(stateEls.notesSearch.value);
    clientState.notesMode = stateEls.notesSearch.value.trim() ? "search" : "recent";
    renderNotes(result);
  }
});

stateEls.notesNewButton.addEventListener("click", () => {
  openNoteEditor();
});

stateEls.noteEditButton.addEventListener("click", () => {
  openNoteEditor(clientState.activeNote);
});

stateEls.noteEditorClose.addEventListener("click", closeNoteEditor);
stateEls.noteEditorSave.addEventListener("click", () => {
  saveNoteFromEditor().catch((error) => console.error(error));
});
stateEls.noteEditorModal.addEventListener("click", (event) => {
  if (event.target === stateEls.noteEditorModal) {
    closeNoteEditor();
  }
});

stateEls.clearEvents.addEventListener("click", async () => {
  await fetch("/api/events/clear", { method: "POST" });
  await loadSnapshot();
});

stateEls.clearFocus.addEventListener("click", () => {
  clientState.focusedTaskId = null;
  renderEvents(clientState.snapshot?.events || []);
});

stateEls.eventLimit.addEventListener("input", () => {
  clientState.eventLimit = Number(stateEls.eventLimit.value);
  stateEls.eventLimitValue.textContent = `${clientState.eventLimit} events`;
  renderEvents(clientState.snapshot?.events || []);
});

stateEls.eventFilters.addEventListener("click", (event) => {
  const target = event.target.closest(".filter-chip");
  if (!target) return;
  clientState.filter = target.dataset.filter || "all";
  stateEls.eventFilters.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.remove("active"));
  target.classList.add("active");
  renderEvents(clientState.snapshot?.events || []);
});

stateEls.drawerPlayback.addEventListener("input", renderDrawerTimeline);
stateEls.closeDrawer.addEventListener("click", closeTaskDrawer);
stateEls.closeNoteDrawer.addEventListener("click", closeNoteDrawer);
stateEls.drawerBackdrop.addEventListener("click", () => {
  closeTaskDrawer();
  closeNoteDrawer();
});
document.querySelectorAll(".graph-reset").forEach((button) => {
  button.addEventListener("click", () => {
    resetGraphViewport(button.dataset.graphTarget);
  });
});
document.querySelectorAll(".graph-expand").forEach((button) => {
  button.addEventListener("click", () => {
    openGraphModal(button.dataset.graphPanel, button.dataset.graphName);
  });
});
stateEls.graphModalClose.addEventListener("click", closeGraphModal);
stateEls.graphModal.addEventListener("click", (event) => {
  if (event.target === stateEls.graphModal) {
    closeGraphModal();
  }
});
stateEls.graphModalReset.addEventListener("click", () => {
  const panel = clientState.expandedGraph?.panelId;
  if (!panel) return;
  const svg = document.getElementById(panel)?.querySelector("svg");
  if (svg) resetGraphViewport(svg.id);
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeTaskDrawer();
    closeNoteDrawer();
    closeGraphModal();
    closeNoteEditor();
  }
});

tickClock();
window.setInterval(tickClock, 1000);
stateEls.eventLimitValue.textContent = `${clientState.eventLimit} events`;
if (stateEls.voiceToggle) {
  stateEls.voiceToggle.addEventListener("click", () => {
    armVoiceMode().catch((error) => console.error(error));
  });
  const params = new URLSearchParams(window.location.search);
  if (params.get("voice") === "1") {
    armVoiceMode().catch((error) => console.error(error));
  } else {
    updateVoiceStatus("Standby", false);
    stateEls.voiceTranscript.textContent = "Voice console ready. Arm clap wake when you want Jarvis listening.";
  }
}
startPolling();
if (clientState.wsEnabled) connectWebSocket();
