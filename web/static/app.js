/* app.js — platform page wiring: strategy form, run list, report viewer. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const fmt = window.reportFormat;
  let specs = [];
  let currentRun = null;
  let currentId = null;

  async function api(path, opts) {
    const r = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts || {}));
    if (r.status === 204) return null;
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail ? (typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)) : r.statusText);
    return body;
  }

  // ── strategies + params ─────────────────────────────────────────────────
  function renderParams() {
    const spec = specs.find((s) => s.name === $("strategy").value);
    $("strategy-desc").textContent = spec ? spec.description : "";
    const box = $("params");
    box.innerHTML = "";
    if (!spec || !spec.params.length) { box.hidden = true; return; }
    box.hidden = false;
    spec.params.forEach((p) => {
      const label = document.createElement("label");
      label.textContent = p.name + " (" + p.type + ")";
      label.htmlFor = "param-" + p.name;
      const input = document.createElement("input");
      input.id = "param-" + p.name;
      input.dataset.param = p.name;
      input.dataset.type = p.type;
      if (p.type === "int" || p.type === "float") { input.type = "number"; input.step = p.type === "int" ? "1" : "any"; }
      if (p.default != null) input.value = p.default;
      box.appendChild(label);
      box.appendChild(input);
    });
  }
  function collectParams() {
    const out = {};
    $("params").querySelectorAll("input[data-param]").forEach((i) => {
      if (i.value === "") return;
      out[i.dataset.param] = i.dataset.type === "int" ? parseInt(i.value, 10) : i.dataset.type === "float" ? parseFloat(i.value) : i.value;
    });
    return out;
  }

  // ── runs list ───────────────────────────────────────────────────────────
  async function loadRuns() {
    const runs = await api("/api/runs");
    const ul = $("runs");
    ul.innerHTML = "";
    if (!runs.length) { ul.appendChild(Object.assign(document.createElement("li"), { className: "empty", textContent: "No saved runs yet." })); return; }
    runs.forEach((r) => {
      const li = document.createElement("li");
      li.className = r.run_id === currentId ? "active" : "";
      const left = document.createElement("div");
      left.innerHTML = '<div class="name"></div><div class="meta"></div>';
      left.querySelector(".name").textContent = r.strategy + " · " + (r.tickers || []).join(", ");
      left.querySelector(".meta").textContent = fmt.date(r.start) + " → " + fmt.date(r.end) + (r.n_trades != null ? " · " + r.n_trades + " trades" : "");
      const right = document.createElement("div");
      const tr = r.metrics && r.metrics.total_return;
      right.innerHTML = '<div class="ret"></div><button class="ghost" title="Delete run">✕</button>';
      right.querySelector(".ret").textContent = fmt.pct(tr, 1);
      right.querySelector(".ret").style.color = tr > 0 ? "var(--good-text)" : tr < 0 ? "var(--critical)" : "";
      right.querySelector("button").addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm("Delete run " + r.run_id + "?")) return;
        await api("/api/runs/" + r.run_id, { method: "DELETE" });
        if (currentId === r.run_id) { currentId = null; currentRun = null; $("report").innerHTML = ""; $("report-link").hidden = true; }
        loadRuns();
      });
      li.appendChild(left); li.appendChild(right);
      li.addEventListener("click", () => openRun(r.run_id));
      ul.appendChild(li);
    });
  }

  async function openRun(runId) {
    setStatus("Loading " + runId + " …");
    try {
      currentRun = await api("/api/runs/" + runId);
      currentId = runId;
      showRun();
      loadRuns();
      setStatus("");
    } catch (err) { showError(err.message); }
  }

  function showRun() {
    if (!currentRun) return;
    window.renderReport($("report"), currentRun);
    const link = $("report-link");
    link.href = "/runs/" + currentId + "/report.html";
    link.hidden = false;
    history.replaceState(null, "", "#" + currentId);
  }

  // ── form submit ─────────────────────────────────────────────────────────
  function setStatus(msg) { $("status").textContent = msg; }
  function showError(msg) { $("error").textContent = msg; setStatus(""); }

  async function submit(e) {
    e.preventDefault();
    $("error").textContent = "";
    const f = e.target;
    const num = (id) => (f[id].value === "" ? null : parseFloat(f[id].value));
    const body = {
      strategy: f.strategy.value,
      params: collectParams(),
      tickers: f.tickers.value.split(/[\s,]+/).filter(Boolean).map((t) => t.toUpperCase()),
      start: f.start.value, end: f.end.value,
      benchmark: f.benchmark.value.trim() || null,
      data_source: f.data_source.value,
      initial_capital: num("initial_capital"), commission: num("commission"), slippage_bps: num("slippage_bps"),
      execution_lag: parseInt(f.execution_lag.value || "1", 10), max_weight: num("max_weight"),
      risk_free_rate: num("risk_free_rate") || 0, n_samples: parseInt(f.n_samples.value || "1000", 10),
      rebalance: f.rebalance.checked, significance: f.significance.checked,
    };
    const btn = $("run-btn");
    btn.disabled = true;
    setStatus("Running backtest — fetching data, simulating, bootstrapping …");
    const t0 = performance.now();
    try {
      currentRun = await api("/api/backtest", { method: "POST", body: JSON.stringify(body) });
      currentId = currentRun.meta.run_id;
      showRun();
      setStatus("Done in " + ((performance.now() - t0) / 1000).toFixed(1) + "s · saved as " + currentId);
      loadRuns();
    } catch (err) {
      showError(err.message);
    } finally { btn.disabled = false; }
  }

  // ── theme ───────────────────────────────────────────────────────────────
  function toggleTheme() {
    const root = document.documentElement;
    const dark = root.getAttribute("data-theme") === "dark" ||
      (!root.getAttribute("data-theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
    root.setAttribute("data-theme", dark ? "light" : "dark");
    try { localStorage.setItem("ps-theme", dark ? "light" : "dark"); } catch (_) { /* ignore */ }
    showRun();
  }

  // ── init ────────────────────────────────────────────────────────────────
  async function init() {
    try { const saved = localStorage.getItem("ps-theme"); if (saved) document.documentElement.setAttribute("data-theme", saved); } catch (_) { /* ignore */ }
    $("theme-toggle").addEventListener("click", toggleTheme);
    $("run-form").addEventListener("submit", submit);
    $("refresh-runs").addEventListener("click", loadRuns);
    $("strategy").addEventListener("change", renderParams);
    try {
      specs = await api("/api/strategies");
      const sel = $("strategy");
      specs.forEach((s) => sel.appendChild(Object.assign(document.createElement("option"), { value: s.name, textContent: s.name })));
      renderParams();
      await loadRuns();
      const fromHash = location.hash.slice(1);
      if (fromHash) openRun(fromHash);
    } catch (err) { showError(err.message); }
  }
  document.addEventListener("DOMContentLoaded", init);
})();
