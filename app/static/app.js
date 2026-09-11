const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const submitBtn = document.getElementById("submit-btn");
const statusBox = document.getElementById("status");
const resultSection = document.getElementById("result");
const resultHeading = document.getElementById("result-heading");
const finalScoreValue = document.getElementById("final-score-value");
const componentsBody = document.querySelector("#components tbody");
const resultMeta = document.getElementById("result-meta");
const tabsBox = document.getElementById("dataset-tabs");
const datasetNote = document.getElementById("dataset-note");

const METRIC_NAMES = {
  SC: "Spatial correlation",
  TC: "Temporal correlation",
  RMSE: "RMSE (normalized)",
  LocErr: "Localization error",
};

// Which ground truth the submission is scored against. Set from the tabs.
let selectedDataset = null;
// key -> label, so history rows can name a dataset the server only sends a key for
const datasetLabels = {};
// True from the moment a submission is sent until its result (or error) lands.
let submitting = false;


function setStatus(message) {
  statusBox.textContent = message;
  statusBox.classList.toggle("hidden", !message);
}

// Enabled only once a dataset tab and a file are both chosen, and never while a
// submission is still in flight.
function refreshSubmitState() {
  submitBtn.disabled = submitting || !selectedDataset || !fileInput.files[0];
}

// Metric breakdown rows, shared by the result table and the history tooltips,
// so both always name and round the metrics the same way.
function metricRows(components) {
  return Object.entries(components || {}).map(([code, info]) => ({
    name: METRIC_NAMES[code] || code,
    score: info.score,
    weight: info.weight,
  }));
}

// Show who is logged in (the page is only reachable when authenticated).
(async function showUser() {
  try {
    const resp = await fetch("/me");
    if (!resp.ok) return;
    const user = await resp.json();
    document.getElementById("user-name").textContent =
      "Logged in as " + (user.username || user.email || user.name || "user") + " · ";
    document.getElementById("userbar").classList.remove("hidden");
  } catch (_) { /* ignore */ }
})();

// Build one tab per ground-truth dataset. A dataset the server has no data for
// is shown but not selectable, so the set of tabs stays the same for everyone.
async function loadDatasets() {
  let items = [];
  try {
    const resp = await fetch("/datasets");
    if (resp.status === 401) {   // session expired before the page finished loading
      window.location.href = "/login";
      return;
    }
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    items = await resp.json();
  } catch (err) {
    datasetNote.textContent = `Could not load the dataset list: ${err.message}`;
    datasetNote.classList.remove("hidden");
    return;
  }

  tabsBox.innerHTML = "";
  for (const item of items) {
    datasetLabels[item.key] = item.label;

    const tab = document.createElement("button");
    tab.type = "button";           // not a submit button inside the form
    tab.className = "tab";
    tab.textContent = item.label;
    tab.dataset.key = item.key;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", "false");

    if (item.available) {
      tab.addEventListener("click", () => selectDataset(item.key));
    } else {
      tab.disabled = true;
      tab.title = `${item.label} ground truth is not available on this server`;
    }
    tabsBox.appendChild(tab);
  }

  const firstAvailable = items.find((it) => it.available);
  if (firstAvailable) {
    selectDataset(firstAvailable.key);
  } else {
    datasetNote.textContent =
      "No ground-truth datasets are available on this server. Please contact the organizers.";
    datasetNote.classList.remove("hidden");
  }
}

function selectDataset(key) {
  selectedDataset = key;
  for (const tab of tabsBox.querySelectorAll(".tab")) {
    const active = tab.dataset.key === key;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  }
  // The result stands until the next submission replaces it: switching tabs to
  // line up another dataset must not throw away what was just scored. It names
  // its own dataset, so it stays unambiguous next to a different active tab.
  // Same for the status line -- clearing it mid-scoring would look like the
  // upload had been dropped.
  if (!submitting) setStatus("");
  refreshSubmitState();
}
loadDatasets();

