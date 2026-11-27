const transcript = document.querySelector("#transcript");
const language = document.querySelector("#language");
const recordButton = document.querySelector("#recordButton");
const recordLabel = document.querySelector("#recordLabel");
const status = document.querySelector("#status");
const saveButton = document.querySelector("#saveButton");
const historyList = document.querySelector("#historyList");
const browserWarning = document.querySelector("#browserWarning");
const waveStage = document.querySelector("#waveStage");
const waveform = document.querySelector("#waveform");
const copyButton = document.querySelector("#copyButton");
const speakButton = document.querySelector("#speakButton");
const clearButton = document.querySelector("#clearButton");
const searchInput = document.querySelector("#searchInput");
const exportButton = document.querySelector("#exportButton");
const themeButton = document.querySelector("#themeButton");

let allItems = [];

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let recognitionEndResolver = null;
let listening = false;
let finalTranscript = "";
let recognizedTranscript = "";
let shouldListen = false;
let microphoneStream = null;
let mediaRecorder = null;
let recordedChunks = [];
let speechServiceUnavailable = !Recognition;
let audioContext = null;
let audioAnalyser = null;
let meterFrame = null;
let recordingStartedAt = 0;

if (!Recognition) {
  browserWarning.hidden = false;
  browserWarning.textContent =
    "Live recognition is unavailable. Audio will be transcribed after you stop recording.";
}

waveform.innerHTML = Array.from({ length: 46 }, () => "<i></i>").join("");

function setListening(value) {
  listening = value;
  recordButton.classList.toggle("listening", value);
  recordLabel.textContent = value ? "Stop recording" : "Start recording";
  if (value) status.textContent = "Listening...";
  waveStage.classList.toggle("listening", value);
  updateTranscriptState();
}

function updateTranscriptState() {
  const hasText = transcript.value.trim().length > 0;
  saveButton.disabled = listening || !hasText;
  copyButton.disabled = !hasText;
  speakButton.disabled = !hasText;
  clearButton.disabled = !hasText;
}

function startAudioMeter(stream) {
  const AudioContextConstructor = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextConstructor) return;
  audioContext = new AudioContextConstructor();
  const source = audioContext.createMediaStreamSource(stream);
  audioAnalyser = audioContext.createAnalyser();
  audioAnalyser.fftSize = 128;
  source.connect(audioAnalyser);
  const levels = new Uint8Array(audioAnalyser.frequencyBinCount);

  const bars = waveform.querySelectorAll("i");
  const drawMeter = () => {
    audioAnalyser.getByteFrequencyData(levels);
    let average = levels.reduce((sum, value) => sum + value, 0) / levels.length;
    bars.forEach((bar, index) => {
      const level = Math.max(7, Math.min(48, average * (0.55 + (index % 7) * 0.08)));
      bar.style.height = `${level}px`;
    });
    meterFrame = requestAnimationFrame(drawMeter);
  };
  drawMeter();
}

function stopAudioMeter() {
  if (meterFrame) cancelAnimationFrame(meterFrame);
  meterFrame = null;
  waveform.querySelectorAll("i").forEach((bar) => bar.style.removeProperty("height"));
  if (audioContext && audioContext.state !== "closed") audioContext.close();
  audioContext = null;
  audioAnalyser = null;
}

function startLocalRecording() {
  if (!window.MediaRecorder || !microphoneStream) return false;
  recordedChunks = [];
  const preferredType = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4"
  ].find((type) => MediaRecorder.isTypeSupported(type));

  mediaRecorder = preferredType
    ? new MediaRecorder(microphoneStream, { mimeType: preferredType })
    : new MediaRecorder(microphoneStream);
  mediaRecorder.ondataavailable = (event) => {
    if (event.data.size) recordedChunks.push(event.data);
  };
  mediaRecorder.start(1000);
  recordingStartedAt = Date.now();
  return true;
}

