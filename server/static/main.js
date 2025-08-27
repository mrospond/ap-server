const experimentSelect = document.getElementById("experimentSelect");
const logsEl = document.getElementById("logs");
const statusEl = document.getElementById("status");
const actionsSection = document.getElementById("actionsSection");

// Load experiments
async function loadExperiments() {
    const res = await fetch("/experiments");
    const data = await res.json();
    experimentSelect.innerHTML = data.experiments.map(e => `<option value="${e}">${e}</option>`).join("");
}

// Start experiment
async function startExperiment() {
    const exp = experimentSelect.value;
    const res = await fetch("/run", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({experiment: exp})
    });
    const data = await res.json();
    statusEl.innerText = data.status;
    actionsSection.style.display = "block";
    logsEl.style.display = "block";
}

// Stop experiment
async function stopExperiment() {
    const res = await fetch("/stop", {method: "POST"});
    const data = await res.json();
    statusEl.innerText = data.status;
}

// Fetch logs
async function fetchLogs() {
    const res = await fetch("/logs");
    const data = await res.json();
    logsEl.innerText = data.logs;
    logsEl.scrollTop = logsEl.scrollHeight;
}

// Poll logs every 2s
setInterval(fetchLogs, 2000);

loadExperiments();
