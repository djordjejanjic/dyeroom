"use strict";

const $ = (id) => document.getElementById(id);
const VIEW_NAMES = { lightbox: "light box", projector: "projector" };
const FILTER_NAMES = {
  auto: "Chosen for the light", none: "None",
  "80A": "80A · blue, tungsten lamps", "80B": "80B · blue, photofloods", "80C": "80C · blue, warm lamps",
  "80D": "80D · light blue, early sun", "82C": "82C · pale blue, warm light", "82B": "82B · pale blue",
  "82A": "82A · faint blue, late sun", "81A": "81A · faint amber, cloud", "81B": "81B · light amber, shade",
  "81C": "81C · amber, deep shade", "81EF": "81EF · strong amber, cold light", "85B": "85B · orange, strong warm cast",
};
const PHASE_TEXT = {
  scan: ["Reading the photograph", "The raw file, as the sensor recorded it"],
  expose: ["Exposing the film", "Light reaches the three layers of the emulsion"],
  develop: ["First developer", "A black-and-white negative forms in every layer"],
  dyes: ["Reversal and colour developers", ""],
  bleach: ["Bleach and fix", "The silver is washed away; only the dyes remain"],
  light: ["On the light box", "The finished slide"],
};
const DYE_TEXT = { cyan: "Cyan dye, in the red-sensitive layer", yellow: "Yellow dye, in the blue-sensitive layer",
                   magenta: "Magenta dye, in the green-sensitive layer" };
// Monday 400: a black-and-white negative, fixed, then enlarged onto paper.
const MONO = "monday400";
const PRINT_TEXT = {
  scan: ["Reading the photograph", "The raw file, as the sensor recorded it"],
  expose: ["Exposing the film", "Light reaches the silver halide crystals"],
  develop: ["In the developer", "A negative forms where the light fell"],
  stop: ["Stop bath", "Development halts"],
  fix: ["Fixer", "The silver halide no light reached dissolves, and the film clears"],
  wash: ["Wash", "The negative is washed and dried"],
  enlarger: ["Under the enlarger", "Light through the negative exposes the paper"],
  tray: ["In the print developer", "The picture comes up on the paper"],
  print: ["The print", "Fixed, washed and dried"],
};
const BW_FILTER_NAMES = {
  none: "None", "8": "8 · yellow, darker skies", "15": "15 · deep yellow, darker skies still",
  "25": "25 · red, dark skies, light reds", "11": "11 · yellow-green, foliage and skin", "58": "58 · green, light foliage",
};
const isMono = (s) => Boolean(s) && s.film === MONO;
// Development time as a darkroom worker writes it: 7¾, 10¾, 12½.
const devMinutes = (rating) => (options && options.development_minutes ? options.development_minutes[rating] : null);
function minutesText(m) {
  const q = Math.round(m * 4);
  return `${Math.floor(q / 4) || ""}${["", "¼", "½", "¾"][q % 4]}`;
}

// Every photograph has its own development settings, starting from these. The controls show and
// change those of the frame in view; with none in view, those the next photographs start from.
const DEFAULTS = { film: "sunday64", view: "lightbox", light: "native", filter: "auto", exposure: "camera", ev: 0,
                   size: "draft", grain: true, rating: 400, grade: 3, bw_filter: "none", toning: "none", format: "35mm",
                   sharpness: 0, clarity: 0 };
const fresh = { ...DEFAULTS };
let settings = fresh;
const FORMAT_NAMES = { "35mm": "35 mm", "645": "6×4.5", "6x6": "6×6", "6x7": "6×7" };
const FORMAT_LABELS = { "35mm": "35 mm", "645": "6×4.5 · 120 film", "6x6": "6×6 · 120 film", "6x7": "6×7 · 120 film" };
// The frame in millimetres (dyeroom/capture.py FORMATS), for the menu and its icons
const FORMAT_SIZES = { "35mm": [36, 24], "645": [56, 41.5], "6x6": [56, 56], "6x7": [69.5, 56] };
const items = [];
const uploadQueue = [];
let current = null;
let options = null;
let compare = "split";
let split = 50;
let activeUploads = 0;
let seq = 0;
let grader = null;
let graderBefore = null;  // the previous development, under the same adjustments
let lab = null;
let labJob = null;
let activeBand = "red";
let me = { accounts: false, signed_in: false };
let paddle = null;
let notice = null;
let presets = [];  // {id?, name, settings}: on the account when signed in, else in this browser
let activeTab = "develop";  // the tool open in the inspector (Develop, Colour, Tones, Crop)
let lastTab = "develop";    // where Return goes back to after cropping
let cropping = false;
let view = null;            // the picture on screen: {k: scale, W, H: turned size, W0, H0: as developed}
let zoom = { z: 1, u: 0.5, v: 0.5 };  // how far in, and the point of the picture at the frame's centre
let zoomFor = null;                   // the frame the zoom belongs to

// --- settings ----------------------------------------------------------------------------

function loadCompare() {
  try {
    compare = localStorage.getItem("dyeroom-compare") || "split";
    localStorage.removeItem("dyeroom-settings");  // kept once for every photograph alike
  } catch (_) { /* private mode or blocked storage: defaults are fine */ }
  if (!["split", "raw", "previous", "slide"].includes(compare)) compare = "split";
}

function saveCompare() {
  try { localStorage.setItem("dyeroom-compare", compare); } catch (_) { /* ignore */ }
}

// The controls follow the frame in view.
function followCurrent() {
  const target = current ? current.settings : fresh;
  if (settings === target) return;
  settings = target;
  syncControls();
}

// Thirds of a stop, as a photographer says them: +1/3, -2/3, +1 1/3.
function formatEv(v) {
  if (Math.abs(v) < 0.01) return "0";
  const sign = v > 0 ? "+" : "−";
  const thirds = Math.round(Math.abs(v) * 3);
  const whole = Math.floor(thirds / 3);
  const frac = ["", "1/3", "2/3"][thirds % 3];
  return sign + [whole || "", frac].filter(Boolean).join(" ");
}

const pad2 = (n) => String(n).padStart(2, "0");
const STAGE_WORDS = {
  "Reading the photograph": "Reading the raw", "Exposing the film": "Exposing the film",
  "First developer": "In the first developer", "Reversal and colour developers": "In the colour developers",
  "Viewing the slide": "Bleach, fix, light box", "Printing the files": "Finishing the files",
  "Finishing the files": "Finishing the files", "Developer": "In the developer", "Stop and fix": "Stop and fix",
  "Printing": "Enlarging and printing",
};

const signed = (v) => (v > 0 ? `+${v}` : v < 0 ? `−${Math.abs(v)}` : "0");

function syncControls() {
  document.querySelectorAll("#sect-develop [data-key]").forEach((b) => {
    b.setAttribute("aria-pressed", String(String(settings[b.dataset.key]) === b.dataset.value));
  });
  ["filter", "bw-filter", "format"].forEach(showDropdown);
  $("filter").querySelector("button").disabled = settings.light === "balanced";
  renderFilm();
  const mono = isMono(settings);
  document.querySelectorAll("#sect-develop [data-film]").forEach((el) => {
    el.hidden = (el.dataset.film === "mono") !== mono;
  });
  $("ev").value = Math.round(settings.ev * 3);
  $("ev-out").textContent = formatEv(settings.ev);
  for (const key of ["sharpness", "clarity"]) {
    $(key).value = settings[key];
    $(`${key}-out`).textContent = signed(settings[key]);
  }
  paintRanges();
  renderAgain();
}

// A slider's track is filled from zero to its value.
function paintRange(input) {
  const min = Number(input.min), max = Number(input.max), value = Number(input.value);
  const at = (v) => `${(100 * (Math.min(max, Math.max(min, v)) - min)) / (max - min)}%`;
  const zero = min < 0 && max > 0 ? 0 : min;
  input.style.setProperty("--a", at(Math.min(zero, value)));
  input.style.setProperty("--b", at(Math.max(zero, value)));
}

function paintRanges() {
  document.querySelectorAll('input[type="range"]').forEach(paintRange);
}

// "Develop again" lights up when the settings no longer match the frame's development; a frame
// not developed yet shows "Develop", lit.
function renderAgain() {
  const done = current && current.doneSettings;
  const first = Boolean(current) && !done;
  const changed = Boolean(done) && [...PRESET_KEYS, "size"].some((k) => String(done[k]) !== String(settings[k]));
  $("again").classList.toggle("primary", (first || changed) && !$("again").disabled);
  $("again").textContent = first ? "Develop" : changed ? "Develop with these settings" : "Develop again";
}

function bindControls() {
  document.querySelectorAll("#sect-develop [data-key]").forEach((b) => {
    b.addEventListener("click", () => {
      const value = b.dataset.value;
      settings[b.dataset.key] = value === "true" ? true : value === "false" ? false
        : /^\d+$/.test(value) ? Number(value) : value;
      syncControls();
    });
  });
  $("about-link").addEventListener("click", () => showSheet($("about")));
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => openTab(tab.dataset.tab)));
  $("ev").addEventListener("input", (e) => {
    settings.ev = Number(e.target.value) / 3;
    $("ev-out").textContent = formatEv(settings.ev);
    renderAgain();
  });
  $("ev").addEventListener("dblclick", () => { settings.ev = 0; syncControls(); });
  for (const key of ["sharpness", "clarity"]) {
    $(key).addEventListener("input", (e) => {
      settings[key] = Number(e.target.value);
      $(`${key}-out`).textContent = signed(settings[key]);
      renderAgain();
    });
    $(key).addEventListener("dblclick", () => { settings[key] = 0; syncControls(); });
  }
  $("again").addEventListener("click", () => { if (current && current.uploadId) develop(current); });
  $("develop-this").addEventListener("click", () => { if (current && current.state === "ready") develop(current); });
  $("develop-rest").addEventListener("click", developAll);
  $("develop-all").addEventListener("click", developAll);
  $("choose").addEventListener("click", () => (needsSignIn() ? openSignIn() : $("picker").click()));
  $("add").addEventListener("click", (e) => { if (needsSignIn()) { e.preventDefault(); openSignIn(); } });
  $("sign-in").addEventListener("click", openSignIn);
  $("account").addEventListener("click", openAccount);
  $("fact-film").addEventListener("click", () => (me.signed_in ? openFilm(false) : openSignIn()));
  $("working-buy").addEventListener("click", () => openFilm(true));
  $("get-colour").addEventListener("click", getColourising);
  // A black-and-white original turned away by the colour film: print it, or colourise it.
  $("as-print").addEventListener("click", () => {
    if (!current) return;
    settings.film = MONO;
    syncControls();
    develop(current);
  });
  $("as-colour").addEventListener("click", () => {
    if (!current) return;
    current.colourise = true;
    develop(current);
  });
  $("account-buy").addEventListener("click", () => { $("account-sheet").close(); openFilm(false); });
  document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));
  $("account-manage").addEventListener("click", manage);
  $("account-out").addEventListener("click", signOut);
  $("account-delete").addEventListener("click", deleteAccount);
  $("sample").addEventListener("click", trySample);
  $("export-jpg").addEventListener("click", () => exportFile($("export-jpg"), "jpg"));
  $("about-open").addEventListener("click", () => showSheet($("about")));
  document.querySelectorAll("[data-compare]").forEach((b) => {
    b.addEventListener("click", () => setCompare(b.dataset.compare));
  });
}

// --- files in --------------------------------------------------------------------------

function extension(name) {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot).toLowerCase();
}

function newItem(name) {
  const item = { key: ++seq, name, state: "uploading", uploadPct: 0, adjust: emptyAdjust(), settings: { ...fresh } };
  items.push(item);
  return item;
}

function addFiles(fileList) {
  if (needsSignIn()) { openSignIn(); return; }
  let room = filmLeft();
  let short = 0;
  const added = [];
  for (const file of fileList) {
    const item = newItem(file.name);
    added.push(item);
    if (options && !options.accepted.includes(extension(file.name))) {
      fail(item, `${extension(file.name) || "This file"} is not a raw or image format this can develop`);
    } else if (options && file.size > options.max_mb * 1024 * 1024) {
      fail(item, `Larger than ${options.max_mb} MB`);
    } else if (room <= 0) {  // kept here, and developed once there is film for it
      item.state = "checking";
      item.file = file;
      short++;
    } else {
      room--;
      item.reserved = true;
      uploadQueue.push([item, file]);
    }
  }
  if (added.length) current = added[0];
  pumpUploads();
  render();
  if (short) {
    checkFree(added.filter((i) => i.state === "checking")).then(() => {
      if (items.some((i) => i.state === "unpaid")) openFilm(true);
    });
  }
}

// A file this account has developed before costs nothing to add again: the browser hashes
// it (SHA-256, never sent anywhere but here) and asks before uploading.
async function sha256(file) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

async function checkFree(waiting) {
  let free = [];
  try {
    if (!(me.accounts && me.signed_in && window.crypto && crypto.subtle)) throw new Error("no check");
    for (const item of waiting) item.fingerprint = await sha256(item.file);
    const response = await fetch("/api/free", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fingerprints: waiting.map((i) => i.fingerprint) }),
    });
    if (response.ok) free = (await response.json()).free;
  } catch (_) { /* treat all as needing film */ }
  waiting.forEach((item, i) => {
    if (item.cleared) return;
    if (free[i]) {
      item.state = "uploading";
      item.uploadPct = 0;
      uploadQueue.push([item, item.file]);
    } else {
      item.state = "unpaid";
    }
  });
  pumpUploads();
  render();
}

async function trySample() {
  const item = newItem("sample");
  item.sample = true;  // a demonstration: not counted towards asking for a coffee
  current = item;
  render();
  try {
    const response = await fetch("/api/sample", { method: "POST" });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || response.statusText);
    item.uploadId = body.upload_id;
    item.name = body.name;
    develop(item);
  } catch (e) {  // refused before there is anything to show: say why, and leave no empty frame
    removeFrame(item);
    setNotice(e.message);
  }
}

function pumpUploads() {
  while (activeUploads < 2 && uploadQueue.length) {
    const [item, file] = uploadQueue.shift();
    activeUploads++;
    upload(item, file);
  }
}

function upload(item, file) {
  const done = () => { activeUploads--; pumpUploads(); };
  const progress = (loaded) => { item.uploadPct = Math.min(100, Math.round((100 * loaded) / file.size)); renderSoon(); };
  const parts = file.size > ((options && options.part_mb) || 32) * 1024 * 1024;
  (parts ? uploadInParts(item, file, progress) : uploadWhole(item, file, progress)).then(
    (reply) => { done(); uploaded(item, file, reply); },
    () => { done(); item.reserved = false; fail(item, "The upload was interrupted"); });
}

