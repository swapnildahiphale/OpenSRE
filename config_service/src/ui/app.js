function qs(id) { return document.getElementById(id); }

const tokenInput = qs("token");
const loadBtn = qs("loadBtn");
const logoutBtn = qs("logoutBtn");
const statusEl = qs("status");
const effectivePre = qs("effectivePre");
const rawPre = qs("rawPre");
const overridesTa = qs("overridesTa");
const saveBtn = qs("saveBtn");
const resetBtn = qs("resetBtn");
const saveStatus = qs("saveStatus");
const teamLabel = qs("teamLabel");
const lineageLabel = qs("lineageLabel");
const reqLabel = qs("reqLabel");

let lastRaw = null;
let lastEffective = null;

function setStatus(text, kind) {
  statusEl.textContent = text;
  statusEl.className = "status" + (kind ? ` ${kind}` : "");
}

function setSaveStatus(text, kind) {
  saveStatus.textContent = text;
  saveStatus.className = "status" + (kind ? ` ${kind}` : "");
}

function getToken() {
  return tokenInput.value.trim();
}

function authHeaders() {
  return { "Authorization": `Bearer ${getToken()}` };
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

function updateLabels(raw, reqId) {
  const lineage = raw?.lineage || [];
  const teamNode = lineage.length ? lineage[lineage.length - 1] : null;
  const teamName = teamNode?.name || (raw?.configs?.[teamNode?.node_id || ""]?.team_name) || "—";
  teamLabel.textContent = `team: ${teamName}`;
  lineageLabel.textContent = `lineage: ${lineage.map(n => n.node_id).join(" → ") || "—"}`;
  reqLabel.textContent = `request: ${reqId || "—"}`;
}

async function fetchJson(url, opts = {}) {
  const resp = await fetch(url, opts);
  const reqId = resp.headers.get("x-request-id");
  const text = await resp.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* ignore */ }
  if (!resp.ok) {
    const detail = data?.detail || text || `HTTP ${resp.status}`;
    const err = new Error(detail);
    err.status = resp.status;
    err.requestId = reqId;
    throw err;
  }
  return { data, requestId: reqId };
}

async function loadAll() {
  setSaveStatus("");
  const token = getToken();
  if (!token) {
    setStatus("Paste a token first.", "err");
    return;
  }

  loadBtn.disabled = true;
  try {
    const rawRes = await fetchJson("/api/v1/config/me/raw", { headers: authHeaders() });
    const effRes = await fetchJson("/api/v1/config/me/effective", { headers: authHeaders() });

    lastRaw = rawRes.data;
    lastEffective = effRes.data;

    rawPre.textContent = pretty(lastRaw);
    effectivePre.textContent = pretty(lastEffective);

    // Fill overrides editor with current team node config (best-effort)
    const lineage = lastRaw.lineage || [];
    const teamNodeId = lineage.length ? lineage[lineage.length - 1].node_id : null;
    const teamCfg = (teamNodeId && lastRaw.configs && lastRaw.configs[teamNodeId]) ? lastRaw.configs[teamNodeId] : {};

    // Remove immutable field if present
    const editable = { ...teamCfg };
    delete editable.team_name;
    overridesTa.value = pretty(editable);

    updateLabels(lastRaw, effRes.requestId || rawRes.requestId);
    setStatus("Loaded.", "ok");
  } catch (e) {
    updateLabels(null, e.requestId);
    setStatus(`Load failed: ${e.message}`, "err");
  } finally {
    loadBtn.disabled = false;
  }
}

async function saveOverrides() {
  setSaveStatus("");
  const token = getToken();
  if (!token) {
    setSaveStatus("Paste a token first.", "err");
    return;
  }

  let payload = null;
  try {
    payload = JSON.parse(overridesTa.value || "{}");
  } catch (e) {
    setSaveStatus(`Invalid JSON: ${e.message}`, "err");
    return;
  }

  if (payload && typeof payload === "object" && "team_name" in payload) {
    setSaveStatus("Remove team_name (immutable).", "err");
    return;
  }

  saveBtn.disabled = true;
  try {
    const res = await fetchJson("/api/v1/config/me", {
      method: "PUT",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setSaveStatus("Saved. Reloading effective config…", "ok");
    await loadAll();
  } catch (e) {
    setSaveStatus(`Save failed: ${e.message}`, "err");
  } finally {
    saveBtn.disabled = false;
  }
}

function clearAll() {
  tokenInput.value = "";
  lastRaw = null;
  lastEffective = null;
  rawPre.textContent = "{}";
  effectivePre.textContent = "{}";
  overridesTa.value = "{}";
  updateLabels(null, null);
  setSaveStatus("");
  setStatus("Not connected.", "");
}

loadBtn.addEventListener("click", loadAll);
saveBtn.addEventListener("click", saveOverrides);
resetBtn.addEventListener("click", () => {
  if (lastRaw) {
    const lineage = lastRaw.lineage || [];
    const teamNodeId = lineage.length ? lineage[lineage.length - 1].node_id : null;
    const teamCfg = (teamNodeId && lastRaw.configs && lastRaw.configs[teamNodeId]) ? lastRaw.configs[teamNodeId] : {};
    const editable = { ...teamCfg };
    delete editable.team_name;
    overridesTa.value = pretty(editable);
    setSaveStatus("Reset to current DB overrides.", "ok");
  } else {
    overridesTa.value = "{}";
  }
});
logoutBtn.addEventListener("click", clearAll);