async function stopLocalRecording() {
  if (!mediaRecorder) return null;
  if (mediaRecorder.state !== "inactive") {
    const stopped = new Promise((resolve) => {
      mediaRecorder.onstop = resolve;
    });
    mediaRecorder.stop();
    await stopped;
  }

  if (!recordedChunks.length) return null;
  return new Blob(recordedChunks, {
    type: mediaRecorder.mimeType || "audio/webm"
  });
}

async function transcribeRecordedAudio() {
  if (!mediaRecorder) {
    status.textContent =
      "No speech was captured, and local audio transcription is unavailable";
    return;
  }
  status.textContent = "Transcribing locally...";
  transcript.value = finalTranscript;
  updateTranscriptState();
  const blob = await stopLocalRecording();
  if (!blob) {
    status.textContent = "No audio recorded";
    return;
  }

  const form = new FormData();
  const filename = blob.type.includes("mp4") ? "recording.mp4" : "recording.webm";
  form.append("audio", blob, filename);
  form.append("language", language.value);

  try {
    const response = await fetch("/api/transcribe", {
      method: "POST",
      body: form
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Transcription failed");

    const separator = transcript.value.trim() ? " " : "";
    transcript.value += separator + result.text;
    finalTranscript = transcript.value;
    updateTranscriptState();
    status.textContent = "Local transcription complete";
  } catch (error) {
    status.textContent = error.message;
  }
}

function startBrowserRecognition() {
  if (!Recognition) return;

  recognition = new Recognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = language.value;
  recognition.onresult = (event) => {
    let interimTranscript = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index];
      const text = result[0].transcript.trim();
      if (result.isFinal && text) {
        recognizedTranscript = [recognizedTranscript, text].filter(Boolean).join(" ");
        finalTranscript = [finalTranscript, text].filter(Boolean).join(" ");
      } else {
        interimTranscript = [interimTranscript, text].filter(Boolean).join(" ");
      }
    }
    transcript.value = [finalTranscript, interimTranscript].filter(Boolean).join(" ");
    updateTranscriptState();
  };
  recognition.onerror = (event) => {
    if (!shouldListen || event.error === "no-speech") return;
    speechServiceUnavailable = true;
    browserWarning.hidden = false;
    browserWarning.textContent =
      `Live recognition unavailable (${event.error}). The recording will use local transcription when you stop.`;
    status.textContent = "Live recognition unavailable; audio is still recording";
  };
  recognition.onend = () => {
    if (!shouldListen) {
      if (recognitionEndResolver) recognitionEndResolver();
      recognitionEndResolver = null;
      return;
    }
    if (speechServiceUnavailable) return;
    try {
      recognition.start();
    } catch (error) {
      speechServiceUnavailable = true;
      status.textContent = `Live recognition stopped: ${error.message}`;
    }
  };

  try {
    recognition.start();
  } catch (error) {
    speechServiceUnavailable = true;
    browserWarning.hidden = false;
    browserWarning.textContent =
      `Live recognition unavailable (${error.message}). The recording will use local transcription when you stop.`;
  }
}

async function stopBrowserRecognition() {
  if (!recognition) return;
  const ended = new Promise((resolve) => {
    recognitionEndResolver = resolve;
  });
  try {
    recognition.stop();
  } catch (error) {
    recognitionEndResolver = null;
    status.textContent = `Unable to stop live recognition: ${error.message}`;
    return;
  }
  await Promise.race([
    ended,
    new Promise((resolve) => setTimeout(resolve, 1500))
  ]);
  recognitionEndResolver = null;
}

