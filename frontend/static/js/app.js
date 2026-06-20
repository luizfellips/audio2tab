const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const selectedFileEl = document.getElementById("selected-file");
const transcribeBtn = document.getElementById("transcribe-btn");
const clearBtn = document.getElementById("clear-btn");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const tabPreviewEl = document.getElementById("tab-preview");
const tabPlayerWrapEl = document.getElementById("tab-player-wrap");
const noteLineEl = document.getElementById("note-line");
const noteCountEl = document.getElementById("note-count");
const downloadLinksEl = document.getElementById("download-links");
const playbackEl = document.getElementById("playback");
const playBtn = document.getElementById("play-btn");
const pauseBtn = document.getElementById("pause-btn");
const stopBtn = document.getElementById("stop-btn");
const progressTrack = document.getElementById("progress-track");
const progressBar = document.getElementById("progress-bar");
const playbackTimeEl = document.getElementById("playback-time");

let selectedFile = null;
const tabPlayer = new TabPlayer();
const noteLineView = new NoteLineView(noteLineEl);
const tabPlayhead = new TabPlayhead(tabPlayerWrapEl, tabPreviewEl);

function basename(path) {
  return path.split(/[/\\]/).pop();
}

function formatTime(seconds) {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

function setStatus(message, type) {
  statusEl.hidden = false;
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
}

function clearStatus() {
  statusEl.hidden = true;
  statusEl.textContent = "";
  statusEl.className = "status";
}

function updatePlaybackUi(elapsedSeconds = 0) {
  const ratio = tabPlayer.totalDuration > 0 ? elapsedSeconds / tabPlayer.totalDuration : 0;
  progressBar.style.width = `${ratio * 100}%`;
  playbackTimeEl.textContent = `${formatTime(elapsedSeconds)} / ${formatTime(tabPlayer.totalDuration)}`;
  if (progressTrack) {
    progressTrack.setAttribute("aria-valuenow", String(Math.round(ratio * 100)));
  }
  tabPlayhead.updatePlayback(elapsedSeconds);
  noteLineView.updatePlayback(elapsedSeconds);
}

function syncTransportButtons({ playing, currentTime }) {
  const hasNotes = tabPlayer.positions.length > 0;
  const atStart = currentTime <= 0.01;
  const atEnd = currentTime >= tabPlayer.totalDuration - 0.05;

  playBtn.disabled = !hasNotes || playing;
  pauseBtn.disabled = !playing;
  stopBtn.disabled = !hasNotes || (atStart && !playing);
  playBtn.classList.toggle("is-playing", playing);
}

function setPlaybackControls(enabled) {
  playbackEl.hidden = !enabled;
  if (!enabled) {
    playBtn.disabled = true;
    pauseBtn.disabled = true;
    stopBtn.disabled = true;
    return;
  }
  syncTransportButtons({ playing: false, currentTime: 0 });
}

tabPlayer.onProgress = (elapsedSeconds) => updatePlaybackUi(elapsedSeconds);
tabPlayer.onStateChange = (state) => {
  syncTransportButtons(state);
  if (!state.playing && state.currentTime <= 0.01) {
    tabPlayhead.resetPlayback();
    noteLineView.resetPlayback();
  } else if (!state.playing && state.currentTime > 0.01) {
    updatePlaybackUi(state.currentTime);
  }
};

function setSelectedFile(file) {
  if (!file) {
    selectedFile = null;
    selectedFileEl.hidden = true;
    selectedFileEl.textContent = "";
    transcribeBtn.disabled = true;
    clearBtn.hidden = true;
    tabPlayer.stop();
    setPlaybackControls(false);
    return;
  }

  if (!file.name.toLowerCase().endsWith(".mp3")) {
    setStatus("Please select an MP3 file.", "error");
    return;
  }

  selectedFile = file;
  selectedFileEl.hidden = false;
  selectedFileEl.textContent = file.name;
  transcribeBtn.disabled = false;
  clearBtn.hidden = false;
  clearStatus();
  resultsEl.hidden = true;
  tabPlayer.stop();
  setPlaybackControls(false);
}

function buildDownloadLink(label, filename) {
  const link = document.createElement("a");
  link.href = `/api/outputs/${encodeURIComponent(filename)}`;
  link.textContent = label;
  link.download = filename;
  return link;
}

async function fetchOutputText(filename) {
  const response = await fetch(`/api/outputs/${encodeURIComponent(filename)}`);
  if (!response.ok) {
    throw new Error(`Could not load ${filename}.`);
  }
  return response.text();
}

async function fetchOutputJson(filename) {
  const response = await fetch(`/api/outputs/${encodeURIComponent(filename)}`);
  if (!response.ok) {
    throw new Error(`Could not load ${filename}.`);
  }
  return response.json();
}

function renderResults(data, tabContent, positions) {
  noteCountEl.textContent = `${data.mapped_note_count} mapped · ${data.note_count} kept · ${data.raw_note_count} raw`;

  if (tabPreviewEl) {
    tabPreviewEl.textContent = tabContent || "(empty tab)";
  }
  noteLineView.load(positions);
  tabPlayhead.load(positions);

  downloadLinksEl.replaceChildren();
  const files = [
    ["TAB", data.tab_file],
    ["MIDI", data.midi_file],
    ["Notes JSON", data.notes_file],
    ["Positions JSON", data.positions_file],
  ];

  for (const [label, path] of files) {
    const filename = basename(path);
    downloadLinksEl.appendChild(buildDownloadLink(`${label} · ${filename}`, filename));
  }

  const hasPlayableNotes = tabPlayer.load(positions);
  setPlaybackControls(hasPlayableNotes);
  updatePlaybackUi(0);
  syncTransportButtons({ playing: false, currentTime: 0 });

  resultsEl.hidden = false;
  resultsEl.scrollIntoView({ behavior: "smooth", block: "nearest" });

  if (data.skipped_notes?.length) {
    const uniqueSkipped = [...new Set(data.skipped_notes)];
    setStatus(
      `Tab generated. Skipped ${uniqueSkipped.length} out-of-range note(s): ${uniqueSkipped.join(", ")}`,
      "success",
    );
  }
}

async function transcribe() {
  if (!selectedFile) {
    return;
  }

  transcribeBtn.disabled = true;
  tabPlayer.stop();
  setStatus("Transcribing audio — this may take up to a minute…", "loading");
  resultsEl.hidden = true;
  setPlaybackControls(false);

  const formData = new FormData();
  formData.append("audio_file", selectedFile);

  try {
    const response = await fetch("/transcribe", {
      method: "POST",
      body: formData,
    });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      const detail = payload.detail || "Transcription failed.";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }

    const tabFilename = basename(payload.tab_file);
    const positionsFilename = basename(payload.positions_file);

    const [tabContent, positions] = await Promise.all([
      fetchOutputText(tabFilename),
      fetchOutputJson(positionsFilename),
    ]);

    renderResults(payload, tabContent, positions);
    if (!payload.skipped_notes?.length) {
      setStatus("Tablature generated successfully. Press Play to hear it.", "success");
    }
  } catch (error) {
    setStatus(error.message || "Something went wrong.", "error");
  } finally {
    transcribeBtn.disabled = !selectedFile;
  }
}