// Load and render the logged-in user's submission history (newest first).
async function loadHistory() {
  try {
    const resp = await fetch("/submissions");
    if (!resp.ok) return;
    const items = await resp.json();

    const tbody = document.querySelector("#history-table tbody");
    const table = document.getElementById("history-table");
    const empty = document.getElementById("history-empty");
    const hint = document.getElementById("history-hint");
    tbody.innerHTML = "";

    if (!items.length) {
      table.classList.add("hidden");
      if (hint) hint.classList.add("hidden");
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");

    let anyDetail = false;
    for (const it of items) {
      // render in Mountain time with the zone label
      const when = it.created_at
        ? new Date(it.created_at).toLocaleString("en-US", {
            timeZone: "America/Denver", timeZoneName: "short",
            year: "numeric", month: "short", day: "2-digit",
            hour: "2-digit", minute: "2-digit", second: "2-digit",
          })
        : (it.timestamp || "");
      const score = (typeof it.final_score === "number") ? it.final_score.toFixed(4) : "—";
      // submissions scored before datasets were selectable have no dataset
      const dataset = it.dataset_label || datasetLabels[it.dataset] || it.dataset || "—";

      const row = document.createElement("tr");
      // textContent (not innerHTML) so a crafted filename can't inject markup
      [when, dataset, it.filename || "", it.num_beats ?? ""].forEach((val) => {
        const td = document.createElement("td");
        td.textContent = val;
        row.appendChild(td);
      });
      row.appendChild(scoreCell(score, it.components));
      if (metricRows(it.components).length) anyDetail = true;
      tbody.appendChild(row);
    }
    table.classList.remove("hidden");
    if (hint) hint.classList.toggle("hidden", !anyDetail);
  } catch (_) { /* ignore */ }
}
loadHistory();

// The score cell, carrying the metric breakdown as a card that opens on hover,
// on keyboard focus, and on tap. The card holds a table of its own, so anything
// selecting history rows wants "#history-table > tbody > tr", not a descendant
// selector, which would also match the rows inside these cards.
function scoreCell(score, components) {
  const cell = document.createElement("td");
  const rows = metricRows(components);
  if (!rows.length) {          // nothing recorded for this submission
    cell.textContent = score;
    return cell;
  }

  cell.className = "score-cell";
  cell.tabIndex = 0;
  cell.setAttribute("aria-label",
    `Score ${score}. Breakdown: ` +
    rows.map((r) => `${r.name} ${r.score.toFixed(4)}`).join(", "));

  const value = document.createElement("span");
  value.className = "score-value";
  value.textContent = score;
  cell.appendChild(value);

  const card = document.createElement("div");
  card.className = "detail-card";
  const table = document.createElement("table");

  const head = document.createElement("tr");
  ["Metric", "Score", "Weight"].forEach((label) => {
    const th = document.createElement("th");
    th.textContent = label;
    head.appendChild(th);
  });
  table.appendChild(head);

  for (const r of rows) {
    const tr = document.createElement("tr");
    [r.name, r.score.toFixed(4), r.weight.toFixed(3)].forEach((val) => {
      const td = document.createElement("td");
      td.textContent = val;
      tr.appendChild(td);
    });
    table.appendChild(tr);
  }
  card.appendChild(table);
  cell.appendChild(card);
  return cell;
}

// handle uploaded file input
fileInput.addEventListener("change", () => {
  refreshSubmitState();
  if (!submitting) setStatus("");
});

// handle form submission for scoring
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = fileInput.files[0];
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".zip")) {
    setStatus("Please choose a .zip file.");
    return;
  }
  if (!selectedDataset) {
    setStatus("Please choose which ground-truth dataset to score against.");
    return;
  }
  // The dataset is captured here, so switching tabs mid-flight cannot change
  // what this submission is scored against.
  const dataset = selectedDataset;

  // feedback while waiting
  submitting = true;
  refreshSubmitState();
  resultSection.classList.add("hidden");   // the only place the result is cleared
  setStatus(`Uploading and scoring against ${datasetLabels[dataset]}…`);

  // prepare payload
  const body = new FormData();
  body.append("file", file);
  body.append("dataset", dataset);

  // send file to scoring endpoint
  try {
    const resp = await fetch("/uploadfile/", { method: "POST", body });

    // the response could be JSON (from the app) or HTML (from a proxy error page
    // 413/502/504). read it as text and parse defensively
    const raw = await resp.text();
    let data = null;
    try { data = JSON.parse(raw); } catch (_) { /* not JSON, e.g. an nginx error page */ }

    if (!resp.ok) {
      if (resp.status === 401) {
        setStatus("401: Your session expired. Redirecting to login");
        window.location.href = "/login";
      } else if (resp.status === 413) {
        setStatus("413: the file is too large to upload");
      } else {
        const detail = (data && data.detail) || `${resp.status} ${resp.statusText}`;
        setStatus(`Error: ${detail}`);
      }
      return;
    }

    if (!data) {
      setStatus("Error: server returned an unexpected (non-JSON) response.");
      return;
    }

    renderResult(data);
    setStatus("");
    loadHistory();  // refresh history with the new submission
  } catch (err) {
    setStatus(`Network error: ${err.message}`);
  } finally {
    submitting = false;
    refreshSubmitState();
  }
});

// display results
function renderResult(data) {
  const label = data.dataset_label || data.dataset || "";
  // The result outlives tab switches, so it says up front which ground truth
  // produced it rather than relying on whichever tab happens to be active.
  resultHeading.textContent = label ? `Result — ${label}` : "Result";
  finalScoreValue.textContent = data.final_score.toFixed(4);
  componentsBody.innerHTML = "";
  for (const r of metricRows(data.components)) {
    const row = document.createElement("tr");
    [r.name, r.score.toFixed(4), r.weight.toFixed(3)].forEach((val) => {
      const td = document.createElement("td");
      td.textContent = val;
      row.appendChild(td);
    });
    componentsBody.appendChild(row);
  }
  resultMeta.textContent =
    `${data.filename} — ${data.num_beats} beat${data.num_beats === 1 ? "" : "s"} ` +
    `scored against ${label} ground truth`;
  resultSection.classList.remove("hidden");
}