// One request, with the upload's progress: { status, text, retryAfter }.
function send(method, url, body = null, headers = {}, onProgress = null) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url);
    Object.entries(headers).forEach(([name, value]) => xhr.setRequestHeader(name, value));
    if (onProgress) xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded); };
    xhr.onload = () => resolve({ status: xhr.status, text: xhr.responseText, retryAfter: xhr.getResponseHeader("Retry-After") });
    xhr.onerror = () => reject(new Error("interrupted"));
    xhr.send(body);
  });
}

function uploadWhole(item, file, progress) {
  const form = new FormData();
  form.append("file", file);
  return send("POST", "/api/uploads", form, item.fingerprint ? { "X-Fingerprint": item.fingerprint } : {}, progress);
}

// A large photograph goes up in parts, each small enough for any proxy on the way; a dropped
// connection sends one part again, not the whole file.
async function uploadInParts(item, file, progress) {
  const start = await send("POST", "/api/uploads/start",
    JSON.stringify({ name: file.name, bytes: file.size, fingerprint: item.fingerprint || "" }),
    { "Content-Type": "application/json" });
  if (start.status !== 200) return start;  // refused before anything was sent: same answers as a whole upload
  const { upload_id: id, part_bytes: size } = JSON.parse(start.text);
  for (let index = 0, sent = 0; sent < file.size; index++) {
    if (item.cleared) { forgetUploads([id]); return { status: 0, cleared: true }; }
    const part = file.slice(sent, sent + size);
    for (let attempt = 1; ; attempt++) {
      let reply = null;
      try {
        reply = await send("PUT", `/api/uploads/${id}/${index}`, part, {}, (loaded) => progress(sent + loaded));
      } catch (_) { /* the connection dropped: try this part again */ }
      if (reply && reply.status === 200) break;
      if (reply && reply.status < 500) return reply;
      if (attempt === 4) throw new Error("interrupted");
      await new Promise((resolve) => setTimeout(resolve, 1500 * attempt));
    }
    sent += part.size;
  }
  return send("POST", `/api/uploads/${id}/finish`);
}

// What the server said to a photograph coming in, whole or in parts.
function uploaded(item, file, reply) {
  if (reply.cleared) return;
  if (reply.status === 200) {
    item.uploadId = JSON.parse(reply.text).upload_id;
    item.file = null;
    if (item.cleared) { forgetUploads([item.uploadId]); return; }
    fetchPreview(item);
    if (item.developWhenIn) {
      develop(item);
    } else {  // it waits for its settings and the photographer's word
      item.state = "ready";
      render();
    }
  } else if (reply.status === 402) {
    outOfFilm(item, file);
  } else if (reply.status === 429 || reply.status === 503) {  // a fair-use limit, or the lab is full: wait
    item.uploadPct = 0;
    item.held = errorText(reply.text, reply.status);
    render();
    later(reply.retryAfter, () => {
      if (item.cleared) return;
      item.held = null;
      uploadQueue.unshift([item, file]);
      pumpUploads();
    });
  } else {
    item.reserved = false;
    fail(item, errorText(reply.text, reply.status));
    if (reply.status === 401) refreshMe().then(openSignIn);
  }
}

// The photograph as it came in, small, made by the server in the moments after: shown until it
// is developed. Asked for until it is there (202 while it is being made); none for some files.
async function fetchPreview(item, tries = 0) {
  if (item.cleared || !item.uploadId || item.preview) return;
  let reply = null;
  try { reply = await fetch(`/api/uploads/${item.uploadId}/preview.jpg`); } catch (_) { /* try again */ }
  if (reply && reply.status === 200) {
    item.preview = `/api/uploads/${item.uploadId}/preview.jpg`;
    renderSoon();
  } else if (!(reply && reply.status === 404) && tries < 90) {
    setTimeout(() => fetchPreview(item, tries + 1), 1000);
  }
}

// Try again once the server says there is room (Retry-After, in seconds), at least after 5 s.
function later(retryAfter, again) {
  const seconds = Math.min(3600, Math.max(5, Number(retryAfter) || 30));
  setTimeout(again, seconds * 1000);
}

function errorText(body, status) {
  try { return JSON.parse(body).detail || `Error ${status}`; } catch (_) { return `Error ${status}`; }
}

function fail(item, message) {
  item.state = "failed";
  item.error = message;
  item.errorCode = null;
  render();
}

// --- developing --------------------------------------------------------------------------

// Frames in the lab not yet developed, or on their way in and not yet asked for.
const toDevelop = () => items.filter((i) => i.state === "ready" || (i.state === "uploading" && !i.developWhenIn));

// Every frame not yet developed goes to the developer with its own settings; one still on its
// way in goes as soon as it arrives.
function developAll() {
  for (const item of toDevelop()) {
    if (item.state === "ready") develop(item);
    else item.developWhenIn = true;
  }
  render();
}

async function develop(item) {
  if (item.cleared) return;
  item.state = "queued";
  item.error = null;
  item.stage = 0;
  item.early = false;
  item.pendingSettings = { ...item.settings, colourise: Boolean(item.colourise) };
  render();
  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ upload_id: item.uploadId, ...item.pendingSettings }),
    });
    const body = await response.json();
    if (response.status === 402) { outOfFilm(item); return; }
    if (response.status === 429) {  // waiting for room in the developer, or a fair-use limit
      item.held = body.detail;
      render();
      later(response.headers.get("Retry-After"), () => { if (!item.cleared && item.held) develop(item); });
      return;
    }
    item.held = null;
    if (response.status === 401) openSignIn();
    if (!response.ok) throw new Error(body.detail || response.statusText);
    item.reserved = false;
    item.jobId = body.job_id;
    if (me.accounts) refreshMe().then(resumeUnpaid);  // a free re-add may have left room
    poll(item, body.job_id);
  } catch (e) {
    item.reserved = false;
    fail(item, e.message);
  }
}

async function poll(item, jobId) {
  if (item.jobId !== jobId || item.cleared) return;  // superseded, or cleared from the lab
  let status;
  try {
    status = await (await fetch(`/api/jobs/${jobId}`)).json();
  } catch (_) {
    setTimeout(() => poll(item, jobId), 2000);
    return;
  }
  if (item.jobId !== jobId) return;
  if (status.state === "done") {
    const img = new Image();
    const loaded = new Promise((resolve) => { img.onload = img.onerror = resolve; });
    img.src = `/api/jobs/${jobId}/view.jpg`;
    const shown = item === current && lab && lab.active && labJob === jobId;
    Promise.all([loaded, shown ? lab.finish() : null]).then(() => {
      if (item.jobId !== jobId) return;
      item.state = "done";
      if (item.doneJob && item.doneJob !== jobId) item.previous = { job: item.doneJob, settings: item.doneSettings };
      item.info = status.info;
      item.doneJob = jobId;
      item.doneSettings = item.pendingSettings;
      if (!item.history) record(item);
      render();
      countForCoffee(item);
    });
    return;
  }
  if (status.state === "failed") {
    fail(item, status.error || "Could not develop this photograph");
    item.errorCode = status.code || null;
    render();
    if (me.accounts) refreshMe();  // its frame came back
    return;
  }
  Object.assign(item, { state: status.state, stage: status.stage || 0, stages: status.stages || 6,
                        stageName: status.stage_name, ahead: status.ahead || 0, wait: status.wait || 0,
                        early: Boolean(status.early) });
  renderSoon();
  setTimeout(() => poll(item, jobId), status.state === "running" ? 500 : 2000);  // waiting moves slowly
}

// --- rendering ---------------------------------------------------------------------------

// Progress from many frames at once comes down to one drawing per screen refresh.
let renderQueued = false;
function renderSoon() {
  if (renderQueued) return;
  renderQueued = true;
  requestAnimationFrame(() => { renderQueued = false; render(); });
}

function render() {
  followCurrent();
  cropping = shownTab() === "crop";
  renderLibrary();
  renderViewer();
  renderInspector();
  $("sharpening-note").hidden = !(current && current.info && current.info["camera sharpening"]);
  renderStatus();
  renderUndo();
}

// "about 4 min" for the time until a photograph goes into the developer.
function waitText(seconds) {
  if (!seconds || seconds < 45) return "";
  const minutes = Math.round(seconds / 60);
  return minutes < 60 ? `about ${minutes} min` : `about ${Math.round(minutes / 6) / 10} h`;
}

function statusLine(item) {
  switch (item.state) {
    case "uploading": return [item.held ? "Waiting to come in" : `Uploading ${item.uploadPct}%`, item.uploadPct / 100, ""];
    case "queued": return [item.held ? "Waiting to go in"
      : item.ahead ? ["Waiting", `${item.ahead} ahead`, waitText(item.wait)].filter(Boolean).join(" · ")
      : "Next in line", 0, ""];
    case "running": return [STAGE_WORDS[item.stageName] || item.stageName || "Developing", item.stage / (item.stages || 6), "darkroom"];
    case "failed": return [`Could not develop`, null, ""];
    case "unpaid": return ["Needs film", null, ""];
    case "checking": return ["Checking the film", null, ""];
    case "ready": return ["Ready to develop", null, ""];
    default: {
      const s = item.doneSettings || {};
      if (isMono(s)) {
        return [`Print ready · grade ${s.grade}${s.toning && s.toning !== "none" ? " · selenium" : ""}`
          + `${s.rating > 400 ? ` · EI ${s.rating}` : ""}`, null, ""];
      }
      return [`Slide ready · ${VIEW_NAMES[s.view] || "light box"}${s.exposure === "auto" ? " · auto" : ""}`, null, ""];
    }
  }
}

function thumbFor(item) {
  if (item.doneJob) return `/api/jobs/${item.doneJob}/thumb.jpg`;
  if (item.jobId && item.early) return `/api/jobs/${item.jobId}/early.jpg`;
  if (item.preview) return `/api/uploads/${item.uploadId}/thumb.jpg`;
  return null;
}

// The frames list is updated in place, never rebuilt: progress comes in many times a second
// while a roll develops, and a row replaced between press and release loses the click.
const rows = new Map();  // frame -> its row in the list

function frameRow(item) {
  if (rows.has(item)) return rows.get(item);
  const el = (tag, className) => Object.assign(document.createElement(tag), className ? { className } : {});
  const row = { li: el("li"), button: el("button", "photo"), thumb: el("span", "thumb"), file: el("span", "file"),
                no: el("span", "no"), line: el("span", "photo-status"), bar: el("span"), fill: el("span"), src: undefined };
  const name = el("span", "photo-name");
  name.append(row.file, row.no);
  row.bar.append(row.fill);
  const text = el("span", "photo-text");
  text.append(name, row.line, row.bar);
  row.button.append(row.thumb, text);
  row.button.addEventListener("click", () => { current = item; render(); });
  const remove = el("button", "photo-remove");
  remove.title = "Remove from the lab";
  remove.setAttribute("aria-label", `Remove ${item.name} from the lab`);
  remove.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7 7 17"/></svg>';
  remove.addEventListener("click", () => removeFrame(item));
  row.li.append(row.button, remove);
  rows.set(item, row);
  return row;
}

function setText(el, text) {
  if (el.textContent !== text) el.textContent = text;
}

function renderLibrary() {
  $("count").textContent = items.length ? String(items.length) : "";
  $("tab-count").textContent = items.length > 1 ? String(items.length) : "";
  $("clear").hidden = items.length === 0;
  const waiting = toDevelop().length;
  $("develop-all").hidden = waiting < 2;
  setText($("develop-all"), `Develop all ${waiting}`);
  $("library-empty").hidden = items.length > 0;
  for (const [item, row] of rows) {
    if (!items.includes(item)) { row.li.remove(); rows.delete(item); }
  }
  const list = $("photos");
  items.forEach((item, index) => {
    const row = frameRow(item);
    if (list.children[index] !== row.li) list.insertBefore(row.li, list.children[index] || null);
    row.button.className = "photo" + (item.state === "failed" ? " failed" : "");
    if (item === current) row.button.setAttribute("aria-current", "true");
    else row.button.removeAttribute("aria-current");
    row.thumb.className = `thumb${item.doneJob ? (isMono(item.doneSettings) ? " print" : " slide") : ""}`;
    const src = thumbFor(item);
    if (src !== row.src) {
      row.src = src;
      const shown = src ? Object.assign(document.createElement("img"), { src, alt: "" })
        : Object.assign(document.createElement("span"), { className: "ext",
                                                           textContent: extension(item.name).slice(1).toUpperCase() || "—" });
      row.thumb.replaceChildren(shown);
    }
    const [status, fraction, kind] = statusLine(item);
    setText(row.file, item.name);
    setText(row.no, pad2(index + 1));
    setText(row.line, status);
    row.button.title = `${item.name}\n${item.state === "failed" ? item.error : status}`;
    row.bar.hidden = fraction === null;
    row.bar.className = `progress ${kind}`;
    if (fraction !== null) row.fill.style.width = `${Math.round(fraction * 100)}%`;
  });
}

// One frame out of the lab: the server deletes the photograph and what was made from it.
function removeFrame(item) {
  const at = items.indexOf(item);
  if (at < 0) return;
  item.cleared = true;
  if (item.uploadId) forgetUploads([item.uploadId]);
  items.splice(at, 1);
  const queued = uploadQueue.findIndex(([waiting]) => waiting === item);
  if (queued >= 0) uploadQueue.splice(queued, 1);
  if (current === item) current = items[at] || items[at - 1] || null;
  render();
}