recordButton.addEventListener("click", async () => {
  if (listening) {
    shouldListen = false;
    await stopBrowserRecognition();

    const elapsed = Date.now() - recordingStartedAt;
    if (mediaRecorder && mediaRecorder.state !== "inactive" && elapsed < 1200) {
      await new Promise((resolve) => setTimeout(resolve, 1200 - elapsed));
    }

    try {
      if (!recognizedTranscript) {
        await transcribeRecordedAudio();
      } else {
        await stopLocalRecording();
        status.textContent = "Live transcription complete";
      }
    } catch (error) {
      status.textContent = `Unable to finish recording: ${error.message}`;
    } finally {
      stopAudioMeter();
      if (microphoneStream) {
        microphoneStream.getTracks().forEach((track) => track.stop());
        microphoneStream = null;
      }
      setListening(false);
    }
    return;
  }

  if (!Recognition && (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia)) {
    status.textContent = "This browser does not support microphone recording";
    return;
  }

  speechServiceUnavailable = !Recognition;
  recognizedTranscript = "";
  finalTranscript = transcript.value.trim();
  recordingStartedAt = Date.now();

  if (window.MediaRecorder && navigator.mediaDevices?.getUserMedia) {
    try {
      status.textContent = "Allow microphone access...";
      microphoneStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      if (startLocalRecording()) {
        try {
          startAudioMeter(microphoneStream);
        } catch (error) {
          status.textContent = `Audio meter unavailable: ${error.message}`;
        }
      }
    } catch (error) {
      if (microphoneStream) {
        microphoneStream.getTracks().forEach((track) => track.stop());
        microphoneStream = null;
      }
      if (!Recognition) {
        status.textContent =
          error.name === "NotAllowedError"
            ? "Microphone permission denied"
            : "Microphone unavailable";
        browserWarning.hidden = false;
        browserWarning.textContent =
          "Allow microphone access in the browser address bar, then try again.";
        return;
      }
      browserWarning.hidden = false;
      browserWarning.textContent =
        "Local recording fallback is unavailable. Browser live recognition will still be attempted.";
      microphoneStream = null;
    }
  }

  shouldListen = true;
  setListening(true);
  if (Recognition) {
    browserWarning.hidden = Boolean(microphoneStream);
    if (!microphoneStream) {
      browserWarning.textContent =
        "Local audio fallback is unavailable. Browser live recognition will still be attempted.";
    }
    status.textContent = "Listening — speak naturally";
    startBrowserRecognition();
  } else {
    status.textContent = "Recording — speak naturally";
  }
});

language.addEventListener("change", () => {
  if (listening && recognition) {
    recognition.lang = language.value;
    recognition.stop();
  }
});
transcript.addEventListener("input", updateTranscriptState);

async function loadHistory() {
  try {
    const response = await fetch("/api/transcriptions");
    if (!response.ok) throw new Error(`Could not load history (${response.status})`);
    const items = await response.json();
    if (!Array.isArray(items)) throw new Error("The history response was invalid");
    allItems = items;
    renderHistory();
    updateMetrics(items);
  } catch (error) {
    allItems = [];
    renderHistory();
    historyList.innerHTML =
      `<div class="empty">${escapeHtml(error.message)}</div>`;
    status.textContent = `Unable to load history: ${error.message}`;
  }
}

function updateMetrics(items) {
  const words = items.reduce((total, item) =>
    total + item.text.trim().split(/\s+/).filter(Boolean).length, 0);
  const languages = new Set(items.map((item) => item.language)).size;
  document.querySelector("#metricCount").textContent = items.length;
  document.querySelector("#metricWords").textContent = words;
  document.querySelector("#metricLanguages").textContent = languages;
  document.querySelector("#wordCount").textContent = words;
  document.querySelector("#wordProgress").textContent =
    words ? `${words} words captured` : "Personal workspace";
}

function renderHistory() {
  const query = searchInput.value.trim().toLowerCase();
  const items = allItems.filter((item) =>
    item.text.toLowerCase().includes(query) ||
    item.language.toLowerCase().includes(query));

  if (!items.length) {
    historyList.innerHTML = `<div class="empty">${query ? "No matching transcriptions" : "No saved transcriptions yet"}</div>`;
    return;
  }

  historyList.innerHTML = items.map((item) => `
    <article class="item" data-id="${item.id}">
      <div class="item-top">
        <span class="item-meta">${escapeHtml(item.language)} · ${formatDate(item.created_at)}</span>
        <div class="item-actions">
            <button class="icon-button edit" type="button" title="Edit">✎</button>
            <button class="icon-button delete" type="button" title="Delete">×</button>
        </div>
      </div>
      <div class="item-text">${escapeHtml(item.text)}</div>
    </article>
  `).join("");
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

function formatDate(value) {
  return new Date(value).toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short"
  });
}

