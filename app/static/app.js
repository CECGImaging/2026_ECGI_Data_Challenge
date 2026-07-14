const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const submitBtn = document.getElementById("submit-btn");
const statusBox = document.getElementById("status");
const resultSection = document.getElementById("result");
const finalScoreValue = document.getElementById("final-score-value");
const componentsBody = document.querySelector("#components tbody");
const resultMeta = document.getElementById("result-meta");

const METRIC_NAMES = {
  SC: "Spatial correlation",
  TC: "Temporal correlation",
  RMSE: "RMSE (normalized)",
};


function setStatus(message) {
  statusBox.textContent = message;
  statusBox.classList.toggle("hidden", !message);
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

// Load and render the logged-in user's submission history (newest first).
async function loadHistory() {
  try {
    const resp = await fetch("/submissions");
    if (!resp.ok) return;
    const items = await resp.json();

    const tbody = document.querySelector("#history-table tbody");
    const table = document.getElementById("history-table");
    const empty = document.getElementById("history-empty");
    tbody.innerHTML = "";

    if (!items.length) {
      table.classList.add("hidden");
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");

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
      const row = document.createElement("tr");
      // textContent (not innerHTML) so a crafted filename can't inject markup
      [when, it.filename || "", it.num_beats ?? "", score].forEach((val) => {
        const td = document.createElement("td");
        td.textContent = val;
        row.appendChild(td);
      });
      tbody.appendChild(row);
    }
    table.classList.remove("hidden");
  } catch (_) { /* ignore */ }
}
loadHistory();

// handle uploaded file input
fileInput.addEventListener("change", () => {
  submitBtn.disabled = !fileInput.files[0];
  setStatus("");
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
  // feedback while waiting
  submitBtn.disabled = true;
  resultSection.classList.add("hidden");
  setStatus("Uploading and scoring…");
  
  // prepare payload
  const body = new FormData();
  body.append("file", file);

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
    submitBtn.disabled = false;
  }
});

// display results
function renderResult(data) {
  finalScoreValue.textContent = data.final_score.toFixed(4);
  componentsBody.innerHTML = "";
  for (const [code, info] of Object.entries(data.components)) {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${METRIC_NAMES[code] || code}</td>` +
      `<td>${info.score.toFixed(4)}</td>` +
      `<td>${info.weight.toFixed(3)}</td>`;
    componentsBody.appendChild(row);
  }
  resultMeta.textContent = `${data.filename} — ${data.num_beats} beat${data.num_beats === 1 ? "" : "s"} scored`;
  resultSection.classList.remove("hidden");
}