function renderViewer() {
  const hasItem = Boolean(current);
  $("welcome").hidden = hasItem;
  document.body.classList.toggle("empty", !hasItem);
  document.querySelector(".viewer").classList.toggle("idle", !hasItem);
  document.querySelector(".viewer").classList.toggle("cropping", cropping);
  $("again").disabled = !hasItem || !current.uploadId || ["uploading", "queued", "running"].includes(current.state);
  renderAgain();
  const shown = hasItem ? current.doneJob : null;
  $("export-jpg").disabled = !shown;
  $("export-more").disabled = !items.some((i) => i.doneJob);
  const previous = shown ? current.previous : null;
  const mode = cropping ? "slide" : compareMode();
  document.querySelectorAll("[data-compare]").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.compare === mode));
    b.disabled = !shown || cropping || (b.dataset.compare === "previous" && !previous);
  });
  $("compare").classList.toggle("off", !shown);

  const frame = $("frame");
  frame.hidden = !shown;
  frame.className = `frame mode-${mode}${cropping ? " cropping" : mode === "split" || mode === "previous" ? " split" : ""}`;
  $("crop-box").hidden = !(shown && cropping);
  if (shown && $("after").dataset.job !== shown) {
    $("after").src = `/api/jobs/${shown}/view.jpg`;
    $("after").dataset.job = shown;
  }
  const left = !shown ? null : mode === "previous" ? `/api/jobs/${previous.job}/view.jpg` : `/api/jobs/${shown}/before.jpg`;
  if (left && $("before").dataset.src !== left) {
    $("before").src = left;
    $("before").dataset.src = left;
    $("before").alt = mode === "previous" ? "The previous development" : "The raw file, rendered neutrally";
  }

  const working = $("working");
  working.hidden = !hasItem || current.state === "done";
  const developing = hasItem && current.state === "running" && lab;
  $("lab").hidden = !developing;
  const original = hasItem && ["ready", "queued"].includes(current.state) ? current.preview : null;
  $("original").hidden = !original;
  if (original && $("original").dataset.src !== original) {
    $("original").src = original;
    $("original").dataset.src = original;
    $("original").alt = `${current.name}, not developed yet`;
  }
  if (developing) {
    if (labJob !== current.jobId) {
      labJob = current.jobId;
      lab.start(isMono(current.pendingSettings) ? "print" : "slide");
    }
    lab.stage(current.stage);
    if (current.early) lab.setImage(`/api/jobs/${current.jobId}/early.jpg`);
  }
  if (!working.hidden) {
    $("stage-name").classList.toggle("error", current.state === "failed");
    if (!developing) {
      const [title, step] = waitingText(current);
      $("stage-name").textContent = title;
      $("step").textContent = step;
    }
    const fraction = current.state === "running" ? current.stage / (current.stages || 6)
      : current.state === "uploading" ? current.uploadPct / 100 : 0;
    $("rule-fill").style.width = `${Math.round(fraction * 100)}%`;
    $("rule-fill").parentElement.hidden = ["failed", "unpaid", "ready"].includes(current.state);
  }
  $("working-ready").hidden = !(hasItem && current.state === "ready");
  const others = toDevelop().length;
  $("develop-rest").hidden = others < 2;
  setText($("develop-rest"), `Develop all ${others}`);
  $("working-buy").hidden = !(hasItem && current.state === "unpaid");
  const turnedAway = hasItem && current.state === "failed" && current.errorCode === "monochrome";
  $("working-mono").hidden = !turnedAway;
  $("as-colour").hidden = !(options && options.colourise);
  $("get-colour").hidden = !(options && options.colourise_download && !options.colourise);

  const doneMono = shown && isMono(current.doneSettings);
  document.querySelector('[data-compare="slide"]').textContent = doneMono ? "Print" : "Slide";
  const [was, now] = mode === "previous" ? settingsDiff(previous.settings, current.doneSettings) : ["", ""];
  document.querySelector(".tag-raw").textContent = mode === "previous" ? (was ? `Previous · ${was}` : "Previous") : "Raw";
  if (shown && current.doneSettings) $("after").alt = `Developed on ${filmName(current.doneSettings.film)}`;
  document.querySelector(".tag-slide").textContent = !(shown && current.doneSettings) ? "Sunday 64"
    : mode === "previous" ? (now ? `Now · ${now}` : "Now") : filmName(current.doneSettings.film);
  applyGrade();

  const info = shown && current.info;
  $("meta").textContent = info ? metaLine(info) : "";
  $("infobar").innerHTML = info ? infoLine(current) : (hasItem ? `<b>${escapeHtml(current.name)}</b>` : "");
  layoutFrame();
}

function waitingText(item) {
  switch (item.state) {
    case "uploading": return item.held ? ["Waiting to come in", item.held] : ["Arriving at the lab", `${item.name} · ${item.uploadPct}%`];
    case "queued": {
      if (item.held) return ["Waiting to go in", item.held];
      const wait = waitText(item.wait);
      return ["Waiting for the developer", item.ahead
        ? `${item.ahead} ${item.ahead === 1 ? "photograph" : "photographs"} ahead${wait ? `, ${wait}` : ""}` : "Next in line"];
    }
    case "failed": return [item.error, `Could not develop ${item.name}`];
    case "unpaid": return ["Out of film", `${item.name} develops as soon as there is film for it`];
    case "checking": return ["Checking the film", `Whether ${item.name} was developed here before`];
    case "ready": return ["Ready to develop", `${item.name}: choose its settings, then develop it`];
    default: return ["Developing", item.name];
  }
}

function filmName(id) {
  const film = options && options.films && options.films.find((f) => f.id === id);
  return film ? film.name : "Sunday 64";
}

function metaLine(info) {
  const parts = [];
  if (info.scene_light_k) parts.push(`${info.scene_light_k} K`);
  if (info.flash) parts.push("flash");
  if (info.film === MONO) {
    const filter = BW_FILTER_NAMES[info.filter];
    parts.push(info.filter && info.filter !== "none" && filter ? `${filter.split(",")[0].replace(" · ", " ")} filter` : "no filter");
    parts.push(`EI ${info.rating}`, `grade ${info.grade}`);
    if (info.toning && info.toning !== "none") parts.push(`selenium ${info.toning === "strong" ? "1+5" : "1+20"}`);
    if (info.format && info.format !== "35mm") parts.push(FORMAT_NAMES[info.format]);
    parts.push(`${info.width} × ${info.height}`);
    return parts.join(" · ");
  }
  parts.push(info.filter && info.filter !== "none" ? `${info.filter} filter` : "no filter");
  parts.push(VIEW_NAMES[info.view] || info.view);
  if (info.format && info.format !== "35mm") parts.push(FORMAT_NAMES[info.format]);
  parts.push(`${info.width} × ${info.height}`);
  return parts.join(" · ");
}

function infoLine(item) {
  const info = item.info;
  const s = item.doneSettings || {};
  const parts = [`<b>${escapeHtml(item.name)}</b>`];
  const film = info["film exposure ev"];
  if (typeof film === "number") {
    parts.push(`Film exposed <b class="mono">${film > 0 ? "+" : film < 0 ? "−" : "±"}${Math.abs(film).toFixed(2)} EV</b> from the meter`);
  }
  parts.push(s.exposure === "auto" ? "Auto exposure" : "As shot");
  if (s.ev) parts.push(`Compensation <b class="mono">${formatEv(s.ev)}</b>`);
  if (isMono(s)) {
    const minutes = devMinutes(s.rating);
    if (minutes) parts.push(`Developed <b class="mono">${minutesText(minutes)} min</b>`);
  }
  if (info.colours) parts.push(`Colours <b>${escapeHtml(info.colours)}</b>`);
  if (info.decoder && info.decoder !== "LibRaw") parts.push(`Decoded by ${escapeHtml(info.decoder)}`);
  parts.push(`<b class="mono">${info.seconds} s</b> in the lab`);
  return parts.map((p) => `<span>${p}</span>`).join("");
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// One tool at a time. Colour, Tones and Crop open once a frame is out of the developer.
function availableTabs() {
  const done = Boolean(current && current.doneJob);
  const mono = done && isMono(current.doneSettings);
  return { develop: true, colour: done && !mono && Boolean(grader), tones: done && Boolean(grader), crop: done,
           frames: framesTab.matches && items.length > 0 };
}

function shownTab() {
  return availableTabs()[activeTab] ? activeTab : "develop";
}

function openTab(name) {
  if (!availableTabs()[name]) return;
  const passing = name === "crop" || name === "frames";  // not where the next visit should open
  if (!passing) lastTab = name;
  activeTab = name;
  try { localStorage.setItem("dyeroom-tab", passing ? lastTab : name); } catch (_) { /* ignore */ }
  render();
}

function renderInspector() {
  renderPresets();
  const ok = availableTabs();
  const shown = shownTab();
  const mono = Boolean(current && current.doneJob && isMono(current.doneSettings));
  document.querySelectorAll(".tab").forEach((tab) => {
    const name = tab.dataset.tab;
    tab.disabled = !ok[name];
    tab.setAttribute("aria-selected", String(name === shown));
    tab.title = ok[name] ? "" : name === "colour" && mono
      ? "A black-and-white print has no colours to adjust; Tones can still tint it"
      : "Opens once a frame is out of the developer";
  });
  document.querySelectorAll(".inspector > .sect").forEach((sect) => { sect.hidden = sect.id !== `sect-${shown}`; });
  document.querySelector(".inspector").dataset.tab = shown;
  syncAdjust();
  syncCrop();
}

function renderStatus() {
  $("statusbar").classList.toggle("quiet", !notice);  // on phones only messages show, over the picture
  const active = items.find((i) => i.state === "running") || items.find((i) => i.state === "queued")
    || items.find((i) => i.state === "uploading");
  const busy = items.filter((i) => ["uploading", "queued", "running"].includes(i.state)).length;
  $("queue").innerHTML = busy > 1 ? `<span class="mono">${busy}</span> in the queue` : "";
  $("status-bar").hidden = !active;
  $("lamp").classList.toggle("on", Boolean(active));
  if (!active && notice) {
    $("status-text").textContent = notice;
    return;
  }
  if (!active) {
    const done = items.filter((i) => i.doneJob).length;
    const draft = options ? options.draft_edge : 2400;
    $("status-text").innerHTML = done ? `Lab ready · <b class="mono">${pad2(done)}</b> ${done === 1 ? "frame" : "frames"} developed`
      : `Lab ready · drafts at <b class="mono">${draft}</b> px`;
    return;
  }
  const [line, fraction] = statusLine(active);
  $("status-text").innerHTML = `<b><span class="mono">${pad2(items.indexOf(active) + 1)}</span> ${escapeHtml(active.name)}</b> · ${escapeHtml(line)}`;
  $("status-fill").style.width = `${Math.round((fraction || 0) * 100)}%`;
}

// The lab reports which phase it is showing; the words under it follow the pictures.
function labPhase(phase, sub) {
  if (lab && lab.mode === "print") {
    const [title, note] = PRINT_TEXT[sub || { fix: "stop", print: "enlarger" }[phase] || phase];
    $("stage-name").textContent = title;
    const minutes = current && current.pendingSettings ? devMinutes(current.pendingSettings.rating) : null;
    $("step").textContent = phase === "develop" && minutes
      ? `${minutesText(minutes)} minutes in the developer: a negative forms where the light fell`
      : phase === "print" && sub === "enlarger" && current && current.pendingSettings
        ? `Light through the negative exposes grade ${current.pendingSettings.grade} paper` : note;
    return;
  }
  let [title, note] = PHASE_TEXT[phase];
  if (phase === "dyes" && sub) note = DYE_TEXT[sub];
  if (phase === "light" && sub === "bleach") [title, note] = PHASE_TEXT.bleach;
  if (phase === "light" && sub !== "bleach" && current && current.pendingSettings
      && current.pendingSettings.view === "projector") {
    title = "On the projector screen";
  }
  $("stage-name").textContent = title;
  $("step").textContent = note;
}

// --- framing: turn, straighten, crop ----------------------------------------------------------
// Each frame keeps its own framing, applied to the developed slide when it is exported, as
// colour and tones are (adjust.frame on the server does the same arithmetic). The picture is
// turned in quarters, then rotated by the straightening angle about its centre; the crop is
// an upright rectangle in fractions of the turned picture, always inside the rotated one.

const ASPECTS = { "1:1": 1, "5:4": 5 / 4, "4:3": 4 / 3, "3:2": 3 / 2, "16:9": 16 / 9 };
const ASPECT_LIST = [
  { value: "original", text: "Original" }, { value: "free", text: "Free" },
  { value: "1:1", text: "1:1 · 6×6" }, { value: "5:4", text: "5:4 · 6×7" }, { value: "4:3", text: "4:3 · 6×4.5" },
  { value: "3:2", text: "3:2 · 35 mm" }, { value: "16:9", text: "16:9" },
];

// A shape of the ratio, its long side 14 of 20; dashed for a free crop, none for the original
function aspectIcon(aspect) {
  if (aspect === "original") return "";
  const r = ASPECTS[aspect] || 4 / 3;
  return rectIcon(14, 14 / r, aspect === "free" ? ' stroke-dasharray="2 2"' : "");
}
const FULL = { x: 0, y: 0, w: 1, h: 1 };
const plainGeometry = () => ({ turns: 0, angle: 0, crop: null, aspect: "original", portrait: undefined, auto: true });
const geometryOf = (item) => (item && item.geometry) || plainGeometry();
const isPlainFrame = (g) => !g || (!g.turns && !g.angle && !g.crop);
const geometryOut = (g) => (isPlainFrame(g) ? {} : { turns: g.turns, angle: Math.round(g.angle * 100) / 100, crop: g.crop });

function editGeometry() {
  if (!current.geometry) current.geometry = plainGeometry();
  return current.geometry;
}

// The frame takes the crop's shape and the room the stage has; every layer inside it is the
// whole developed picture, turned, straightened and moved so the crop fills the frame.
function layoutFrame() {
  const frame = $("frame");
  const img = $("after");
  if (frame.hidden || !current || !img.naturalWidth) return;
  const g = geometryOf(current);
  const W0 = img.naturalWidth, H0 = img.naturalHeight;
  const W = g.turns % 2 ? H0 : W0, H = g.turns % 2 ? W0 : H0;
  const crop = cropping ? FULL : (g.crop || FULL);
  const stage = $("stage");
  const style = getComputedStyle(stage);
  const roomW = stage.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  const roomH = stage.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
  // A phone sizes the picture's area to the picture (style.css): set its shape before measuring
  $("stage").parentElement.style.setProperty("--aspect", ((crop.w * W) / (crop.h * H)).toFixed(4));
  let k = Math.min(roomW / (crop.w * W), roomH / (crop.h * H));
  k = Math.max(0.01, Math.min(k, crop === FULL ? 1 : 3));  // a whole picture is never blown up past its size
  if (cropping || zoomFor !== current) resetZoom();
  zoomFor = current;
  const z = Math.min(zoom.z, zoomMax(k));
  const zk = k * z;
  // Zoomed in, the picture is larger than the frame, which then fills the stage and shows the
  // part around the zoom's centre; at 1 the frame is the picture
  const pw = crop.w * W * zk, ph = crop.h * H * zk;
  const fw = Math.min(roomW, pw), fh = Math.min(roomH, ph);
  const px = pw <= fw ? 0 : Math.min(0, Math.max(fw - pw, fw / 2 - zoom.u * pw));
  const py = ph <= fh ? 0 : Math.min(0, Math.max(fh - ph, fh / 2 - zoom.v * ph));
  zoom = { z, u: pw <= fw ? 0.5 : (fw / 2 - px) / pw, v: ph <= fh ? 0.5 : (fh / 2 - py) / ph };
  frame.style.width = `${fw}px`;
  frame.style.height = `${fh}px`;
  frame.classList.toggle("zoomed", z > 1.001);
  const transform = `translate(${px - crop.x * W * zk}px, ${py - crop.y * H * zk}px) translate(${(W * zk) / 2}px, ${(H * zk) / 2}px) `
    + `rotate(${g.angle + 90 * g.turns}deg) translate(${(-W0 * zk) / 2}px, ${(-H0 * zk) / 2}px)`;
  frame.querySelectorAll(".film").forEach((film) => {
    film.style.width = `${W0 * zk}px`;
    film.style.height = `${H0 * zk}px`;
    film.style.transform = transform;
  });
  view = { k, W, H, W0, H0, z, px, py, pw, ph };
  if (cropping) placeCropBox();
}

// Whether a rectangle (in pixels of the turned picture) lies inside the frame and inside the
// straightened picture: its corners, turned back by the angle, must land on the picture.
function covered(r, g, W, H) {
  const e = 0.5;
  if (r.x < -e || r.y < -e || r.x + r.w > W + e || r.y + r.h > H + e) return false;
  if (!g.angle) return true;
  const t = (g.angle * Math.PI) / 180, c = Math.cos(t), s = Math.sin(t);
  return [[r.x, r.y], [r.x + r.w, r.y], [r.x, r.y + r.h], [r.x + r.w, r.y + r.h]].every(([px, py]) => {
    const dx = px - W / 2, dy = py - H / 2;
    const qx = c * dx + s * dy + W / 2, qy = -s * dx + c * dy + H / 2;
    return qx >= -e && qx <= W + e && qy >= -e && qy <= H + e;
  });
}

const lerpRect = (a, b, t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t,
                                 w: a.w + (b.w - a.w) * t, h: a.h + (b.h - a.h) * t });