saveButton.addEventListener("click", async () => {
  const text = transcript.value.trim();
  if (!text) return;
  saveButton.disabled = true;
  try {
    const response = await fetch("/api/transcriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language: language.value })
    });
    await ensureSuccess(response, "Unable to save transcription");
    transcript.value = "";
    finalTranscript = "";
    recognizedTranscript = "";
    updateTranscriptState();
    await loadHistory();
  } catch (error) {
    status.textContent = error.message;
    updateTranscriptState();
  }
});

historyList.addEventListener("click", async (event) => {
  const item = event.target.closest(".item");
  if (!item) return;
  const id = item.dataset.id;
  const button = event.target.closest("button");
  if (!button) return;

  if (button.classList.contains("edit")) {
    const textElement = item.querySelector(".item-text");
    const text = textElement.textContent;
    const meta = item.querySelector(".item-meta").textContent.split(" · ")[0];
    textElement.outerHTML = `
      <textarea class="edit-text">${escapeHtml(text)}</textarea>
      <select class="edit-language">
        ${languageOptions(meta)}
      </select>
      <div class="edit-actions">
        <button class="cancel-edit" type="button">Cancel</button>
        <button class="save-edit" type="button">Save</button>
      </div>
    `;
  }

  try {
    if (button.classList.contains("delete")) {
      const response = await fetch(`/api/transcriptions/${id}`, { method: "DELETE" });
      await ensureSuccess(response, "Unable to delete transcription");
      await loadHistory();
    }

    if (button.classList.contains("cancel-edit")) await loadHistory();

    if (button.classList.contains("save-edit")) {
      const text = item.querySelector(".edit-text").value.trim();
      const selectedLanguage = item.querySelector(".edit-language").value;
      if (!text) {
        status.textContent = "Transcription text cannot be blank";
        return;
      }
      const response = await fetch(`/api/transcriptions/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language: selectedLanguage })
      });
      await ensureSuccess(response, "Unable to update transcription");
      await loadHistory();
    }
  } catch (error) {
    status.textContent = error.message;
  }
});

async function ensureSuccess(response, message) {
  if (response.ok) return;
  let detail = "";
  try {
    const body = await response.json();
    detail = body.detail || "";
  } catch (error) {
    detail = "";
  }
  throw new Error(detail || `${message} (${response.status})`);
}

function languageOptions(selected) {
  const options = [
    ["en-US", "English (US)"], ["hi-IN", "Hindi / Hinglish"],
    ["en-IN", "English (India)"], ["es-ES", "Spanish"], ["fr-FR", "French"]
  ];
  return options.map(([value, label]) =>
    `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`
  ).join("");
}

searchInput.addEventListener("input", renderHistory);

copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(transcript.value);
  copyButton.textContent = "Copied";
  setTimeout(() => copyButton.textContent = "Copy", 1200);
});

clearButton.addEventListener("click", () => {
  transcript.value = "";
  finalTranscript = "";
  updateTranscriptState();
});

speakButton.addEventListener("click", () => {
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(transcript.value);
  utterance.lang = language.value;
  speechSynthesis.speak(utterance);
});

exportButton.addEventListener("click", () => {
  const content = allItems.map((item) =>
    `[${item.created_at}] ${item.language}\n${item.text}`
  ).join("\n\n");
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "voxly-transcriptions.txt";
  anchor.click();
  URL.revokeObjectURL(url);
});

themeButton.addEventListener("click", () => {
  document.body.classList.toggle("dark");
  localStorage.setItem("voxly-theme",
    document.body.classList.contains("dark") ? "dark" : "light");
});

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((item) =>
      item.classList.remove("active"));
    button.classList.add("active");
    if (button.dataset.view === "history") {
      document.querySelector("#historyCard").scrollIntoView({ behavior: "smooth" });
      searchInput.focus();
    }
  });
});

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    if (!saveButton.disabled) saveButton.click();
  }
});

if (localStorage.getItem("voxly-theme") === "dark") {
  document.body.classList.add("dark");
}

loadHistory();
