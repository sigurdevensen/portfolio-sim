/* batch.js — renders an algorithm-lab batch (see research/report.py) with Plotly.
 * Public API: window.renderBatch(containerElement, batchDict, { onSelect(row) })
 */
(function () {
  "use strict";

  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function theme() {
    return {
      surface: cssVar("--surface"), text: cssVar("--text"), text2: cssVar("--text-2"), muted: cssVar("--muted"),
      grid: cssVar("--grid"), axis: cssVar("--axis"),
      s1: cssVar("--series-1"), s2: cssVar("--series-2"), s3: cssVar("--series-3"), s4: cssVar("--series-4"),
      s5: cssVar("--series-5") || "#e87ba4", s6: cssVar("--series-6") || "#008300", s7: cssVar("--series-7"), s8: cssVar("--series-8"),
      good: cssVar("--good"), warning: cssVar("--warning"), critical: cssVar("--critical"),
    };
  }
  function baseLayout(t, extra) {
    return Object.assign({
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: t.surface,
      font: { family: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: t.text2, size: 12 },
      margin: { l: 56, r: 16, t: 28, b: 44 }, hovermode: "closest",
      hoverlabel: { bgcolor: t.surface, bordercolor: t.axis, font: { color: t.text } },
      legend: { orientation: "h", y: 1.12, x: 0, font: { color: t.text2 } },
      xaxis: { gridcolor: t.grid, zerolinecolor: t.axis, linecolor: t.axis, tickfont: { color: t.muted } },
      yaxis: { gridcolor: t.grid, zerolinecolor: t.axis, linecolor: t.axis, tickfont: { color: t.muted } },
    }, extra || {});
  }
  const CFG = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };
  const fmt = window.reportFormat || {
    pct: (v, d = 2) => (v == null || !isFinite(v)) ? "–" : (v * 100).toFixed(d) + "%",
    num: (v, d = 2) => (v == null || !isFinite(v)) ? "–" : Number(v).toFixed(d),
    int: (v) => (v == null) ? "–" : String(Math.round(v)),
    date: (s) => (s ? String(s).slice(0, 10) : "–"),
  };
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v; else if (k === "text") node.textContent = v; else node.setAttribute(k, v);
    }
    (children || []).forEach((c) => c && node.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
    return node;
  }
  function card(title, note, cls) {
    const c = el("div", { class: "card" + (cls ? " " + cls : "") });
    if (title) c.appendChild(el("h2", { text: title }));
    if (note) c.appendChild(el("p", { class: "chart-note", text: note }));
    return c;
  }
  function chartDiv() { return el("div", { class: "chart" }); }
  function histTrace(hist, color, name, t) {
    if (!hist || !hist.edges || hist.edges.length < 2) return null;
    const centers = hist.edges.slice(0, -1).map((e, i) => (e + hist.edges[i + 1]) / 2);
    const widths = hist.edges.slice(0, -1).map((e, i) => hist.edges[i + 1] - e);
    return { type: "bar", x: centers, y: hist.counts, width: widths, name, marker: { color, line: { width: 1, color: t.surface } }, hovertemplate: name + "<br>%{x:.2f}: %{y}<extra></extra>" };
  }
  function vline(x, color, width) { return { type: "line", x0: x, x1: x, y0: 0, y1: 1, yref: "paper", line: { color, width: width || 2 } }; }
  function label(x, text, color) { return { x, y: 1, yref: "paper", yanchor: "bottom", text, showarrow: false, font: { color, size: 11 } }; }
  const EDGE_ORDER = { strong: 0, candidate: 1, none: 2 };

  // ── sections ─────────────────────────────────────────────────────────────
  function renderHeader(data) {
    const m = data.meta || {}, cfg = m.config || {};
    const head = el("div", { class: "report-head" });
    head.appendChild(el("div", { class: "title", text: "Algorithm lab — " + (m.n_algorithms || "?") + " algorithms" }));
    const chips = el("div", { class: "chips" });
    const items = [(m.tickers || []).join(", "), fmt.date(m.start) + " → " + fmt.date(m.end), (m.n_days || 0) + " days"];
    if (cfg.commission != null) items.push("commission " + fmt.pct(cfg.commission, 2));
    if (cfg.slippage_bps != null) items.push("slippage " + cfg.slippage_bps + " bps");
    if (cfg.execution_lag != null) items.push("lag " + cfg.execution_lag);
    if (cfg.is_fraction != null) items.push("IS " + Math.round(cfg.is_fraction * 100) + "% / OOS " + Math.round((1 - cfg.is_fraction) * 100) + "%");
    if (cfg.n_boot) items.push(cfg.n_boot + " bootstraps");
    if (m.synthetic) items.push("synthetic OHLC");
    items.forEach((s) => chips.appendChild(el("span", { class: "chip", text: s })));
    head.appendChild(chips);
    return head;
  }

  function renderVerdict(data) {
    const s = data.summary || {};
    const luck = s.best_is_consistent_with_luck;
    const cls = s.n_strong > 0 && !luck ? "strong" : (s.n_candidate > 0 || !luck ? "weak" : "none");
    const parts = [];
    const vs = s.has_benchmark ? "in excess of equal-weight buy-and-hold (Sharpe " + fmt.num(s.benchmark_sharpe) + ")" : "versus cash";
    parts.push("Tested " + s.n_algorithms + " algorithms " + vs + ". Under the null of no skill, the best of " + s.n_algorithms +
      " is expected to reach an excess Sharpe of about " + fmt.num(s.expected_max_sharpe) + "; the observed best is " + fmt.num(s.observed_max_sharpe) + ".");
    parts.push("White's Reality Check p = " + fmt.num(s.reality_check_p, 4) + " for the best algorithm (" + s.reality_check_best + ").");
    parts.push("Probability of Backtest Overfitting = " + fmt.pct(s.pbo, 0) + " across " + s.pbo_combinations + " in/out-of-sample splits.");
    parts.push(luck
      ? "Verdict: the best result is consistent with luck after accounting for the number of trials."
      : "Verdict: the best result is not explained by selection alone. " + s.n_strong + " algorithm(s) pass every gate.");
    if (s.n_random_controls_strong > 0) parts.push("WARNING: " + s.n_random_controls_strong + " random control(s) were flagged strong — treat every result with suspicion.");
    return el("div", { class: "verdict " + cls, text: parts.join(" ") });
  }

  function renderTiles(data) {
    const s = data.summary || {};
    const wrap = el("div", { class: "tiles" });
    const tile = (l, v, cls, sub) => {
      const t = el("div", { class: "tile" });
      t.appendChild(el("div", { class: "label", text: l }));
      t.appendChild(el("div", { class: "value" + (cls ? " " + cls : ""), text: v }));
      if (sub) t.appendChild(el("div", { class: "sub", text: sub }));
      return t;
    };
    wrap.appendChild(tile("Algorithms tested", fmt.int(s.n_algorithms), "", s.n_failed ? s.n_failed + " failed" : "all completed"));
    wrap.appendChild(tile("Benchmark Sharpe", fmt.num(s.benchmark_sharpe), "", s.has_benchmark ? "equal-weight buy & hold" : "none (vs cash)"));
    wrap.appendChild(tile("E[max excess Sharpe] under H0", fmt.num(s.expected_max_sharpe), "", "observed max " + fmt.num(s.observed_max_sharpe)));
    wrap.appendChild(tile("Reality Check p", fmt.num(s.reality_check_p, 4), s.reality_check_p < 0.05 ? "up" : "down", "best: " + s.reality_check_best));
    wrap.appendChild(tile("PBO", fmt.pct(s.pbo, 0), s.pbo > 0.5 ? "down" : (s.pbo < 0.2 ? "up" : ""), "prob. IS winner is below median OOS"));
    wrap.appendChild(tile("Strong edges", fmt.int(s.n_strong), s.n_strong > 0 ? "up" : "", s.n_candidate + " candidates · " + s.n_fdr_5pct + " pass FDR 5%"));
    wrap.appendChild(tile("IS→OOS rank corr.", fmt.num(s.is_oos_rank_corr), "", "Spearman across algorithms"));
    wrap.appendChild(tile("Best IS excess Sharpe", fmt.num(s.best_is_sharpe_is), "", s.best_is_name + " → OOS " + fmt.num(s.best_is_oos_sharpe)));
    wrap.appendChild(tile("Random controls flagged", fmt.int(s.n_random_controls_strong), s.n_random_controls_strong > 0 ? "down" : "up", "should be 0"));
    return wrap;
  }

  function renderScatter(data) {
    const t = theme();
    const rows = data.leaderboard || [];
    const c = card("In-sample vs out-of-sample excess Sharpe", "Sharpe of returns in excess of the buy-and-hold benchmark. Points below the diagonal degraded out of sample; anything left of zero never beat the benchmark. Random controls are crosses.");
    const div = chartDiv(); c.appendChild(div);
    const groups = { strong: { color: t.good, name: "Strong edge" }, candidate: { color: t.warning, name: "Candidate" }, none: { color: t.muted, name: "No edge" } };
    const traces = Object.entries(groups).map(([key, g]) => {
      const pts = rows.filter((r) => r.edge === key);
      return {
        type: "scatter", mode: "markers", name: g.name,
        x: pts.map((r) => r.excess_sharpe_is != null ? r.excess_sharpe_is : r.sharpe_is), y: pts.map((r) => r.excess_sharpe_oos != null ? r.excess_sharpe_oos : r.sharpe_oos),
        text: pts.map((r) => r.name + " (" + r.family + ")"),
        marker: { size: 9, color: g.color, symbol: pts.map((r) => (r.family === "random" ? "x" : "circle")), line: { width: 1.5, color: t.surface } },
        hovertemplate: "%{text}<br>IS %{x:.2f} · OOS %{y:.2f}<extra></extra>",
      };
    });
    const all = rows.flatMap((r) => [r.excess_sharpe_is != null ? r.excess_sharpe_is : r.sharpe_is, r.excess_sharpe_oos != null ? r.excess_sharpe_oos : r.sharpe_oos]).filter((v) => v != null && isFinite(v));
    const lo = Math.min(-0.5, ...all), hi = Math.max(0.5, ...all);
    Plotly.newPlot(div, traces, baseLayout(t, {
      shapes: [{ type: "line", x0: lo, y0: lo, x1: hi, y1: hi, line: { color: t.axis, width: 1, dash: "dot" } }],
      xaxis: Object.assign({}, baseLayout(t).xaxis, { title: { text: "In-sample excess Sharpe" }, zeroline: true }),
      yaxis: Object.assign({}, baseLayout(t).yaxis, { title: { text: "Out-of-sample excess Sharpe" }, zeroline: true }),
    }), CFG);
    return c;
  }

  function renderSharpeHist(data) {
    const t = theme(), s = data.summary || {};
    const c = card("Distribution of excess Sharpe across algorithms", "Full-sample Sharpe of returns in excess of the benchmark. The red line is the excess Sharpe the best of N skill-less strategies would be expected to reach.");
    const div = chartDiv(); c.appendChild(div);
    const tr = histTrace(data.excess_sharpe_hist || data.sharpe_hist, t.s1, "Algorithms", t);
    Plotly.newPlot(div, tr ? [tr] : [], baseLayout(t, {
      bargap: 0, showlegend: false,
      shapes: [vline(s.expected_max_sharpe, t.s8, 2), vline(s.observed_max_sharpe, t.text, 2)],
      annotations: [label(s.expected_max_sharpe, "E[max] " + fmt.num(s.expected_max_sharpe), t.s8), label(s.observed_max_sharpe, "observed max", t.text)],
      xaxis: Object.assign({}, baseLayout(t).xaxis, { title: { text: "Annualised excess Sharpe" } }),
      yaxis: Object.assign({}, baseLayout(t).yaxis, { title: { text: "Algorithms" } }),
    }), CFG);
    return c;
  }

  function renderRealityCheck(data) {
    const t = theme(), s = data.summary || {};
    const c = card("Reality Check null distribution", "Bootstrap distribution of the best strategy's statistic when no strategy has skill (√T × mean excess return). The line is the observed best.");
    const div = chartDiv(); c.appendChild(div);
    const tr = histTrace(data.reality_check_hist, t.s2, "Null max statistic", t);
    const obs = data.reality_check_observed;
    Plotly.newPlot(div, tr ? [tr] : [], baseLayout(t, {
      bargap: 0, showlegend: false,
      shapes: obs != null ? [vline(obs, t.text, 2)] : [],
      annotations: obs != null ? [label(obs, "observed (p = " + fmt.num(s.reality_check_p, 4) + ")", t.text)] : [],
      xaxis: Object.assign({}, baseLayout(t).xaxis, { title: { text: "max √T · mean return" } }),
      yaxis: Object.assign({}, baseLayout(t).yaxis, { title: { text: "Bootstrap samples" } }),
    }), CFG);
    return c;
  }

  function renderPBO(data) {
    const t = theme(), s = data.summary || {};
    const c = card("Probability of backtest overfitting (CSCV)", "For every split, the in-sample winner's out-of-sample rank as a logit. Mass at or below zero means the IS winner was below median OOS.");
    const div = chartDiv(); c.appendChild(div);
    const tr = histTrace(data.pbo_logit_hist, t.s7, "Splits", t);
    Plotly.newPlot(div, tr ? [tr] : [], baseLayout(t, {
      bargap: 0, showlegend: false,
      shapes: [vline(0, t.s8, 2)],
      annotations: [label(0, "PBO = " + fmt.pct(s.pbo, 0), t.s8)],
      xaxis: Object.assign({}, baseLayout(t).xaxis, { title: { text: "OOS rank logit of IS winner" } }),
      yaxis: Object.assign({}, baseLayout(t).yaxis, { title: { text: "Splits" } }),
    }), CFG);
    return c;
  }

  function renderNavs(data) {
    const t = theme();
    const names = Object.keys(data.navs || {}).slice(0, 8);
    if (!names.length) return null;
    const palette = [t.s1, t.s2, t.s3, t.s4, t.s5, t.s6, t.s7, t.s8];
    const c = card("Equity curves of the top in-sample algorithms", "Indexed to 100. The vertical line marks the in-sample / out-of-sample boundary.");
    const div = chartDiv(); c.appendChild(div);
    const split = data.dates[Math.min(data.dates.length - 1, (data.summary || {}).is_days || 0)];
    const traces = names.map((n, i) => ({ type: "scatter", mode: "lines", name: n, x: data.dates, y: data.navs[n], line: { width: 1.6, color: palette[i % palette.length] }, hovertemplate: n + " %{y:.1f}<extra></extra>" }));
    if (data.benchmark_nav) traces.push({ type: "scatter", mode: "lines", name: "Buy & hold (benchmark)", x: data.dates, y: data.benchmark_nav, line: { width: 2, color: t.muted, dash: "dot" }, hovertemplate: "benchmark %{y:.1f}<extra></extra>" });
    Plotly.newPlot(div, traces, baseLayout(t, {
      hovermode: "x unified", legend: { orientation: "h", y: -0.2, x: 0, font: { color: t.text2, size: 10 } }, margin: { l: 56, r: 16, t: 20, b: 90 },
      shapes: split ? [{ type: "line", x0: split, x1: split, y0: 0, y1: 1, yref: "paper", line: { color: t.axis, width: 1.5, dash: "dash" } }] : [],
      annotations: split ? [{ x: split, y: 1, yref: "paper", yanchor: "bottom", text: "OOS →", showarrow: false, font: { color: t.muted, size: 11 } }] : [],
      yaxis: Object.assign({}, baseLayout(t).yaxis, { title: { text: "Indexed NAV" } }),
    }), CFG);
    return c;
  }

  function renderLeaderboard(data, opts) {
    const rows = (data.leaderboard || []).slice();
    const c = card("Leaderboard", "Excess = Sharpe of returns over the buy-and-hold benchmark; every p-value, DSR and stability figure is computed on those excess returns. p FDR is the Benjamini–Hochberg adjusted one-sided p-value; DSR is the Deflated Sharpe Ratio. Click a column to sort, a row to load the algorithm into the backtest form.");
    const controls = el("div", { class: "row", style: "margin-bottom:8px;max-width:520px" });
    const famSel = el("select");
    famSel.appendChild(el("option", { value: "", text: "All families" }));
    (data.families || []).forEach((f) => famSel.appendChild(el("option", { value: f, text: f })));
    const edgeSel = el("select");
    [["", "All verdicts"], ["strong", "Strong"], ["candidate", "Candidate"], ["none", "No edge"]].forEach(([v, l]) => edgeSel.appendChild(el("option", { value: v, text: l })));
    controls.appendChild(famSel); controls.appendChild(edgeSel);
    c.appendChild(controls);

    const cols = [
      { key: "name", label: "Algorithm" },
      { key: "family", label: "Family" },
      { key: "data_type", label: "Data" },
      { key: "stops", label: "Stops", get: (r) => [r.stop_loss != null ? "SL " + fmt.pct(r.stop_loss, 0) : "", r.trailing_stop != null ? "TS " + fmt.pct(r.trailing_stop, 0) : "", r.take_profit != null ? "TP " + fmt.pct(r.take_profit, 0) : ""].filter(Boolean).join(" ") || "–" },
      { key: "excess_sharpe_is", label: "Excess IS", num: true, fmt: (v) => fmt.num(v), signed: true },
      { key: "excess_sharpe_oos", label: "Excess OOS", num: true, fmt: (v) => fmt.num(v), signed: true },
      { key: "sharpe_full", label: "Sharpe", num: true, fmt: (v) => fmt.num(v) },
      { key: "sharpe_oos", label: "Sharpe OOS", num: true, fmt: (v) => fmt.num(v) },
      { key: "cagr_full", label: "CAGR", num: true, fmt: (v) => fmt.pct(v, 1), signed: true },
      { key: "max_drawdown_full", label: "Max DD", num: true, fmt: (v) => fmt.pct(v, 1) },
      { key: "n_trades", label: "Trades", num: true, fmt: (v) => fmt.int(v) },
      { key: "p_value", label: "p", num: true, fmt: (v) => fmt.num(v, 3) },
      { key: "p_fdr", label: "p FDR", num: true, fmt: (v) => fmt.num(v, 3) },
      { key: "dsr", label: "DSR", num: true, fmt: (v) => fmt.pct(v, 0) },
      { key: "stability", label: "Stability", num: true, fmt: (v) => fmt.pct(v, 0) },
      { key: "edge", label: "Edge" },
    ];
    let sortKey = "excess_sharpe_is", sortDir = -1;
    const wrap = el("div", { class: "table-wrap" });
    const tbl = el("table"); const thead = el("thead"); const trh = el("tr");
    cols.forEach((col) => {
      const th = el("th", { class: col.num ? "num" : "", text: col.label, style: "cursor:pointer" });
      th.addEventListener("click", () => { if (sortKey === col.key) sortDir = -sortDir; else { sortKey = col.key; sortDir = col.num ? -1 : 1; } draw(); });
      trh.appendChild(th);
    });
    thead.appendChild(trh); tbl.appendChild(thead);
    const tbody = el("tbody"); tbl.appendChild(tbody); wrap.appendChild(tbl); c.appendChild(wrap);

    function draw() {
      const fam = famSel.value, edge = edgeSel.value;
      const view = rows.filter((r) => (!fam || r.family === fam) && (!edge || r.edge === edge));
      view.sort((a, b) => {
        let va = a[sortKey], vb = b[sortKey];
        if (sortKey === "edge") { va = EDGE_ORDER[va]; vb = EDGE_ORDER[vb]; }
        if (va == null) return 1; if (vb == null) return -1;
        return (va < vb ? -1 : va > vb ? 1 : 0) * sortDir;
      });
      tbody.innerHTML = "";
      view.forEach((r) => {
        const tr = el("tr", { style: opts && opts.onSelect ? "cursor:pointer" : "" });
        cols.forEach((col) => {
          const raw = col.get ? col.get(r) : r[col.key];
          const text = col.fmt ? col.fmt(raw) : (raw == null ? "–" : String(raw));
          const cls = [col.num ? "num" : "", col.signed ? (raw > 0 ? "pos" : raw < 0 ? "neg" : "") : "", col.key === "edge" ? "edge-" + raw : ""].join(" ").trim();
          tr.appendChild(el("td", { class: cls, text }));
        });
        if (opts && opts.onSelect) tr.addEventListener("click", () => opts.onSelect(r));
        tbody.appendChild(tr);
      });
      if (!view.length) tbody.appendChild(el("tr", {}, [el("td", { class: "muted", text: "No algorithms match.", colspan: String(cols.length) })]));
    }
    famSel.addEventListener("change", draw); edgeSel.addEventListener("change", draw);
    draw();
    return c;
  }

  function renderErrors(data) {
    const errs = Object.entries(data.errors || {});
    if (!errs.length) return null;
    const c = card("Failed algorithms", null);
    const ul = el("ul");
    errs.forEach(([k, v]) => ul.appendChild(el("li", { text: k + ": " + v })));
    c.appendChild(ul);
    return c;
  }

  function renderBatch(container, data, opts) {
    container.innerHTML = "";
    if (!data || !data.summary) { container.appendChild(el("p", { class: "error", text: "Batch has no summary." })); return; }
    const sections = [renderHeader(data), renderVerdict(data), el("div", { style: "height:12px" }), renderTiles(data), el("div", { style: "height:12px" })];
    const g1 = el("div", { class: "grid-2 section" }); [renderScatter(data), renderSharpeHist(data)].forEach((x) => x && g1.appendChild(x)); sections.push(g1);
    const g2 = el("div", { class: "grid-2 section" }); [renderRealityCheck(data), renderPBO(data)].forEach((x) => x && g2.appendChild(x)); sections.push(g2);
    sections.push(renderNavs(data));
    sections.push(renderLeaderboard(data, opts));
    sections.push(renderErrors(data));
    sections.forEach((s) => s && container.appendChild(s));
    container.querySelectorAll(".js-plotly-plot").forEach((p) => Plotly.Plots.resize(p));
  }

  window.renderBatch = renderBatch;
})();