// From a rectangle that fits towards one that may not: as far as it still fits. (The room is
// convex, so the rectangles that fit along the way are one stretch from the start.)
function furthest(from, to, fits) {
  if (fits(to)) return to;
  let lo = 0, hi = 1;
  for (let i = 0; i < 16; i++) {
    const mid = (lo + hi) / 2;
    if (fits(lerpRect(from, to, mid))) lo = mid; else hi = mid;
  }
  return lerpRect(from, to, lo);
}

// Width over height the crop must keep, or null for a free crop.
function ratioOf(g, W, H) {
  if (g.aspect === "free") return null;
  const r = g.aspect === "original" ? Math.max(W, H) / Math.min(W, H) : ASPECTS[g.aspect] || W / H;
  const portrait = g.portrait === undefined ? H > W : g.portrait;
  return portrait ? 1 / r : r;
}

// The largest crop of this shape around a point that fits the straightened picture.
function largest(g, W, H, ratio, cx = W / 2, cy = H / 2) {
  const r = ratio || W / H;
  const w = Math.min(W, H * r, 2 * Math.min(cx, W - cx), 2 * Math.min(cy, H - cy) * r);
  const at = (s) => ({ x: cx - (w * s) / 2, y: cy - (w * s) / r / 2, w: w * s, h: (w * s) / r });
  return furthest(at(0), at(1), (q) => covered(q, g, W, H));
}

function cropRect(g) {
  const { W, H } = view;
  const c = g.crop || FULL;
  return { x: c.x * W, y: c.y * H, w: c.w * W, h: c.h * H };
}

function setCrop(g, rect, auto) {
  const { W, H } = view;
  const crop = { x: rect.x / W, y: rect.y / H, w: rect.w / W, h: rect.h / H };
  const whole = Math.abs(crop.x) < 1e-4 && Math.abs(crop.y) < 1e-4 && crop.w > 0.9999 && crop.h > 0.9999;
  g.crop = whole ? null : crop;
  g.auto = auto;
  placeCropBox();
}

// After the angle or the shape changed: a crop never moved by hand becomes the largest that
// fits; one placed by hand shrinks about its centre until it fits again.
function refit(g) {
  const { W, H } = view;
  const ratio = ratioOf(g, W, H);
  if (g.auto) { setCrop(g, largest(g, W, H, ratio), true); return; }
  const r = cropRect(g);
  const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
  const centre = { x: cx, y: cy, w: 0, h: 0 };
  if (!covered(centre, g, W, H)) { setCrop(g, largest(g, W, H, ratio || r.w / r.h), false); return; }
  const target = ratio ? largest(g, W, H, ratio, cx, cy) : r;
  setCrop(g, furthest(centre, target, (q) => covered(q, g, W, H)), false);
}

function placeCropBox() {
  if (!view || !current) return;
  const g = geometryOf(current);
  const r = cropRect(g);
  const box = $("crop-box");
  Object.assign(box.style, { left: `${r.x * view.k}px`, top: `${r.y * view.k}px`,
                             width: `${r.w * view.k}px`, height: `${r.h * view.k}px` });
  box.classList.toggle("locked", ratioOf(g, view.W, view.H) !== null);
  $("reset-crop").disabled = isPlainFrame(g);
  noteEdit();
}

function syncCrop() {
  const g = geometryOf(current);
  showDropdown("aspect");
  $("straighten").value = g.angle;
  $("straighten-out").textContent = `${g.angle > 0 ? "+" : g.angle < 0 ? "−" : ""}${Math.abs(g.angle).toFixed(1)}°`;
  $("aspect-swap").disabled = !current;
  $("reset-crop").disabled = !current || isPlainFrame(g);
  paintRange($("straighten"));
}

// A drag on the crop: inside moves it, an edge or corner resizes it (corners keep its shape).
function dragCrop(handle, r, dx, dy, g) {
  const { W, H, k } = view;
  const fits = (q) => covered(q, g, W, H);
  if (handle === "move") {
    const across = furthest(r, { ...r, x: r.x + dx }, fits);
    return furthest(across, { ...across, y: r.y + dy }, fits);
  }
  const min = 32 / k;
  let left = r.x, top = r.y, right = r.x + r.w, bottom = r.y + r.h;
  if (handle.includes("w")) left = Math.min(left + dx, right - min);
  if (handle.includes("e")) right = Math.max(right + dx, left + min);
  if (handle.includes("n")) top = Math.min(top + dy, bottom - min);
  if (handle.includes("s")) bottom = Math.max(bottom + dy, top + min);
  let to = { x: left, y: top, w: right - left, h: bottom - top };
  const ratio = ratioOf(g, W, H);
  if (ratio && handle.length === 2) {
    let { w, h } = to;
    if (w / h > ratio) h = w / ratio; else w = h * ratio;
    to = { x: handle.includes("w") ? right - w : left, y: handle.includes("n") ? bottom - h : top, w, h };
  }
  return furthest(r, to, fits);
}

function turn(by) {  // +1: a quarter to the right (clockwise), -1: to the left
  if (!current || !current.doneJob) return;
  const g = editGeometry();
  g.turns = (g.turns + by + 4) % 4;
  const c = g.crop;
  if (c) g.crop = by > 0 ? { x: 1 - (c.y + c.h), y: c.x, w: c.h, h: c.w } : { x: c.y, y: 1 - (c.x + c.w), w: c.h, h: c.w };
  if (g.portrait !== undefined) g.portrait = !g.portrait;
  layoutFrame();
}

// The crop is kept as it is drawn; finishing only leaves the tool, back to the one used before
function finishCrop() {
  openTab(lastTab === "crop" ? "develop" : lastTab);
}

function chooseAspect(aspect) {
  if (!current || !view) return;
  const g = editGeometry();
  const r = cropRect(g);
  g.aspect = aspect;
  g.portrait = g.aspect === "original" ? undefined : r.h > r.w;
  if (g.aspect !== "free") setCrop(g, largest(g, view.W, view.H, ratioOf(g, view.W, view.H)), true);
  placeCropBox();
  showDropdown("aspect");
}

function bindCrop() {
  const box = $("crop-box");
  let drag = null;
  box.addEventListener("pointerdown", (e) => {
    if (!cropping || !current || !view) return;
    e.preventDefault();
    e.stopPropagation();
    box.setPointerCapture(e.pointerId);
    drag = { handle: e.target.dataset.handle || "move", x: e.clientX, y: e.clientY, rect: cropRect(geometryOf(current)) };
  });
  box.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const g = editGeometry();
    setCrop(g, dragCrop(drag.handle, drag.rect, (e.clientX - drag.x) / view.k, (e.clientY - drag.y) / view.k, g), false);
  });
  const end = () => { drag = null; };
  box.addEventListener("pointerup", end);
  box.addEventListener("pointercancel", end);

  $("straighten").addEventListener("input", (e) => {
    if (!current || !view) return;
    const g = editGeometry();
    g.angle = Number(e.target.value);
    refit(g);
    layoutFrame();
    syncCrop();
  });
  $("straighten").addEventListener("dblclick", () => {
    if (!current || !view) return;
    editGeometry().angle = 0;
    refit(current.geometry);
    layoutFrame();
    syncCrop();
  });
  bindDropdown("aspect", { list: () => ASPECT_LIST, chosen: () => geometryOf(current).aspect, icon: aspectIcon,
                           choose: chooseAspect });
  $("aspect-swap").addEventListener("click", () => {
    if (!current || !view) return;
    const g = editGeometry();
    const r = cropRect(g);
    if (g.aspect === "free") {
      const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
      const turned = { x: cx - r.h / 2, y: cy - r.w / 2, w: r.h, h: r.w };
      setCrop(g, furthest({ x: cx, y: cy, w: 0, h: 0 }, turned, (q) => covered(q, g, view.W, view.H)), false);
      return;
    }
    g.portrait = !(g.portrait === undefined ? view.H > view.W : g.portrait);
    setCrop(g, largest(g, view.W, view.H, ratioOf(g, view.W, view.H)), true);
  });
  $("rotate-left").addEventListener("click", () => turn(-1));
  $("crop-done").addEventListener("click", finishCrop);
  $("rotate-right").addEventListener("click", () => turn(1));
  $("reset-crop").addEventListener("click", () => {
    if (!current) return;
    current.geometry = null;
    layoutFrame();
    syncCrop();
  });
}

// --- adjustments -------------------------------------------------------------------------

function applyGrade() {
  const identity = !current || isIdentity(current.adjust);
  const ready = grader && current && current.doneJob && $("graded").dataset.job === current.doneJob;
  $("graded").hidden = !ready || identity;
  noteEdit();
  if (ready && !identity) grader.render(current.adjust);
  // The previous development gets the same finishing adjustments, so only the development differs.
  const previous = current && current.previous;
  const readyBefore = graderBefore && previous && compareMode() === "previous"
    && $("graded-before").dataset.job === previous.job;
  $("graded-before").hidden = !readyBefore || identity;
  if (readyBefore && !identity) graderBefore.render(current.adjust);
}

function syncAdjust() {
  const adjust = current ? current.adjust : emptyAdjust();
  document.querySelectorAll("#bands button").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.band === activeBand));
    b.classList.toggle("changed", (adjust.bands[b.dataset.band] || [0, 0, 0]).some((v) => v !== 0));
  });
  $("band-name").textContent = activeBand[0].toUpperCase() + activeBand.slice(1);
  const values = adjust.bands[activeBand] || [0, 0, 0];
  document.querySelectorAll("#sect-colour input[data-param]").forEach((input) => {
    input.value = values[Number(input.dataset.param)];
    input.nextElementSibling.textContent = signed(Number(input.value));
  });
  document.querySelectorAll("#sect-tones .wheel").forEach((el) => {
    const [angle, amount, light] = adjust.wheels[el.dataset.wheel] || [0, 0, 0];
    el.wheel.set([angle, amount]);
    el.querySelector("input").value = light;
  });
  const moved = (values) => Object.values(values).some((v) => v.some((x) => x !== 0));
  $("reset-colour").disabled = !moved(adjust.bands);
  $("reset-tones").disabled = !Object.values(adjust.wheels).some(([, amount, light]) => amount !== 0 || light !== 0);
  paintRanges();
}

function bindAdjust() {
  const bands = $("bands");
  Object.entries(ADJUST.bands).forEach(([name, hue]) => {
    const b = document.createElement("button");
    b.dataset.band = name;
    b.setAttribute("aria-label", name);
    b.title = name[0].toUpperCase() + name.slice(1);
    b.style.setProperty("--band", oklchCss(0.68, 0.15, hue));
    b.addEventListener("click", () => { activeBand = name; syncAdjust(); });
    bands.append(b);
  });
  const label = document.createElement("span");
  label.className = "band-name label";
  label.id = "band-name";
  bands.append(label);

  const changed = () => { applyGrade(); syncAdjust(); };
  document.querySelectorAll("#sect-colour input[data-param]").forEach((input) => {
    const set = (value) => {
      if (!current) return;
      const values = (current.adjust.bands[activeBand] || [0, 0, 0]).slice();
      values[Number(input.dataset.param)] = value;
      current.adjust.bands[activeBand] = values;
      changed();
    };
    input.addEventListener("input", () => set(Number(input.value)));
    input.addEventListener("dblclick", () => set(0));
  });
  document.querySelectorAll("#sect-tones .wheel").forEach((el) => {
    const name = el.dataset.wheel;
    const light = el.querySelector("input");
    const store = (angle, amount, value) => { if (current) current.adjust.wheels[name] = [angle, amount, value]; changed(); };
    el.wheel = new Wheel(el.querySelector("canvas"), ([angle, amount]) => store(angle, amount, Number(light.value)));
    light.addEventListener("input", () => store(el.wheel.value[0], el.wheel.value[1], Number(light.value)));
    light.addEventListener("dblclick", () => { light.value = 0; store(el.wheel.value[0], el.wheel.value[1], 0); });
  });
  $("reset-colour").addEventListener("click", () => { if (current) current.adjust.bands = {}; changed(); });
  $("reset-tones").addEventListener("click", () => { if (current) current.adjust.wheels = {}; changed(); });
  $("after").addEventListener("load", () => {
    layoutFrame();
    if (!grader || !current || !current.doneJob) return;
    grader.setImage($("after"), (current.doneSettings && current.doneSettings.display) || "p3");
    $("graded").dataset.job = current.doneJob;
    applyGrade();
  });
  $("before").addEventListener("load", () => {
    const previous = current && current.previous;
    if (!graderBefore || !previous || $("before").dataset.src !== `/api/jobs/${previous.job}/view.jpg`) return;
    graderBefore.setImage($("before"), (previous.settings && previous.settings.display) || "p3");
    $("graded-before").dataset.job = previous.job;
    applyGrade();
  });
}