dropZone.addEventListener("click", () => fileInput.click());

dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  if (file) {
    setSelectedFile(file);
  }
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragover");
  const file = event.dataTransfer?.files?.[0];
  if (file) {
    setSelectedFile(file);
  }
});

transcribeBtn.addEventListener("click", transcribe);

playBtn.addEventListener("click", () => {
  tabPlayer.play();
});

pauseBtn.addEventListener("click", () => {
  tabPlayer.pause();
});

stopBtn.addEventListener("click", () => {
  tabPlayer.stop();
});

function seekRatioFromClientX(clientX, scrubbing = false) {
  if (!progressTrack || tabPlayer.totalDuration <= 0) {
    return;
  }
  const rect = progressTrack.getBoundingClientRect();
  if (rect.width <= 0) {
    return;
  }
  const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
  if (scrubbing) {
    tabPlayer.scrubToRatio(ratio);
  } else {
    tabPlayer.seekRatio(ratio);
  }
}

if (progressTrack) {
  progressTrack.addEventListener("keydown", (event) => {
    if (!tabPlayer.positions.length) {
      return;
    }
    const step = tabPlayer.totalDuration * 0.05;
    if (event.key === "ArrowRight") {
      event.preventDefault();
      tabPlayer.seek(tabPlayer.currentTime + step);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      tabPlayer.seek(tabPlayer.currentTime - step);
    }
  });

  let scrubbing = false;

  progressTrack.addEventListener("pointerdown", (event) => {
    if (!tabPlayer.positions.length) {
      return;
    }
    scrubbing = true;
    tabPlayer.beginScrub();
    progressTrack.setPointerCapture(event.pointerId);
    seekRatioFromClientX(event.clientX, true);
  });

  progressTrack.addEventListener("pointermove", (event) => {
    if (!scrubbing) {
      return;
    }
    seekRatioFromClientX(event.clientX, true);
  });

  const endScrub = (event) => {
    if (!scrubbing) {
      return;
    }
    scrubbing = false;
    if (event?.pointerId !== undefined) {
      progressTrack.releasePointerCapture(event.pointerId);
    }
    tabPlayer.endScrub();
  };

  progressTrack.addEventListener("pointerup", endScrub);
  progressTrack.addEventListener("pointercancel", endScrub);
}

clearBtn.addEventListener("click", () => {
  fileInput.value = "";
  setSelectedFile(null);
  clearStatus();
  resultsEl.hidden = true;
  if (tabPreviewEl) {
    tabPreviewEl.textContent = "";
  }
  noteLineView.load([]);
  tabPlayhead.load([]);
});
