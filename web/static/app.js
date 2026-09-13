/* app.js — platform page wiring: tabs, backtest form, run list, lab form, batch list. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const fmt = window.reportFormat;
  let specs = [];
  let currentRun = null, currentId = null;
  let currentBatch = null, currentBatchId = null;
  let activeTab = "backtest";

  async function api(path, opts) {
    const r = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts || {}));
    if (r.status === 204) return null;
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail ? (typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)) : r.statusText);
    return body;
  }

  // ── tabs ────────────────────────────────────────────────────────────────
  function showTab(name) {
    activeTab = name;
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    $("tab-backtest").hidden = name !== "backtest";
    $("tab-lab").hidden = name !== "lab";
    const link = $("report-link");
    if (name === "backtest") { link.hidden = !currentId; if (currentId) link.href = "/runs/" + currentId + "/report.html"; }
    else { link.hidden = !currentBatchId; if (currentBatchId) link.href = "/batches/" + currentBatchId + "/report.html"; }
    try { localStorage.setItem("ps-tab", name); } catch (_) { /* ignore */ }
    rerender();
  }
  function rerender() {
    if (activeTab === "backtest" && currentRun) window.renderReport($("report"), currentRun);
    if (activeTab === "lab" && currentBatch) window.renderBatch($("batch-report"), currentBatch, { onSelect: loadAlgorithmIntoForm });
  }

  // ── strategies + params ─────────────────────────────────────────────────
  function renderParams(values) {
    const spec = specs.find((s) => s.name === $("strategy").value);
    $("strategy-desc").textContent = spec ? spec.description : "";
    const box = $("params");
    box.innerHTML = "";
    if (!spec || !spec.params.length) { box.hidden = true; return; }
    box.hidden = false;
    spec.params.forEach((p) => {
      const label = document.createElement("label");
      label.textContent = p.name + " (" + p.type + ")"; label.htmlFor = "param-" + p.name;
      const input = document.createElement("input");
      input.id = "param-" + p.name; input.dataset.param = p.name; input.dataset.type = p.type;
      if (p.type === "int" || p.type === "float") { input.type = "number"; input.step = p.type === "int" ? "1" : "any"; }
      const v = values && values[p.name] != null ? values[p.name] : p.default;
      if (v != null) input.value = v;
      box.appendChild(label); box.appendChild(input);
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
  function loadAlgorithmIntoForm(row) {
    if (!specs.find((s) => s.name === row.family)) return;
    $("strategy").value = row.family;
    renderParams(row.params || {});
    if (currentBatch && currentBatch.meta) {
      const m = currentBatch.meta;
      if (m.tickers) $("tickers").value = m.tickers.join(" ");
      if (m.start) $("start").value = fmt.date(m.start);
      if (m.end) $("end").value = fmt.date(m.end);
    }
    showTab("backtest");
    setStatus("Loaded " + row.name + " into the form" + (row.stop_loss || row.trailing_stop || row.take_profit ? " (stops are applied in the lab only)" : "") + ". Press Run backtest.");
  }

  // ── runs list ───────────────────────────────────────────────────────────
  function listItem(title, meta, value, valueSign, onOpen, onDelete, active) {
    const li = document.createElement("li");
    li.className = active ? "active" : "";
    const left = document.createElement("div");
    left.innerHTML = '<div class="name"></div><div class="meta"></div>';
    left.querySelector(".name").textContent = title;
    left.querySelector(".meta").textContent = meta;
    const right = document.createElement("div");
    right.innerHTML = '<div class="ret"></div><button class="ghost" title="Delete">✕</button>';
    right.querySelector(".ret").textContent = value;
    right.querySelector(".ret").style.color = valueSign > 0 ? "var(--good-text)" : valueSign < 0 ? "var(--critical)" : "";
    right.querySelector("button").addEventListener("click", async (e) => { e.stopPropagation(); await onDelete(); });
    li.appendChild(left); li.appendChild(right);
    li.addEventListener("click", onOpen);
    return li;
  }

  async function loadRuns() {
    const runs = await api("/api/runs");
    const ul = $("runs"); ul.innerHTML = "";
    if (!runs.length) { ul.appendChild(Object.assign(document.createElement("li"), { className: "empty", textContent: "No saved runs yet." })); return; }
    runs.forEach((r) => {
      const tr = r.metrics && r.metrics.total_return;
      ul.appendChild(listItem(
        r.strategy + " · " + (r.tickers || []).join(", "),
        fmt.date(r.start) + " → " + fmt.date(r.end) + (r.n_trades != null ? " · " + r.n_trades + " trades" : ""),
        fmt.pct(tr, 1), tr,
        () => openRun(r.run_id),
        async () => {
          if (!confirm("Delete run " + r.run_id + "?")) return;
          await api("/api/runs/" + r.run_id, { method: "DELETE" });
          if (currentId === r.run_id) { currentId = null; currentRun = null; $("report").innerHTML = ""; $("report-link").hidden = true; }
          loadRuns();
        }, r.run_id === currentId));
    });
  }
  async function openRun(runId) {
    setStatus("Loading " + runId + " …");
    try { currentRun = await api("/api/runs/" + runId); currentId = runId; showRun(); loadRuns(); setStatus(""); }
    catch (err) { showError(err.message); }
  }
  function showRun() {
    if (!currentRun) return;
    window.renderReport($("report"), currentRun);
    $("report-link").href = "/runs/" + currentId + "/report.html"; $("report-link").hidden = false;
    history.replaceState(null, "", "#run=" + currentId);
  }

  // ── batches list ────────────────────────────────────────────────────────
  async function loadBatches() {
    const batches = await api("/api/batches");
    const ul = $("batches"); ul.innerHTML = "";
    if (!batches.length) { ul.appendChild(Object.assign(document.createElement("li"), { className: "empty", textContent: "No saved batches yet." })); return; }
    batches.forEach((b) => {
      const s = b.summary || {};
      ul.appendChild(listItem(
        (b.n_algorithms || s.n_algorithms || "?") + " algos · " + (b.tickers || []).slice(0, 4).join(", ") + ((b.tickers || []).length > 4 ? " +" + (b.tickers.length - 4) : ""),
        fmt.date(b.start) + " → " + fmt.date(b.end) + " · PBO " + fmt.pct(s.pbo, 0) + " · RC p " + fmt.num(s.reality_check_p, 3),
        (s.n_strong || 0) + " strong", s.n_strong > 0 ? 1 : 0,
        () => openBatch(b.batch_id),
        async () => {
          if (!confirm("Delete batch " + b.batch_id + "?")) return;
          await api("/api/batches/" + b.batch_id, { method: "DELETE" });
          if (currentBatchId === b.batch_id) { currentBatchId = null; currentBatch = null; $("batch-report").innerHTML = ""; }
          loadBatches();
        }, b.batch_id === currentBatchId));
    });
  }
  async function openBatch(batchId) {
    setBatchStatus("Loading " + batchId + " …");
    try { currentBatch = await api("/api/batches/" + batchId); currentBatchId = batchId; showBatch(); loadBatches(); setBatchStatus(""); }
    catch (err) { showBatchError(err.message); }
  }
  function showBatch() {
    if (!currentBatch) return;
    window.renderBatch($("batch-report"), currentBatch, { onSelect: loadAlgorithmIntoForm });
    $("report-link").href = "/batches/" + currentBatchId + "/report.html"; $("report-link").hidden = false;
    history.replaceState(null, "", "#batch=" + currentBatchId);
  }

  // ── forms ───────────────────────────────────────────────────────────────
  function setStatus(msg) { $("status").textContent = msg; }
  function showError(msg) { $("error").textContent = msg; setStatus(""); }
  function setBatchStatus(msg) { $("batch-status").textContent = msg; }
  function showBatchError(msg) { $("batch-error").textContent = msg; setBatchStatus(""); }
  const num = (f, id) => (f[id].value === "" ? null : parseFloat(f[id].value));
  const tickers = (s) => s.split(/[\s,]+/).filter(Boolean).map((t) => t.toUpperCase());

  async function submitRun(e) {
    e.preventDefault();
    $("error").textContent = "";
    const f = e.target;
    const body = {
      strategy: f.strategy.value, params: collectParams(), tickers: tickers(f.tickers.value),
      start: f.start.value, end: f.end.value, benchmark: f.benchmark.value.trim() || null, data_source: f.data_source.value,
      initial_capital: num(f, "initial_capital"), commission: num(f, "commission"), slippage_bps: num(f, "slippage_bps"),
      execution_lag: parseInt(f.execution_lag.value || "1", 10), max_weight: num(f, "max_weight"),
      risk_free_rate: num(f, "risk_free_rate") || 0, n_samples: parseInt(f.n_samples.value || "1000", 10),
      rebalance: f.rebalance.checked, significance: f.significance.checked,
    };
    const btn = $("run-btn"); btn.disabled = true;
    setStatus("Running backtest — fetching data, simulating, bootstrapping …");
    const t0 = performance.now();
    try {
      currentRun = await api("/api/backtest", { method: "POST", body: JSON.stringify(body) });
      currentId = currentRun.meta.run_id; showRun();
      setStatus("Done in " + ((performance.now() - t0) / 1000).toFixed(1) + "s · saved as " + currentId);
      loadRuns();
    } catch (err) { showError(err.message); } finally { btn.disabled = false; }
  }

  async function submitBatch(e) {
    e.preventDefault();
    $("batch-error").textContent = "";
    const f = e.target;
    const fams = Array.from($("b_families").selectedOptions).map((o) => o.value).filter(Boolean);
    const universe = f.universe.value || null;
    const body = {
      tickers: universe ? [] : tickers(f.tickers.value), universe, start: f.start.value, end: f.end.value,
      sizing: f.sizing.value, rebalance_band: num(f, "rebalance_band") || 0, prior_trials: parseInt(f.prior_trials.value || "0", 10),
      families: fams.length ? fams : null, limit: f.limit.value ? parseInt(f.limit.value, 10) : null,
      n_jobs: parseInt(f.n_jobs.value || "0", 10), is_fraction: num(f, "is_fraction") || 0.6,
      n_boot: parseInt(f.n_boot.value || "1000", 10), pbo_blocks: parseInt(f.pbo_blocks.value || "16", 10),
      min_trades: parseInt(f.min_trades.value || "20", 10), commission: num(f, "commission"),
      slippage_bps: num(f, "slippage_bps"), execution_lag: parseInt(f.execution_lag.value || "1", 10),
      data_source: f.data_source.value,
    };
    const btn = $("batch-btn"); btn.disabled = true;
    setBatchStatus("Running batch — this backtests every algorithm and bootstraps the null; expect a minute or two …");
    const t0 = performance.now();
    try {
      currentBatch = await api("/api/batch", { method: "POST", body: JSON.stringify(body) });
      currentBatchId = currentBatch.meta.batch_id; showBatch();
      setBatchStatus("Done in " + ((performance.now() - t0) / 1000).toFixed(1) + "s · saved as " + currentBatchId);
      loadBatches();
    } catch (err) { showBatchError(err.message); } finally { btn.disabled = false; }
  }

  // ── theme ───────────────────────────────────────────────────────────────
  function toggleTheme() {
    const root = document.documentElement;
    const dark = root.getAttribute("data-theme") === "dark" ||
      (!root.getAttribute("data-theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
    root.setAttribute("data-theme", dark ? "light" : "dark");
    try { localStorage.setItem("ps-theme", dark ? "light" : "dark"); } catch (_) { /* ignore */ }
    rerender();
  }

  // ── init ────────────────────────────────────────────────────────────────
  async function init() {
    try { const saved = localStorage.getItem("ps-theme"); if (saved) document.documentElement.setAttribute("data-theme", saved); } catch (_) { /* ignore */ }
    $("theme-toggle").addEventListener("click", toggleTheme);
    $("run-form").addEventListener("submit", submitRun);
    $("batch-form").addEventListener("submit", submitBatch);
    $("refresh-runs").addEventListener("click", loadRuns);
    $("refresh-batches").addEventListener("click", loadBatches);
    $("strategy").addEventListener("change", () => renderParams());
    document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
    try {
      specs = await api("/api/strategies");
      const sel = $("strategy");
      specs.forEach((s) => sel.appendChild(Object.assign(document.createElement("option"), { value: s.name, textContent: s.name })));
      renderParams();
      const lib = await api("/api/algorithms");
      Object.entries(lib.universes || {}).forEach(([k, u]) => $("b_universe").appendChild(Object.assign(document.createElement("option"), { value: k, textContent: k + " — " + u.description })));
      async function refreshFamilies() {
        const uni = $("b_universe").value;
        const l = uni ? await api("/api/algorithms?universe=" + encodeURIComponent(uni)) : lib;
        $("algo-count").textContent = "— " + l.count + " algorithms";
        $("b_families").innerHTML = "";
        l.families.forEach((f) => $("b_families").appendChild(Object.assign(document.createElement("option"), { value: f, textContent: f })));
        if (uni && l.universes && l.universes[uni]) { $("b_tickers").value = l.universes[uni].tickers.join(" "); $("b_start").value = l.universes[uni].default_start; }
        $("b_tickers").disabled = !!uni;
      }
      $("b_universe").addEventListener("change", refreshFamilies);
      await refreshFamilies();
      await Promise.all([loadRuns(), loadBatches()]);
      const hash = location.hash.slice(1);
      let tab = "backtest";
      try { tab = localStorage.getItem("ps-tab") || tab; } catch (_) { /* ignore */ }
      if (hash.startsWith("run=")) { tab = "backtest"; openRun(hash.slice(4)); }
      else if (hash.startsWith("batch=")) { tab = "lab"; openBatch(hash.slice(6)); }
      showTab(tab);
    } catch (err) { showError(err.message); }
  }
  document.addEventListener("DOMContentLoaded", init);
})();