async function exportFile(button, format) {
  const item = current;
  if (!item || !item.doneJob || button.classList.contains("busy")) return;
  if (format === "jpg" && isIdentity(item.adjust) && isPlainFrame(item.geometry)) {  // the developed file as it is
    const a = document.createElement("a");
    a.href = `/api/jobs/${item.doneJob}/slide.jpg?download=1`;
    document.body.append(a);
    a.click();
    a.remove();
    return;
  }
  const label = button.lastChild.textContent;
  button.classList.add("busy");
  button.lastChild.textContent = "Preparing…";
  try {
    const response = await fetch(`/api/jobs/${item.doneJob}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ format, adjust: item.adjust, geometry: geometryOut(geometryOf(item)) }),
    });
    if (!response.ok) throw new Error(errorText(await response.text(), response.status));
    const name = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") || "");
    const url = URL.createObjectURL(await response.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = name ? name[1] : `slide.${format}`;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) {
    button.title = e.message;
  } finally {
    button.classList.remove("busy");
    button.lastChild.textContent = label;
  }
}

// Every developed frame, each with its own Colour and Tones, in one ZIP. The server makes it
// frame by frame while the browser saves it, so even a roll of TIFFs never sits in memory here.
async function exportRoll(format) {
  const frames = items.filter((i) => i.doneJob).map((i) => ({ job_id: i.doneJob, adjust: cleanAdjust(i.adjust),
                                                                geometry: geometryOut(geometryOf(i)) }));
  if (!frames.length) return;
  try {
    const response = await fetch("/api/rolls", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ format, frames }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || response.statusText);
    const a = document.createElement("a");
    a.href = `/api/rolls/${body.roll_id}.zip`;
    document.body.append(a);
    a.click();
    a.remove();
    setNotice(`Exporting ${body.frames} ${body.frames === 1 ? "frame" : "frames"} · the ZIP arrives as each is made`);
  } catch (e) {
    setNotice(e.message || "The roll could not be exported");
  }
}

// --- account and film --------------------------------------------------------------------

const SSO_ICONS = {
  apple: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M16.37 1.43c0 1.14-.49 2.27-1.18 3.08-.74.9-1.99 1.57-2.99 1.57-.12 0-.23-.02-.3-.03-.01-.06-.04-.22-.04-.39 0-1.15.57-2.27 1.21-2.98.8-.94 2.14-1.64 3.25-1.68.03.13.05.28.05.43zm4.56 15.71c-.03.07-.46 1.58-1.52 3.12-.94 1.34-1.94 2.71-3.43 2.71-1.52 0-1.9-.88-3.63-.88-1.7 0-2.3.91-3.67.91-1.38 0-2.33-1.26-3.43-2.8-1.29-1.82-2.32-4.63-2.32-7.28 0-4.28 2.8-6.55 5.55-6.55 1.45 0 2.68.95 3.6.95.87 0 2.22-1.01 3.9-1.01.61 0 2.89.06 4.37 2.19-.13.09-2.38 1.37-2.38 4.19 0 3.26 2.85 4.42 2.96 4.45z"/></svg>',
  google: '<svg viewBox="0 0 18 18" aria-hidden="true"><path fill="#EA4335" d="M9 3.48c1.69 0 2.83.73 3.48 1.34l2.54-2.48C13.46.89 11.43 0 9 0 5.48 0 2.44 2.02.96 4.96l2.91 2.26C4.6 5.05 6.62 3.48 9 3.48z"/><path fill="#4285F4" d="M17.64 9.2c0-.74-.06-1.28-.19-1.84H9v3.34h4.96c-.1.83-.64 2.08-1.84 2.92l2.84 2.2c1.7-1.57 2.68-3.88 2.68-6.62z"/><path fill="#FBBC05" d="M3.88 10.78A5.54 5.54 0 0 1 3.58 9c0-.62.11-1.22.29-1.78L.96 4.96A9 9 0 0 0 0 9c0 1.45.35 2.82.96 4.04l2.92-2.26z"/><path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.84-2.2c-.76.53-1.78.9-3.12.9-2.38 0-4.4-1.57-5.12-3.74L.97 13.04C2.45 15.98 5.48 18 9 18z"/></svg>',
};

async function refreshMe() {
  try {
    const response = await fetch("/api/me", { cache: "no-store" });
    if (response.ok) me = await response.json();
  } catch (_) { /* offline: keep what was known */ }
  renderAccount();
  return me;
}

const needsSignIn = () => Boolean(me.accounts && !me.signed_in);

// Photographs that may still be started: what the account covers, less those already on their way.
function filmLeft() {
  if (!me.accounts) return Infinity;
  if (!me.signed_in) return 0;
  return me.available - items.filter((i) => i.reserved).length;
}

const framesText = (n) => `${n} ${n === 1 ? "frame" : "frames"} left`;
const planName = (plan) => ({ monthly: "Monthly plan", yearly: "Yearly plan" })[plan.id] || "Plan";
const longDate = (t) => new Date(t * 1000).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

function renderAccount() {
  const on = Boolean(me.accounts);
  $("sign-in").hidden = !on || me.signed_in;
  $("account").hidden = !on || !me.signed_in;
  $("fact-film").hidden = !on;
  if (!on) return;
  const free = options ? options.free_frames : 5;
  $("free-count").textContent = free;
  let title, note;
  if (!me.signed_in) {
    [title, note] = [`First ${free} photographs free`, "Sign in with Apple or Google"];
  } else if (me.plan) {
    title = me.plan.status === "past_due" ? `${planName(me.plan)} · payment due` : planName(me.plan);
    note = `${me.plan.used.toLocaleString("en")} of ${me.plan.cap.toLocaleString("en")} this month`;
  } else if (me.frames > 0) {
    [title, note] = [framesText(me.frames), "One per photograph"];
  } else {
    [title, note] = ["Out of film", "Buy a roll or start a plan"];
  }
  $("account-label").textContent = me.signed_in ? (me.plan ? title : framesText(me.frames)) : "";
  $("fact-film-title").textContent = title;
  $("fact-film-note").textContent = note;
  $("fact-film").title = me.signed_in ? "Buy film" : "Sign in";
}

function legalLink(href, text) {
  return Object.assign(document.createElement("a"), { href, textContent: text, target: "_blank", rel: "noopener" });
}

function renderProviders() {
  const list = options.providers || [];
  $("providers").replaceChildren(...list.map((p) => {
    const a = document.createElement("a");
    a.className = p.id;
    a.href = `/auth/${p.id}`;
    a.innerHTML = `${SSO_ICONS[p.id] || ""}<span>${p.id === "dev" ? "Continue as a test user" : `Continue with ${escapeHtml(p.label)}`}</span>`;
    return a;
  }));
  if (!list.length) $("providers").textContent = "Sign-in is not set up on this server yet.";
}

function openSignIn() {
  if (!$("signin").open) showSheet($("signin"));
}

// Opened with the sheet itself focused, so no button looks chosen in advance.
function showSheet(dialog) {
  dialog.showModal();
  dialog.focus();
}

function setNotice(text) {
  notice = text;
  renderStatus();
  setTimeout(() => { if (notice === text) { notice = null; renderStatus(); } }, 8000);
}

function outOfFilm(item, file) {
  item.reserved = false;
  item.state = "unpaid";
  if (file) item.file = file;
  render();
  refreshMe().then(() => openFilm(true));
}

function openFilm(out) {
  if ($("film-sheet").open) return;
  const billing = options && options.billing;
  const plans = billing ? billing.plans : [];
  const waiting = items.filter((i) => i.state === "unpaid").length;
  let note = !out ? `You have ${framesText(me.frames || 0)}. Each photograph uses one; developing it again is free.`
    : me.plan ? `This month's ${me.plan.cap.toLocaleString("en")} photographs on your plan are used. A roll covers the rest.`
    : "You're out of frames.";
  if (waiting) note += ` ${waiting === 1 ? "One photograph is" : `${waiting} photographs are`} waiting and will develop as soon as you buy.`;
  if (!plans.length) note += " Buying film is not set up on this server yet.";
  $("film-title").textContent = out ? "Out of film" : "Buy film";
  $("film-note").textContent = note;

  let chosen = null;
  const choose = (plan) => {
    chosen = plan;
    $("plans").querySelectorAll(".plan").forEach((tile) => tile.setAttribute("aria-checked", String(tile.dataset.plan === plan.id)));
    const [amount, ...per] = plan.price.split(" ");
    $("film-buy").textContent = plan.kind === "roll" ? `Buy a roll · ${amount}` : `Subscribe · ${amount} ${per.join(" ")}`;
  };
  $("plans").replaceChildren(...plans.map((plan) => {
    const yours = me.plan && me.plan.id === plan.id;
    const [amount, ...per] = plan.price.split(" ");
    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = "plan";
    tile.dataset.plan = plan.id;
    tile.setAttribute("role", "radio");
    tile.disabled = yours || (plan.kind === "plan" && Boolean(me.plan));  // one plan at a time; change it in the portal
    tile.innerHTML = `<span class="plan-name"></span><span class="plan-price"></span><span class="plan-per"></span>`
      + `<span class="plan-note"></span>${yours || plan.extra ? '<span class="plan-extra"></span>' : ""}`;
    tile.querySelector(".plan-name").textContent = plan.name;
    tile.querySelector(".plan-price").textContent = amount;
    tile.querySelector(".plan-per").textContent = per.join(" ") || "paid once";
    tile.querySelector(".plan-note").textContent = plan.note;
    if (yours || plan.extra) tile.querySelector(".plan-extra").textContent = yours ? "Your plan" : plan.extra;
    tile.addEventListener("click", () => choose(plan));
    return tile;
  }));
  const first = plans.find((p) => !$("plans").querySelector(`[data-plan="${p.id}"]`).disabled);
  $("plans").hidden = $("film-buy").hidden = !first;
  if (first) choose(first);
  $("film-buy").onclick = () => { if (chosen) buy(chosen); };
  $("film-fine").hidden = !billing;
  const refund = options.refund_days || 30;
  $("film-fine").replaceChildren(billing && billing.provider === "test"
    ? "Test mode: nothing is charged, and the film arrives at once. "
    : "Paddle.com sells the film for us as Merchant of Record, and sends the receipt. Cancel a plan any time from your account. ",
    `Refunds within ${refund} days: `, legalLink("/refunds", "refund policy"), ", ", legalLink("/terms", "terms"), ".");
  showSheet($("film-sheet"));
}

async function buy(plan) {
  $("film-sheet").close();
  fetch("/api/billing/opened", { method: "POST" }).catch(() => {});  // a count on /admin, nothing more
  if (options.billing.provider === "test") {
    const response = await fetch("/api/billing/test-buy", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plan: plan.id }),
    });
    await refreshMe();
    if (response.ok) { setNotice(`Film loaded · ${plan.name}`); resumeUnpaid(); }
    return;
  }
  try {
    await loadPaddle();
  } catch (e) {
    setNotice(e.message);
    return;
  }
  const checkout = { items: [{ priceId: plan.price_id, quantity: 1 }], customData: { user_id: me.id },
                     settings: { displayMode: "overlay", theme: "dark" } };
  if (me.email) checkout.customer = { email: me.email };
  window.Paddle.Checkout.open(checkout);
}

function loadPaddle() {
  if (!paddle) {
    paddle = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://cdn.paddle.com/paddle/v2/paddle.js";
      script.onload = () => {
        if (options.billing.environment === "sandbox") window.Paddle.Environment.set("sandbox");
        window.Paddle.Initialize({
          token: options.billing.token,
          eventCallback: (event) => { if (event.name === "checkout.completed") waitForFilm(); },
        });
        resolve();
      };
      script.onerror = () => { paddle = null; reject(new Error("The checkout could not load. Check the connection and try again.")); };
      document.head.append(script);
    });
  }
  return paddle;
}

// Paddle tells the server by webhook, a moment after the payment: wait for the film to arrive.
async function waitForFilm() {
  const before = me.available;
  setNotice("Payment received · loading the film");
  for (let i = 0; i < 30 && me.available <= before; i++) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    await refreshMe();
  }
  setNotice(me.available > before ? "Film loaded" : "The film is on its way; reload the page in a minute");
  resumeUnpaid();
}

function resumeUnpaid() {
  let room = filmLeft();
  for (const item of items) {
    if (item.state !== "unpaid" || room <= 0) continue;
    room--;
    item.reserved = true;
    if (item.uploadId) {
      develop(item);
    } else {
      item.state = "uploading";
      item.uploadPct = 0;
      uploadQueue.push([item, item.file]);
    }
  }
  pumpUploads();
  render();
}

function openAccount() {
  const who = me.name || me.email || "";
  $("account-initial").textContent = (who.trim()[0] || "·").toUpperCase();
  $("account-title").textContent = me.name || "Account";
  $("account-who").textContent = me.email || "";
  $("account-frames").textContent = (me.frames || 0).toLocaleString("en");
  const plan = me.plan;
  $("account-plan").textContent = plan ? planName(plan).replace(" plan", "") : "None";
  $("account-meter").hidden = !plan;
  if (plan) {
    $("account-meter-fill").style.width = `${Math.min(100, (100 * plan.used) / plan.cap)}%`;
    const when = plan.ends ? `Ends ${longDate(plan.ends)}` : plan.renews ? `Renews ${longDate(plan.renews)}` : "";
    $("account-plan-note").textContent = `${plan.used.toLocaleString("en")} of ${plan.cap.toLocaleString("en")} this month`
      + (plan.status === "past_due" ? " · payment due" : "") + (when ? `\n${when}` : "");
  } else {
    $("account-plan-note").textContent = options.billing
      ? `A plan covers up to ${options.billing.plan_cap.toLocaleString("en")} photographs a month.` : "";
  }
  const billing = options && options.billing;
  const test = billing && billing.provider === "test";
  $("account-buy").hidden = !billing;
  $("account-manage").hidden = !(billing && (test ? plan : me.customer));
  $("account-manage-label").textContent = test ? "End test plan" : "Plan and receipts";
  $("account-manage").classList.toggle("local", Boolean(test));  // no outside page to open in test mode
  showSheet($("account-sheet"));
}

async function manage() {
  const button = $("account-manage");
  const test = options.billing.provider === "test";
  const tab = test ? null : window.open("about:blank", "_blank");  // opened now, while the click still counts
  button.disabled = true;
  try {
    const response = await fetch("/api/billing/portal", { method: "POST" });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || response.statusText);
    if (body.url && tab) {
      tab.opener = null;
      tab.location = body.url;
    } else if (body.url) {
      location.href = body.url;
    } else {
      $("account-sheet").close();
      await refreshMe();
      setNotice(body.note || "Done");
    }
  } catch (e) {
    if (tab) tab.close();
    setNotice(e.message);
  } finally {
    button.disabled = false;
  }
}

async function signOut() {
  await fetch("/auth/logout", { method: "POST" });
  location.reload();
}

async function deleteAccount() {
  const sure = window.confirm("Delete your Dyeroom account? Your name and email are removed and you are signed out "
    + "everywhere. If you have a plan, cancel it first under Plan and receipts.");
  if (!sure) return;
  await fetch("/api/me", { method: "DELETE" });
  location.reload();
}

// --- presets -----------------------------------------------------------------------------------
// A preset is the development settings plus Colour and Tones. Choosing one applies it to the
// frame in view (developing it again if the development changes), or with none in view to the
// photographs added next.
// The button names the preset last chosen or saved, for as long as the settings still match it.

