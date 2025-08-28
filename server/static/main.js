// const server = "http://localhost:8000";
const server = `${window.location.protocol}//${window.location.hostname}:${window.location.port}`;
const expSelect = document.getElementById("expSelect");
const expConfig = document.getElementById("expConfig");
const output = document.getElementById("output");
const btnBuild    = document.getElementById("btnBuild");
const btnRun      = document.getElementById("btnRun");
const btnRemove   = document.getElementById("btnRemove");
const btnLogs     = document.getElementById("btnLogs");
const btnDownload = document.getElementById("btnDownload");

function clearOutput() {
  output.textContent = "";
}

function log(msg, ok = false) {
  const d = document.createElement("div");
  if (ok) d.classList.add("status-ok");
  d.textContent = msg;
  output.appendChild(d);
  output.scrollTop = output.scrollHeight;
}

async function api(path, opts = {}) {
  const res = await fetch(server + path, {
    headers: {"Content-Type":"application/json"},
    ...opts
  });
  return opts.method === "GET" ? res.json() : res.text();
}

async function load() {
  const { experiments } = await api("/experiments", { method: "GET" });
  experiments.forEach(c => expSelect.add(new Option(c.name, c.name)));

  expSelect.onchange = () => showConfig(experiments);
  showConfig(experiments);
}

function showConfig(experiments) {
  expConfig.innerHTML = "";
  const cfg = experiments.find(c => c.name === expSelect.value);
  Object.entries(cfg).forEach(([k, v]) => {
    const p = document.createElement("p");
    p.innerHTML = `<span class="key">${k}:</span>${
      (typeof v === "string" && v.startsWith("http"))
        ? `<a href="${v}" target="_blank">${v}</a>`
        : v
    }`;
    expConfig.appendChild(p);
  });
}

async function build() {
  clearOutput();
  log(`POST /build`, true); // consistent green log with other actions

  const reader = (await fetch(`${server}/build`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({experiment_name: expSelect.value})
  })).body.getReader();
  const dec = new TextDecoder();

  let doneReading = false;
  while (!doneReading) {
    const {done, value} = await reader.read();
    doneReading = done;
    if (value) log(dec.decode(value)); // log streaming output
  }

  log("[build complete]", true); // green when finished
}

async function postAction(path) {
  clearOutput();
  log(`POST ${path}`, true); // green log for consistency
  const text = await api(path, {
    method: "POST",
    body: JSON.stringify({experiment_name: expSelect.value})
  });
  log(text, true);
}

btnBuild.onclick    = build;
btnRun.onclick      = () => postAction("/run");
btnRemove.onclick   = () => postAction("/remove");
btnLogs.onclick     = () => {
  clearOutput();
  const c = expSelect.value.replace(/_/g,"-") + "-container";
  window.open(`logs.html?ws=${encodeURIComponent(`ws://${location.hostname}:8000/ws/logs/container/${c}`)}`, "_blank");
};
btnDownload.onclick = () => {
  clearOutput();
  const url = `${server}/artifacts/${encodeURIComponent(expSelect.value)}`;
  // Open in new window/tab so errors (404) show there without navigating away
  window.open(url, "_blank");
};


load().catch(e => log(e.message));