const PRESET_KEYS = ["film", "exposure", "ev", "light", "filter", "view", "grain", "rating", "grade",
                     "bw_filter", "toning", "format", "sharpness", "clarity"];
const onAccount = () => Boolean(me.accounts && me.signed_in);
const stable = (value) => JSON.stringify(value, (_, v) => (v && typeof v === "object" && !Array.isArray(v)
  ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, v[k]])) : v));
const cleanAdjust = (a) => ({ bands: { ...((a && a.bands) || {}) }, wheels: { ...((a && a.wheels) || {}) } });
let chosenPreset = null;  // name of the preset last chosen or saved
const ICON = {
  check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5.5v13M5.5 12h13"/></svg>',
  download: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4.5v10.5M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/></svg>',
  all: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="11" height="8" rx="1"/><rect x="9.5" y="11" width="11" height="8" rx="1"/></svg>',
  bin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 7h15M9.5 7V4.8h5V7M6.5 7l1 12.2h9l1-12.2"/></svg>',
};

function presetNow() {
  const s = Object.fromEntries(PRESET_KEYS.map((k) => [k, settings[k]]));
  s.adjust = cleanAdjust(current ? current.adjust : null);
  return s;
}

function presetInUse() {
  const preset = presets.find((p) => p.name === chosenPreset);
  if (!preset) return null;
  const now = presetNow();
  const same = PRESET_KEYS.every((k) => !(k in preset.settings) || String(preset.settings[k]) === String(now[k]))
    && stable(cleanAdjust(preset.settings.adjust)) === stable(now.adjust);
  return same ? preset : null;
}

function renderPresets() {
  const inUse = presetInUse();
  $("preset-current").textContent = inUse ? inUse.name : presets.length ? "No preset" : "No presets yet";
  $("preset-button").classList.toggle("empty", !inUse);
}

// Menus that drop from a button: built when opened, closed by a choice, a click elsewhere
// or Escape, walked with the arrow keys. One open at a time.
const openMenus = new Set();

function bindMenu(button, menu, build) {
  const close = () => {
    menu.hidden = true;
    button.setAttribute("aria-expanded", "false");
    openMenus.delete(close);
  };
  const open = () => {
    openMenus.forEach((other) => other());
    menu.replaceChildren(...build(close));
    menu.hidden = false;
    button.setAttribute("aria-expanded", "true");
    openMenus.add(close);
    const first = menu.querySelector(".menu-item.chosen") || menu.querySelector(".menu-item:not(:disabled)");
    if (first) first.focus();
  };
  button.addEventListener("click", () => (menu.hidden ? open() : close()));
  document.addEventListener("pointerdown", (e) => {
    if (!menu.hidden && !menu.contains(e.target) && !button.contains(e.target)) close();
  });
  menu.addEventListener("keydown", (e) => {
    const entries = [...menu.querySelectorAll(".menu-item:not(:disabled)")];
    const at = entries.indexOf(document.activeElement);
    if (e.key === "Escape") { close(); button.focus(); }
    else if (e.key === "ArrowDown") entries[(at + 1) % entries.length].focus();
    else if (e.key === "ArrowUp") entries[(at - 1 + entries.length) % entries.length].focus();
    else return;
    e.preventDefault();
    e.stopPropagation();
  });
  return { open, close };
}

function menuItem(icon, text, action, close, extra = "", note = "") {
  const b = document.createElement("button");
  b.type = "button";
  b.className = `menu-item ${extra}${note ? " tall" : ""}`;
  b.setAttribute("role", "menuitem");
  b.innerHTML = `<span class="menu-icon">${icon}</span><span class="menu-text"><span></span>${note ? "<small></small>" : ""}</span>`;
  b.querySelector(".menu-text > span").textContent = text;
  if (note) b.querySelector("small").textContent = note;
  b.addEventListener("click", () => { close(); action(); });
  return b;
}

function presetMenu(close) {
  const inUse = presetInUse();
  const parts = [];
  if (presets.length) {
    const label = document.createElement("p");
    label.className = "menu-label";
    label.textContent = onAccount() ? "Your presets" : "Presets in this browser";
    parts.push(label, ...presets.map((p) => menuItem(p === inUse ? ICON.check : "", p.name, () => applyPreset(p), close, "preset")));
  } else {
    const note = document.createElement("p");
    note.className = "menu-note";
    note.textContent = "No presets yet. Save the settings of a frame you like, then use them on other photographs.";
    parts.push(note);
  }
  const line = () => Object.assign(document.createElement("div"), { className: "menu-sep" });
  parts.push(line(), menuItem(ICON.plus, "Save current settings…", openPresetSheet, close));
  if (inUse) {
    parts.push(menuItem(ICON.all, "Apply to every frame", () => applyPreset(inUse, true), close),
               menuItem(ICON.bin, "Delete this preset", deletePreset, close, "danger"));
  }
  return parts;
}


async function loadPresets() {
  let local = [];
  try { local = JSON.parse(localStorage.getItem("dyeroom-presets") || "[]"); } catch (_) { local = []; }
  presets = local;
  if (onAccount()) {
    try {
      const response = await fetch("/api/presets", { cache: "no-store" });
      presets = response.ok ? await response.json() : local;
      if (response.ok && !presets.length && local.length) {  // presets made before signing in move to the account
        for (const p of local) await sendPreset(p.name, p.settings);
        presets = await (await fetch("/api/presets", { cache: "no-store" })).json();
        try { localStorage.removeItem("dyeroom-presets"); } catch (_) { /* ignore */ }
      }
    } catch (_) { presets = local; }
  }
  renderPresets();
}

async function sendPreset(name, presetSettings) {
  const response = await fetch("/api/presets", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, settings: presetSettings }),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || response.statusText);
  return body;
}

function openPresetSheet() {
  const inUse = presetInUse();
  $("preset-name").value = inUse ? inUse.name : "";
  $("preset-sheet").returnValue = "";  // not the answer from last time
  showSheet($("preset-sheet"));
  $("preset-name").focus();
}

async function savePreset() {
  const name = $("preset-name").value.split(/\s+/).filter(Boolean).join(" ").slice(0, 60);
  if (!name) return;
  const presetSettings = presetNow();
  try {
    if (onAccount()) {
      await sendPreset(name, presetSettings);
      presets = await (await fetch("/api/presets", { cache: "no-store" })).json();
    } else {
      presets = [...presets.filter((p) => p.name !== name), { name, settings: presetSettings }]
        .sort((a, b) => a.name.localeCompare(b.name));
      localStorage.setItem("dyeroom-presets", JSON.stringify(presets));
    }
    chosenPreset = name;
    setNotice(`Preset saved · ${name}`);
  } catch (e) {
    setNotice(e.message || "The preset could not be saved");
  }
  renderPresets();
}

function presetChangesDevelopment(item, presetSettings) {
  const done = item.doneSettings || {};
  return PRESET_KEYS.some((k) => k in presetSettings && String(done[k]) !== String(presetSettings[k]));
}

function applyPreset(preset, everyFrame = false) {
  const s = preset.settings;
  const take = (target) => PRESET_KEYS.forEach((k) => { if (k in s) target[k] = s[k]; });
  take(settings);
  chosenPreset = preset.name;
  syncControls();
  for (const item of everyFrame ? items : current ? [current] : []) {
    take(item.settings);
    item.adjust = cleanAdjust(s.adjust);
    record(item);
    if (item.uploadId && ["done", "failed"].includes(item.state) && presetChangesDevelopment(item, s)) develop(item);
  }
  syncAdjust();
  applyGrade();
  render();
}

async function deletePreset() {
  const inUse = presetInUse();
  if (!inUse || !window.confirm(`Delete the preset “${inUse.name}”?`)) return;
  if (onAccount() && inUse.id) {
    await fetch(`/api/presets/${inUse.id}`, { method: "DELETE" }).catch(() => {});
  }
  presets = presets.filter((p) => p !== inUse);
  chosenPreset = null;
  if (!onAccount()) {
    try { localStorage.setItem("dyeroom-presets", JSON.stringify(presets)); } catch (_) { /* ignore */ }
  }
  renderPresets();
}

function bindPresets() {
  bindMenu($("preset-button"), $("preset-menu"), presetMenu);
  $("preset-new").addEventListener("click", openPresetSheet);
  $("preset-sheet").addEventListener("close", () => {
    if ($("preset-sheet").returnValue === "save") savePreset();
  });
}

// The film, chosen from a menu that says what each one is.
const chip = (film) => `<span class="film-chip${film && film.kind === "mono" ? " mono" : ""}"></span>`;

function renderFilm() {
  const film = options && options.films ? options.films.find((f) => f.id === settings.film) : null;
  $("film-name").textContent = film ? film.name : "Sunday 64";
  $("film-chip").className = `film-chip${film && film.kind === "mono" ? " mono" : ""}`;
  $("pitch").textContent = film && film.kind === "mono"
    ? "Leave your photographs here, raw or from your phone. Each one is exposed on Monday 400, developed, stopped and fixed, "
      + "then enlarged onto paper and printed the way a darkroom would."
    : "Leave your photographs here, raw or from your phone. Each one is exposed on Sunday 64 and taken through the whole reversal "
      + "process, from the first developer to the bleach, before it reaches the light table.";
}

function rectIcon(w, h, extra = "") {
  return `<svg class="frame-size" viewBox="0 0 20 20" aria-hidden="true"><rect x="${(10 - w / 2).toFixed(2)}" `
    + `y="${(10 - h / 2).toFixed(2)}" width="${w.toFixed(2)}" height="${h.toFixed(2)}" rx="0.8"${extra}/></svg>`;
}

// Each format drawn to the same scale, so the bigger frames look bigger
function frameIcon(format) {
  const [w, h] = FORMAT_SIZES[format] || FORMAT_SIZES["35mm"];
  const k = 17 / 69.5;
  return rectIcon(w * k, h * k);
}

// A choice from a list, opened like the film and the presets (never the browser's own menu,
// which phones and narrow windows draw poorly). list() gives { value, text, note?, label? }
// entries; label, when given, is what the closed button shows.
const dropdowns = {};

function bindDropdown(id, { list, chosen, choose, heading = "", icon = () => "" }) {
  const root = $(id);
  root.innerHTML = `<button class="dropdown-button" type="button" aria-haspopup="menu" aria-expanded="false" `
    + `aria-controls="${id}-menu" aria-labelledby="${id}-label ${id}-name"><span class="dropdown-icon"></span>`
    + `<span class="dropdown-name" id="${id}-name"></span><svg class="chevron" viewBox="0 0 24 24" aria-hidden="true">`
    + `<path d="M7.5 10l4.5 4.5 4.5-4.5"/></svg></button>`
    + `<div class="menu" id="${id}-menu" role="menu" aria-labelledby="${id}-label" hidden></div>`;
  dropdowns[id] = () => {
    const now = chosen();
    const entry = list().find((e) => e.value === now);
    root.querySelector(".dropdown-name").textContent = entry ? entry.label || entry.text : now;
    root.querySelector(".dropdown-icon").innerHTML = icon(now);
  };
  bindMenu(root.querySelector("button"), $(`${id}-menu`), (close) => {
    const now = chosen();
    const items = list().map((e) => {
      const item = menuItem(icon(e.value), e.text, () => choose(e.value), close, e.value === now ? "chosen" : "", e.note);
      if (e.value === now) item.insertAdjacentHTML("beforeend", `<span class="menu-check">${ICON.check}</span>`);
      return item;
    });
    if (!heading) return items;
    return [Object.assign(document.createElement("p"), { className: "menu-label", textContent: heading }), ...items];
  });
}

function showDropdown(id) {
  if (dropdowns[id]) dropdowns[id]();
}

function chooseSetting(key) {
  return (value) => { settings[key] = value; syncControls(); };
}

function bindDevelopDropdowns() {
  const named = (values, names) => (values || []).map((v) => ({ value: v, text: names[v] || v }));
  bindDropdown("filter", { list: () => named(options && options.filters, FILTER_NAMES), chosen: () => settings.filter,
                           choose: chooseSetting("filter") });
  bindDropdown("bw-filter", { list: () => named(options && options.bw_filters, BW_FILTER_NAMES),
                              chosen: () => settings.bw_filter, choose: chooseSetting("bw_filter") });
  bindDropdown("format", {
    list: () => (options && options.formats ? options.formats : ["35mm"]).map((f) => {
      const [w, h] = FORMAT_SIZES[f] || [];
      return { value: f, text: FORMAT_NAMES[f] || f, label: FORMAT_LABELS[f],
               note: w ? `${w} × ${h} mm${f === "35mm" ? "" : ", on 120 film"}` : "" };
    }),
    chosen: () => settings.format,
    choose: chooseSetting("format"),
    heading: "Bigger frames, finer grain",
    icon: frameIcon,
  });
}

function bindFilm() {
  bindDevelopDropdowns();
  bindMenu($("film-button"), $("film-menu"), (close) => (options && options.films ? options.films : []).map((film) => {
    const item = menuItem(chip(film), film.name, () => { settings.film = film.id; syncControls(); },
                          close, film.id === settings.film ? "chosen" : "", film.note);
    if (film.id === settings.film) item.insertAdjacentHTML("beforeend", `<span class="menu-check">${ICON.check}</span>`);
    return item;
  }));
  bindMenu($("export-more"), $("export-menu"), (close) => {
    const shown = Boolean(current && current.doneJob);
    const done = items.filter((i) => i.doneJob).length;
    const one = [
      menuItem(ICON.download,
               "JPEG", () => exportFile($("export-jpg"), "jpg"), close, "", "8-bit with its colour profile, for sharing"),
      menuItem(ICON.download,
               "TIFF", () => exportFile($("export-jpg"), "tif"), close, "", "16-bit, for further editing"),
    ];
    one.forEach((b) => { b.disabled = !shown; });
    const label = document.createElement("p");
    label.className = "menu-label";
    label.textContent = `The whole roll · ${done} ${done === 1 ? "frame" : "frames"}`;
    return [...one, Object.assign(document.createElement("div"), { className: "menu-sep" }), label,
      menuItem(ICON.all, "Roll as JPEG", () => exportRoll("jpg"), close, "", "Every developed frame in one ZIP"),
      menuItem(ICON.all, "Roll as TIFF", () => exportRoll("tif"), close, "", "16-bit, every frame in one ZIP")];
  });
}

// --- colourising, on your own computer -----------------------------------------------------
// The model is not part of the install: the page fetches it once, when it is first wanted.

const GET_COLOUR = "Get colourising (270 MB, once)";

async function getColourising() {
  const button = $("get-colour");
  button.disabled = true;
  try {
    let status = await (await fetch("/api/colourise-model", { method: "POST" })).json();
    while (status.state === "fetching") {
      button.textContent = status.total ? `Getting the model, ${Math.floor((100 * status.done) / status.total)} %`
        : "Getting the model";
      await new Promise((resolve) => setTimeout(resolve, 700));
      status = await (await fetch("/api/colourise-model")).json();
    }
    if (status.available) {
      options.colourise = true;
      options.colourise_download = false;
      setNotice("Colourising is ready");
    } else {
      setNotice(status.error || "The model could not be fetched");
    }
  } catch (_) {
    setNotice("The model could not be fetched");
  }
  button.disabled = false;
  button.textContent = GET_COLOUR;
  render();
}

// --- photographs are not kept ---------------------------------------------------------------
// The server holds a photograph only while this page works on it: the page says so every two
// minutes, lets go of everything when it closes, and Clear deletes it all at once.

const heldUploads = () => items.filter((i) => i.uploadId).map((i) => i.uploadId);

function forgetUploads(uploads, beacon = false) {
  if (!uploads.length) return null;
  const body = JSON.stringify({ uploads });
  if (beacon) return navigator.sendBeacon("/api/forget", new Blob([body], { type: "application/json" }));
  return fetch("/api/forget", { method: "POST", headers: { "Content-Type": "application/json" }, body })
    .catch(() => {});
}

function bindPrivacy() {
  setInterval(() => {
    const uploads = heldUploads();
    if (!uploads.length) return;
    fetch("/api/keep", { method: "POST", headers: { "Content-Type": "application/json" },
                         body: JSON.stringify({ uploads }) }).catch(() => {});
  }, 120000);
  window.addEventListener("pagehide", () => forgetUploads(heldUploads(), true));
  window.addEventListener("pageshow", (e) => { if (e.persisted && items.length) location.reload(); });
  $("clear").addEventListener("click", clearLab);
}

async function clearLab() {
  if (!items.length) return;
  const busy = items.some((i) => ["uploading", "queued", "running"].includes(i.state));
  const what = items.length === 1 ? "this frame" : `all ${items.length} frames`;
  if (!window.confirm(`Delete ${what} from the lab now? Download anything you want to keep first.`
    + (busy ? " Frames still in the developer are deleted as they come out." : ""))) return;
  const uploads = heldUploads();
  items.forEach((i) => { i.cleared = true; });
  items.length = 0;
  uploadQueue.length = 0;
  current = null;
  render();
  await forgetUploads(uploads);
}

function privacyText(long) {
  const p = options && options.privacy;
  if (!p) return "";
  if (options.local) {
    return long ? "Your photographs stay on this computer. Dyeroom works on copies in its own folder while "
      + "you work and deletes them when it next starts. The one thing it sends out is a question to PyPI, once "
      + "a day, whether a newer version is there." : "Nothing leaves this computer.";
  }
  if (!long) return "Nothing is stored: your photographs are deleted when you leave.";
  const where = p.in_memory ? "in the server's memory, never on a disk, and only while you work" : "only while you work";
  const hours = p.keep_hours === 1 ? "an hour" : `${String(p.keep_hours).replace(/\.0$/, "")} hours`;
  return `Your photographs are never stored. They are held ${where}, and deleted as soon as you close the page, `
    + `after ${p.idle_minutes} minutes without activity, or ${hours} after upload at the latest. `
    + `There are no copies and no backups${options.accounts ? "; only your account and what you bought are kept" : ""}.`;
}

// --- compare -----------------------------------------------------------------------------

function setCompare(mode) {
  // Raw and Slide are a pair: choosing the one already shown switches to the other.
  if (mode === compareMode() && (mode === "raw" || mode === "slide")) mode = mode === "raw" ? "slide" : "raw";
  compare = mode;
  saveCompare();
  renderViewer();
}

// Holding Space shows the raw until it is let go; the chosen comparison is not changed.
let heldCompare = null;
function holdRaw(down) {
  if (down && heldCompare === null && current && current.doneJob) {
    heldCompare = compare;
    compare = "raw";
    renderViewer();
  } else if (!down && heldCompare !== null) {
    compare = heldCompare;
    heldCompare = null;
    renderViewer();
  }
}

function toggleFullscreen() {
  const viewer = document.querySelector(".viewer");
  const active = document.fullscreenElement || document.webkitFullscreenElement;
  if (active) (document.exitFullscreen || document.webkitExitFullscreen).call(document);
  else (viewer.requestFullscreen || viewer.webkitRequestFullscreen).call(viewer);
}

// Previous falls back to Split for a frame developed only once.
function compareMode() {
  return compare === "previous" && !(current && current.previous) ? "split" : compare;
}

// Only the settings that changed between two developments, in a few words each.
function settingsDiff(was, now) {
  const words = {
    film: (s) => filmName(s.film), view: (s) => VIEW_NAMES[s.view],
    light: (s) => (s.light === "balanced" ? "daylight balanced" : "light as it was"),
    filter: (s) => (s.filter === "auto" ? "filter for the light" : s.filter === "none" ? "no filter" : `${s.filter} filter`),
    bw_filter: (s) => (s.bw_filter === "none" ? "no filter" : `${s.bw_filter} filter`),
    exposure: (s) => (s.exposure === "auto" ? "auto exposure" : "as shot"), ev: (s) => `${formatEv(s.ev)} EV`,
    rating: (s) => `EI ${s.rating}`, grade: (s) => `grade ${s.grade}`,
    toning: (s) => (s.toning === "none" ? "untoned" : `selenium ${s.toning}`),
    grain: (s) => (s.grain ? "grain" : "no grain"), size: (s) => (s.size === "full" ? "full size" : "draft"),
    format: (s) => FORMAT_NAMES[s.format || "35mm"],
    sharpness: (s) => `sharpness ${signed(s.sharpness || 0)}`, clarity: (s) => `clarity ${signed(s.clarity || 0)}`,
    colourise: (s) => (s.colourise ? "AI colours" : "own colours"),
  };
  const colourKeys = ["view", "light", "filter"];
  const monoKeys = ["rating", "grade", "bw_filter", "toning"];
  const keys = was.film !== now.film ? ["film"] : Object.keys(words).filter((k) => k !== "film"
    && !(isMono(now) ? colourKeys : monoKeys).includes(k) && String(was[k]) !== String(now[k]));
  const say = (s) => keys.slice(0, 2).map((k) => words[k](s)).join(" · ");
  return [say(was), say(now)];
}

function setSplit(percent) {
  split = Math.min(100, Math.max(0, percent));
  $("frame").style.setProperty("--split", `${split}%`);
  $("divider").style.left = `${split}%`;
}

// --- looking closer ----------------------------------------------------------------------
// Pinch (or pinch on a trackpad) to look closer, drag to look around, double-tap or double-click
// to go in or back out. The zoom stays when the comparison changes, so the raw and the slide
// can be compared up close; another frame, or the crop, starts from the whole picture again.
function resetZoom() { zoom = { z: 1, u: 0.5, v: 0.5 }; }

// As far as two screen pixels to a pixel of the picture, and never less than twice
const zoomMax = (k) => Math.max(2, 2 / k);

// The point of the picture under (x, y) on the screen, as a fraction of its width and height
function pictureAt(x, y) {
  const box = $("frame").getBoundingClientRect();
  return { u: (x - box.left - view.px) / view.pw, v: (y - box.top - view.py) / view.ph };
}

// Zoom to z with the picture point (u, v) under the screen point (x, y)
function zoomTo(z, u, v, x, y) {
  const stage = $("stage"), box = stage.getBoundingClientRect(), style = getComputedStyle(stage);
  // the frame is centred in the stage's room, inside its padding
  const cx = box.left + (parseFloat(style.paddingLeft) + stage.clientWidth - parseFloat(style.paddingRight)) / 2;
  const cy = box.top + (parseFloat(style.paddingTop) + stage.clientHeight - parseFloat(style.paddingBottom)) / 2;
  const z1 = Math.min(Math.max(z, 1), zoomMax(view.k));
  const pw = (view.pw / view.z) * z1, ph = (view.ph / view.z) * z1;
  zoom = { z: z1, u: u + (cx - x) / pw, v: v + (cy - y) / ph };
  layoutFrame();
}

function bindCompare() {
  const frame = $("frame");
  const pointers = new Map();
  let gesture = null;  // {kind: "split" | "pan" | "pinch", ...}
  let tap = null;      // the last short touch, for a double-tap
  let touched = false; // the last pointer was a finger: its double-tap is handled here, not as a double-click
  const splitAt = (e) => {
    const box = frame.getBoundingClientRect();
    setSplit(((e.clientX - box.left) / box.width) * 100);
  };
  const mid = () => {
    const [a, b] = [...pointers.values()];
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, d: Math.hypot(a.x - b.x, a.y - b.y) };
  };
  const inOrOut = (x, y) => {
    const p = pictureAt(x, y);
    zoomTo(zoom.z > 1.001 ? 1 : Math.max(2.5, 1 / (view.k * devicePixelRatio)), p.u, p.v, x, y);
  };
  frame.addEventListener("pointerdown", (e) => {
    if (cropping || !view) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    try { frame.setPointerCapture(e.pointerId); } catch (_) { /* a pointer already gone */ }
    touched = e.pointerType === "touch";
    if (pointers.size === 2) {
      if (gesture && gesture.kind === "split") setSplit(gesture.was);  // the first finger was a pinch's, not a split
      const m = mid();
      gesture = { kind: "pinch", z: zoom.z, d: m.d, ...pictureAt(m.x, m.y) };
    } else if (pointers.size === 1) {
      if (e.pointerType === "touch" && tap && e.timeStamp - tap.t < 320 && Math.hypot(e.clientX - tap.x, e.clientY - tap.y) < 30) {
        setSplit(tap.was);  // a double-tap: the split stays where it was before the first
        tap = { ...tap, second: true };
        gesture = null;
        return;
      }
      tap = { t: e.timeStamp, x: e.clientX, y: e.clientY, was: split };
      // Zoomed in, a drag looks around, and only the divider itself moves the split
      const splits = frame.classList.contains("split") && (zoom.z <= 1.001 || e.target.closest("#divider"));
      gesture = splits ? { kind: "split", was: split }
        : zoom.z > 1.001 ? { kind: "pan", x: e.clientX, y: e.clientY, u: zoom.u, v: zoom.v } : null;
      if (splits) splitAt(e);
    }
  });
  frame.addEventListener("pointermove", (e) => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (tap && Math.hypot(e.clientX - tap.x, e.clientY - tap.y) > 10) tap = null;  // a drag, not a tap
    if (!gesture) return;
    if (gesture.kind === "split") splitAt(e);
    else if (gesture.kind === "pan") {
      zoom = { z: zoom.z, u: gesture.u - (e.clientX - gesture.x) / view.pw, v: gesture.v - (e.clientY - gesture.y) / view.ph };
      layoutFrame();
    } else if (gesture.kind === "pinch" && pointers.size === 2) {
      const m = mid();
      zoomTo(gesture.z * (m.d / Math.max(1, gesture.d)), gesture.u, gesture.v, m.x, m.y);
    }
  });
  const end = (e) => {
    if (!pointers.delete(e.pointerId)) return;
    if (gesture && gesture.kind === "pinch" && pointers.size === 1) {  // one finger lifted: the other looks around
      const [p] = [...pointers.values()];
      gesture = zoom.z > 1.001 ? { kind: "pan", x: p.x, y: p.y, u: zoom.u, v: zoom.v } : null;
      tap = null;
    } else if (!pointers.size) {
      gesture = null;
      if (tap && tap.second && e.type === "pointerup") {
        tap = null;
        inOrOut(e.clientX, e.clientY);
      }
    }
  };
  frame.addEventListener("pointerup", end);
  frame.addEventListener("pointercancel", end);
  frame.addEventListener("dblclick", (e) => { if (!cropping && view && !touched) inOrOut(e.clientX, e.clientY); });
  // A trackpad pinch arrives as a wheel with Ctrl held; zoomed in, two fingers look around
  frame.addEventListener("wheel", (e) => {
    if (cropping || !view) return;
    if (e.ctrlKey) {
      e.preventDefault();
      const p = pictureAt(e.clientX, e.clientY);
      zoomTo(zoom.z * Math.exp(-e.deltaY * 0.01), p.u, p.v, e.clientX, e.clientY);
    } else if (zoom.z > 1.001) {
      e.preventDefault();
      zoom = { z: zoom.z, u: zoom.u + e.deltaX / view.pw, v: zoom.v + e.deltaY / view.ph };
      layoutFrame();
    }
  }, { passive: false });
}

// --- drag and drop, keys -------------------------------------------------------------------

function bindDrop() {
  let depth = 0;
  const hasFiles = (e) => Array.from((e.dataTransfer && e.dataTransfer.types) || []).includes("Files");
  window.addEventListener("dragenter", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    depth++;
    $("veil").classList.add("on");
  });
  window.addEventListener("dragleave", (e) => {
    if (!hasFiles(e)) return;
    depth = Math.max(0, depth - 1);
    if (!depth) $("veil").classList.remove("on");
  });
  window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    depth = 0;
    $("veil").classList.remove("on");
    if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  });
  $("picker").addEventListener("change", (e) => { addFiles(e.target.files); e.target.value = ""; });
}

function bindKeys() {
  const typing = () => {
    const el = document.activeElement;
    return el.tagName === "TEXTAREA" || el.tagName === "SELECT" || (el.tagName === "INPUT" && el.type !== "range");
  };
  const blocked = () => typing() || document.querySelector("dialog[open]") || openMenus.size > 0;
  const press = (id) => { if (!$(id).disabled && !$(id).hidden) $(id).click(); };
  window.addEventListener("keydown", (e) => {
    if (e.key === "?" && !typing()) {  // the list of shortcuts, from anywhere but a text field
      if (!$("keys-sheet").open) showSheet($("keys-sheet"));
      e.preventDefault();
      return;
    }
    const letter = e.key.toLowerCase();
    if ((e.metaKey || e.ctrlKey) && !e.altKey && !blocked() && (letter === "z" || (e.ctrlKey && letter === "y"))) {
      step(e.shiftKey || letter === "y" ? 1 : -1);
      e.preventDefault();
      return;
    }
    if (blocked() || e.metaKey || e.ctrlKey || e.altKey) return;
    const onSlider = document.activeElement.type === "range";
    if (cropping && (e.key === "Enter" || e.key === "Escape" || e.key.toLowerCase() === "r")) {
      finishCrop();
      e.preventDefault();
      return;
    }
    if (cropping && (e.key === "[" || e.key === "]")) {
      turn(e.key === "]" ? 1 : -1);
      e.preventDefault();
      return;
    }
    const shown = current && current.doneJob && !cropping;
    const i = items.indexOf(current);
    const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    let handled = true;
    if ((key === "ArrowDown" || key === "ArrowRight") && !onSlider) {
      if (i < items.length - 1) { current = items[i + 1]; render(); }
    } else if ((key === "ArrowUp" || key === "ArrowLeft") && !onSlider) {
      if (i > 0) { current = items[i - 1]; render(); }
    } else if (key === " " && shown) {
      if (!e.repeat) holdRaw(true);
    } else if (key === "\\" && shown) {
      setCompare(compareMode() === "raw" ? "slide" : "raw");
    } else if (["1", "2", "3", "4"].includes(key) && shown) {
      const mode = ["split", "raw", "previous", "slide"][Number(key) - 1];
      if (mode !== "previous" || current.previous) { compare = mode; saveCompare(); renderViewer(); }
    } else if (key === "c" && shown) {
      const order = ["split", "raw", ...(current.previous ? ["previous"] : []), "slide"];
      setCompare(order[(order.indexOf(compareMode()) + 1) % order.length]);
    } else if (key === "r") {
      openTab("crop");
    } else if (key === "f") {
      toggleFullscreen();
    } else if (key === "d") {
      press("again");
    } else if (key === "e") {
      if (!$("export-jpg").disabled) exportFile($("export-jpg"), e.shiftKey ? "tif" : "jpg");
    } else if (key === "o") {
      if (needsSignIn()) openSignIn(); else $("picker").click();
    } else if ((key === "Delete" || key === "Backspace") && current) {
      if (window.confirm(`Remove ${current.name} from the lab?`)) removeFrame(current);
    } else {
      handled = false;
    }
    if (handled) e.preventDefault();
  });
  window.addEventListener("keyup", (e) => {
    if (e.key === " " && heldCompare !== null) { holdRaw(false); e.preventDefault(); }
  });
  window.addEventListener("blur", () => holdRaw(false));
  $("keys-open").addEventListener("click", () => showSheet($("keys-sheet")));
  $("fullscreen").addEventListener("click", toggleFullscreen);
  document.addEventListener("fullscreenchange", layoutFrame);
  document.addEventListener("webkitfullscreenchange", layoutFrame);
}

// --- a coffee ----------------------------------------------------------------------------

// The free lab asks for a coffee after the fifth of your own photographs developed in this
// browser, again much later, then never; and never again once you have gone to give. Each
// photograph counts once, however often it is developed again.
const COFFEE_AT = { 5: "Five", 40: "Forty", 120: "A hundred and twenty" };

function coffeeState() {
  try { return JSON.parse(localStorage.getItem("dyeroom-coffee") || "{}"); } catch (_) { return {}; }
}

function countForCoffee(item) {
  if (item.counted || item.sample || !options || !options.donate || options.accounts) return;
  item.counted = true;
  const state = coffeeState();
  state.developed = (state.developed || 0) + 1;
  try { localStorage.setItem("dyeroom-coffee", JSON.stringify(state)); } catch (_) { /* ignore */ }
  if (!state.gave && COFFEE_AT[state.developed]) {
    setTimeout(() => showCoffee(item, state.developed), 1200);  // the frame first, then the ask
  }
}

function showCoffee(item, count) {
  $("coffee-title").textContent = `${COFFEE_AT[count]} frames developed`;
  $("coffee-frame").src = `/api/jobs/${item.doneJob}/view.jpg`;
  $("coffee-go").href = options.donate;
  $("coffee-note").hidden = false;
}

function bindCoffee() {
  $("coffee-later").addEventListener("click", () => { $("coffee-note").hidden = true; });
  $("coffee-go").addEventListener("click", () => {
    const state = coffeeState();
    state.gave = true;
    try { localStorage.setItem("dyeroom-coffee", JSON.stringify(state)); } catch (_) { /* ignore */ }
    $("coffee-note").hidden = true;
  });
}

// --- undo ------------------------------------------------------------------------------

// Each frame keeps the states of its finishing (Colour, Tones, Crop), one per finished
// gesture: a slider or wheel let go, a crop drawn, a turn, a preset. Undo and Redo step
// through them. Developing again and the develop settings are not part of it.
const HISTORY_MAX = 100;
let pending = null;   // the frame with a change not yet kept as a step
let pendingTimer = null;
let held = false;     // a pointer is down: a drag is one step, kept when it ends

const stateOf = (item) => JSON.stringify({ adjust: item.adjust, geometry: item.geometry || null });

function record(item) {
  if (!item) return;
  const now = stateOf(item);
  if (!item.history) { item.history = [now]; item.at = 0; return; }
  if (now === item.history[item.at]) return;
  item.history.splice(item.at + 1);
  item.history.push(now);
  if (item.history.length > HISTORY_MAX) item.history.shift();
  item.at = item.history.length - 1;
}

function keepPending() {
  clearTimeout(pendingTimer);
  if (pending) record(pending);
  pending = null;
  renderUndo();
}

function noteEdit() {
  if (!current || !current.history) return;
  if (pending && pending !== current) keepPending();
  pending = current;
  clearTimeout(pendingTimer);
  if (!held) pendingTimer = setTimeout(keepPending, 400);
  renderUndo();
}

function step(by) {  // -1 undo, +1 redo
  keepPending();
  const item = current;
  if (!item || !item.history) return;
  const at = item.at + by;
  if (at < 0 || at >= item.history.length) return;
  item.at = at;
  const { adjust, geometry } = JSON.parse(item.history[at]);
  item.adjust = adjust;
  item.geometry = geometry;
  syncAdjust();
  applyGrade();
  layoutFrame();
  syncCrop();
  renderInspector();
  keepPending();
}

function renderUndo() {
  const item = current;
  const changed = Boolean(item && item.history && stateOf(item) !== item.history[item.at]);
  $("undo").disabled = !item || !item.history || (item.at === 0 && !changed);
  $("redo").disabled = !item || !item.history || changed || item.at >= item.history.length - 1;
}

function bindUndo() {
  const mod = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl+";
  $("undo").title = `Undo (${mod}Z)`;
  $("redo").title = `Redo (Shift+${mod}Z)`;
  if (mod !== "⌘") document.querySelectorAll("kbd.mod").forEach((k) => { k.textContent = "Ctrl"; });
  $("undo").addEventListener("click", () => step(-1));
  $("redo").addEventListener("click", () => step(1));
  window.addEventListener("pointerdown", () => { held = true; }, true);
  const release = () => {
    held = false;
    if (pending) { clearTimeout(pendingTimer); pendingTimer = setTimeout(keepPending, 400); }
  };
  window.addEventListener("pointerup", release, true);
  window.addEventListener("pointercancel", release, true);
}

// --- panel widths ------------------------------------------------------------------------

// The frames and the tools can be dragged wider or narrower. Widths are remembered, and
// squeezed (not forgotten) while the window is too small to leave the picture its room.
const PANES = { library: { min: 200, max: 440 }, inspector: { min: 300, max: 520 } };
const VIEWER_MIN = 420;
// The stacked layout of phones, tablets and foldables (style.css): no side panels to size there
const STACKED = "(max-width: 860px), (max-width: 1100px) and (max-aspect-ratio: 11/10), "
  + "(pointer: coarse) and (max-width: 1366px), (horizontal-viewport-segments: 2), (vertical-viewport-segments: 2)";
const phoneLayout = window.matchMedia(STACKED);
// A phone held upright: the frames are a tab of their own, so the tools get the strip's room (style.css)
const framesTab = window.matchMedia("(max-width: 699px) and (orientation: portrait)");
let paneWidths = {};

function setPane(name, width) {
  const { min, max } = PANES[name];
  const other = $(name === "library" ? "inspector" : "library").getBoundingClientRect().width;
  const w = Math.round(Math.max(min, Math.min(width, max, window.innerWidth - VIEWER_MIN - other)));
  document.querySelector(".workspace").style.setProperty(`--${name}-w`, `${w}px`);
  return w;
}

function describePane(name) {
  const splitter = $(`split-${name}`);
  splitter.setAttribute("aria-valuemin", PANES[name].min);
  splitter.setAttribute("aria-valuemax", PANES[name].max);
  splitter.setAttribute("aria-valuenow", Math.round($(name).getBoundingClientRect().width));
}

function applyPanes() {
  if (phoneLayout.matches) return;
  const workspace = document.querySelector(".workspace");
  for (const name of Object.keys(PANES)) {
    if (paneWidths[name]) {
      setPane(name, paneWidths[name]);
    } else {  // the usual width for this window, narrowed if the picture would lack room
      workspace.style.removeProperty(`--${name}-w`);
      setPane(name, $(name).getBoundingClientRect().width);
    }
    describePane(name);
  }
}

function savePane(name, width) {
  if (width === null) delete paneWidths[name];
  else paneWidths[name] = width;
  applyPanes();
  try { localStorage.setItem("dyeroom-panes", JSON.stringify(paneWidths)); } catch (_) { /* ignore */ }
}

function bindPanes() {
  try { paneWidths = JSON.parse(localStorage.getItem("dyeroom-panes") || "{}") || {}; } catch (_) { paneWidths = {}; }
  document.querySelectorAll(".splitter").forEach((splitter) => {
    const name = splitter.dataset.pane;
    const sign = name === "library" ? 1 : -1;  // the frames widen to the right, the tools to the left
    let drag = null;
    splitter.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      drag = { x: e.clientX, width: $(name).getBoundingClientRect().width, last: null };
      splitter.setPointerCapture(e.pointerId);
      splitter.classList.add("dragging");
      document.body.classList.add("resizing");
      e.preventDefault();
    });
    splitter.addEventListener("pointermove", (e) => {
      if (drag) drag.last = setPane(name, drag.width + sign * (e.clientX - drag.x));
    });
    const end = () => {
      if (!drag) return;
      if (drag.last !== null) savePane(name, drag.last);
      drag = null;
      splitter.classList.remove("dragging");
      document.body.classList.remove("resizing");
    };
    splitter.addEventListener("pointerup", end);
    splitter.addEventListener("pointercancel", end);
    splitter.addEventListener("dblclick", () => savePane(name, null));
    splitter.addEventListener("keydown", (e) => {
      const width = $(name).getBoundingClientRect().width;
      const step = e.shiftKey ? 48 : 16;
      const target = { ArrowLeft: width - sign * step, ArrowRight: width + sign * step,
                       Home: PANES[name].min, End: PANES[name].max }[e.key];
      if (e.key === "Enter") savePane(name, null);
      else if (target !== undefined) savePane(name, setPane(name, target));
      else return;
      e.preventDefault();
      e.stopPropagation();
    });
  });
  window.addEventListener("resize", applyPanes);
  phoneLayout.addEventListener("change", applyPanes);
  framesTab.addEventListener("change", () => render());  // turned sideways: the Frames tab goes, the strip is back
  applyPanes();
}

// --- start -------------------------------------------------------------------------------

async function start() {
  loadCompare();
  const now = new Date();
  $("mount-date").textContent = `${now.toLocaleString("en", { month: "short" }).toUpperCase()} ${now.getFullYear()}`;
  try { grader = new Grader($("graded")); } catch (_) { grader = null; /* no WebGL 2: no live adjustments */ }
  try { graderBefore = grader && new Grader($("graded-before")); } catch (_) { graderBefore = null; }
  lab = new Lab($("lab"), labPhase);
  bindControls();
  bindAdjust();
  bindCompare();
  bindDrop();
  bindKeys();
  bindPrivacy();
  bindPresets();
  bindFilm();
  setSplit(50);
  new ResizeObserver(() => layoutFrame()).observe($("stage"));  // the window, a panel dragged, full screen
  bindPanes();
  bindUndo();
  bindCoffee();
  bindCrop();
  try { activeTab = lastTab = localStorage.getItem("dyeroom-tab") || "develop"; } catch (_) { /* ignore */ }
  if (!["develop", "colour", "tones"].includes(activeTab)) activeTab = lastTab = "develop";
  document.addEventListener("input", (e) => { if (e.target.type === "range") paintRange(e.target); });
  try {
    options = await (await fetch("/api/options")).json();
    if (!(options.formats || []).includes(settings.format)) settings.format = "35mm";
    if (options.films && !options.films.some((f) => f.id === settings.film)) settings.film = "sunday64";
    $("picker").accept = options.accepted.join(",");
    $("fact-formats-note").textContent = `Cameras and phones, up to ${options.max_mb} MB`;
    $("fact-formats").title = "RAF, NEF, CR3, CR2, ARW, DNG, ORF, RW2, PEF and more, or JPEG, HEIC, TIFF and PNG";
    $("sample").hidden = !options.sample;
    document.querySelectorAll(".contact-link").forEach((a) => {
      a.hidden = !options.contact;
      if (options.contact) a.href = `mailto:${options.contact}`;
    });
    $("privacy-about").textContent = privacyText(true);
    $("fact-privacy").title = privacyText(true);
    $("fact-privacy").hidden = $("about-privacy").hidden = !options.privacy;
    document.querySelectorAll(".refunds-link").forEach((a) => { a.hidden = !options.accounts; });  // nothing sold
    if (options.donate && !options.accounts) {  // free: a coffee, if they like it
      document.querySelectorAll("#fact-free, .donate-link").forEach((a) => { a.href = options.donate; a.hidden = false; });
      $("about-free").hidden = false;
    }
    $("local-offer").hidden = Boolean(options.local);  // already on your own computer
    if (options.local) {  // the lab on this computer: no service terms, and nothing leaves it
      document.querySelectorAll(".legal-links a:not(.source-link)").forEach((a) => { a.hidden = true; });
      $("fact-privacy").querySelector("b").textContent = "On this computer";
      $("fact-privacy").querySelector("b + span").textContent = "Nothing is uploaded";
      setInterval(() => fetch("/api/here").catch(() => {}), 60000);  // the lab runs while a window is open
      if (options.update) {
        $("update-status").querySelector("span").textContent = `Dyeroom ${options.update} is out`;
        $("update-status").hidden = false;
      }
    }
    if (!options.full) {
      $("size-full").disabled = true;
      settings.size = "draft";
    }
    if (options.accounts) {
      renderProviders();
      await refreshMe();
    }
    await loadPresets();
  } catch (_) { /* server unreachable: drops will report the error */ }
  const query = new URLSearchParams(location.search);
  const signin = query.get("signin");
  if (signin === "failed" || signin === "later") {
    setNotice(signin === "later" ? "Many sign-ins from here just now: try again in a few minutes."
      : "Sign-in did not complete. Please try again.");
  }
  if (query.toString()) history.replaceState(null, "", "/app");
  // The guides link to a film's sample as /app?sample=1&film=monday400: load that film first
  const film = query.get("film");
  if (film && options && (options.films || []).some((f) => f.id === film)) {
    settings.film = film;
  }
  syncControls();
  render();
  // "Try a sample" on the home page comes here as /app?sample=1: start it at once
  if (query.get("sample") === "1" && options && options.sample && !items.length) trySample();
}

start();
