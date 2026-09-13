/* report.js — renders a serialised backtest run (see evaluation/serialize.py)
 * into interactive Plotly charts and tables. Shared by the platform page and the
 * standalone report.html produced by HTMLReporter.
 *
 * Public API:  window.renderReport(containerElement, runDict)
 */
(function () {
  "use strict";

  // ── theme + palette ─────────────────────────────────────────────────────
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function theme() {
    return {
      surface: cssVar("--surface"),
      text: cssVar("--text"),
      text2: cssVar("--text-2"),
      muted: cssVar("--muted"),
      grid: cssVar("--grid"),
      axis: cssVar("--axis"),
      s1: cssVar("--series-1"),
      s2: cssVar("--series-2"),
      s3: cssVar("--series-3"),
      s7: cssVar("--series-7"),
      s8: cssVar("--series-8"),
      good: cssVar("--good"),
      critical: cssVar("--critical"),
      seq100: cssVar("--seq-100"),
      seq400: cssVar("--seq-400"),
      seq700: cssVar("--seq-700"),
      divMid: cssVar("--div-mid"),
    };
  }
  function baseLayout(t, extra) {
    return Object.assign({
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: t.surface,
      font: { family: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: t.text2, size: 12 },
      margin: { l: 56, r: 16, t: 28, b: 40 },
      hovermode: "x unified",
      hoverlabel: { bgcolor: t.surface, bordercolor: t.axis, font: { color: t.text } },
      legend: { orientation: "h", y: 1.12, x: 0, font: { color: t.text2 } },
      xaxis: { gridcolor: t.grid, zerolinecolor: t.axis, linecolor: t.axis, tickfont: { color: t.muted } },
      yaxis: { gridcolor: t.grid, zerolinecolor: t.axis, linecolor: t.axis, tickfont: { color: t.muted } },
    }, extra || {});
  }
  const PLOT_CONFIG = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };

  // ── formatting ──────────────────────────────────────────────────────────
  const fmt = {
    pct: (v, d = 2) => (v == null || !isFinite(v)) ? "–" : (v * 100).toFixed(d) + "%",
    num: (v, d = 2) => (v == null || !isFinite(v)) ? (v === Infinity ? "∞" : "–") : Number(v).toFixed(d),
    int: (v) => (v == null) ? "–" : String(Math.round(v)),
    money: (v) => (v == null || !isFinite(v)) ? "–" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 }),
    money2: (v) => (v == null || !isFinite(v)) ? "–" : Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    date: (s) => (s ? String(s).slice(0, 10) : "–"),
  };
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "html") node.innerHTML = v;
      else node.setAttribute(k, v);
    }
    (children || []).forEach((c) => c && node.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
    return node;
  }
  function card(title, note) {
    const c = el("div", { class: "card" });
    if (title) c.appendChild(el("h2", { text: title }));
    if (note) c.appendChild(el("p", { class: "chart-note", text: note }));
    return c;
  }
  function chartDiv(cls) { return el("div", { class: "chart" + (cls ? " " + cls : "") }); }

  // ── sections ────────────────────────────────────────────────────────────
  function renderHeader(data) {
    const m = data.meta || {};
    const head = el("div", { class: "report-head" });
    head.appendChild(el("div", { class: "title", text: (m.strategy || "strategy") + " backtest" }));
    const chips = el("div", { class: "chips" });
    const cfg = m.config || {};
    const items = [];
    if (m.tickers) items.push((Array.isArray(m.tickers) ? m.tickers : [m.tickers]).join(", "));
    items.push(fmt.date(m.start) + " → " + fmt.date(m.end));
    if (m.params && Object.keys(m.params).length) items.push(Object.entries(m.params).map(([k, v]) => k + "=" + v).join(", "));
    if (cfg.initial_capital != null) items.push("capital " + fmt.money(cfg.initial_capital));
    if (cfg.commission != null) items.push("commission " + fmt.pct(cfg.commission, 2));
    if (cfg.slippage_bps != null) items.push("slippage " + cfg.slippage_bps + " bps");
    if (cfg.execution_lag != null) items.push("lag " + cfg.execution_lag + " bar" + (cfg.execution_lag === 1 ? "" : "s"));
    if (m.benchmark) items.push("benchmark " + m.benchmark);
    if (m.data_source) items.push(m.data_source);
    items.forEach((s) => chips.appendChild(el("span", { class: "chip", text: s })));
    head.appendChild(chips);
    return head;
  }

  function renderTiles(data) {
    const m = data.metrics || {}, ts = data.trade_stats || {}, sig = data.significance;
    const nav = data.series.nav;
    const wrap = el("div", { class: "tiles" });
    const tile = (label, value, cls, sub) => {
      const t = el("div", { class: "tile" });
      t.appendChild(el("div", { class: "label", text: label }));
      t.appendChild(el("div", { class: "value" + (cls ? " " + cls : ""), text: value }));
      if (sub) t.appendChild(el("div", { class: "sub", text: sub }));
      return t;
    };
    const sign = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");
    wrap.appendChild(tile("Total return", fmt.pct(m.total_return), sign(m.total_return),
      fmt.money(nav[0]) + " → " + fmt.money(nav[nav.length - 1])));
    wrap.appendChild(tile("CAGR", fmt.pct(m.cagr), sign(m.cagr), m.benchmark_total_return != null ? "benchmark " + fmt.pct(m.benchmark_total_return) + " total" : null));
    wrap.appendChild(tile("Sharpe", fmt.num(m.sharpe), "", "Sortino " + fmt.num(m.sortino)));
    wrap.appendChild(tile("Max drawdown", fmt.pct(m.max_drawdown), "down", "Calmar " + fmt.num(m.calmar)));
    wrap.appendChild(tile("Volatility (ann.)", fmt.pct(m.annualised_volatility), "", "VaR95 " + fmt.pct(data.risk && data.risk.var_95)));
    if (m.beta != null) wrap.appendChild(tile("Beta", fmt.num(m.beta), "", "alpha " + fmt.pct(m.alpha) + " · IR " + fmt.num(m.information_ratio)));
    wrap.appendChild(tile("Round trips", fmt.int(ts.n_trades), "", ts.n_trades ? "win rate " + fmt.pct(ts.win_rate, 0) + " · PF " + fmt.num(ts.profit_factor) : "no completed trades"));
    if (sig) wrap.appendChild(tile("P(Sharpe > 0)", fmt.pct(sig.prob_sharpe_ratio, 1), sig.prob_sharpe_ratio > 0.95 ? "up" : "",
      "sign-flip p = " + fmt.num(sig.p_value_sharpe, 3)));
    return wrap;
  }

  function tradeMarkers(trades, t, xKey, yOf, tickerFilter) {
    const buys = trades.filter((tr) => tr.direction === 1 && (!tickerFilter || tr.ticker === tickerFilter));
    const sells = trades.filter((tr) => tr.direction === -1 && (!tickerFilter || tr.ticker === tickerFilter));
    const mk = (list, name, color, symbol) => ({
      type: "scatter", mode: "markers", name,
      x: list.map((tr) => tr[xKey]),
      y: list.map(yOf),
      marker: { symbol, size: 11, color, line: { width: 2, color: t.surface } },
      customdata: list.map((tr) => [tr.ticker, tr.quantity, tr.fill_price, tr.value, tr.commission]),
      hovertemplate: name + " %{customdata[0]}<br>qty %{customdata[1]:,.0f} @ %{customdata[2]:,.2f}<br>value %{customdata[3]:,.0f} · fee %{customdata[4]:,.2f}<extra></extra>",
    });
    return [mk(buys, "▲ Buy", t.good, "triangle-up"), mk(sells, "▼ Sell", t.critical, "triangle-down")];
  }

  function renderPriceCharts(data) {
    const prices = data.prices;
    if (!prices || !Object.keys(prices).length) return null;
    const t = theme();
    const tickers = Object.keys(prices);
    const c = card("Prices with executed orders", "One panel per ticker. ▲ marks a buy fill, ▼ a sell fill; hover a marker for quantity, price and fees.");
    const div = chartDiv(tickers.length > 1 ? "tall" : "");
    c.appendChild(div);
    const dates = data.series.dates;
    const traces = [];
    const layout = baseLayout(t, { showlegend: true, height: Math.max(300, 220 * tickers.length) });
    tickers.forEach((tk, i) => {
      const ax = i === 0 ? "" : String(i + 1);
      traces.push({
        type: "scatter", mode: "lines", name: tk, x: dates, y: prices[tk],
        line: { width: 1.6, color: t.s1 }, xaxis: "x" + ax, yaxis: "y" + ax,
        hovertemplate: tk + " %{y:,.2f}<extra></extra>", showlegend: false,
      });
      const priceAt = Object.fromEntries(dates.map((d, j) => [d, prices[tk][j]]));
      tradeMarkers(data.trades || [], t, "date", (tr) => tr.fill_price, tk).forEach((m, k) => {
        m.xaxis = "x" + ax; m.yaxis = "y" + ax; m.showlegend = i === 0; m.legendgroup = k ? "sell" : "buy";
        traces.push(m);
      });
      const domainH = 1 / tickers.length, gap = 0.06 / tickers.length;
      const top = 1 - i * domainH, bottom = top - domainH + gap;
      layout["yaxis" + ax] = Object.assign({}, layout.yaxis, { domain: [Math.max(0, bottom), top], title: { text: tk, font: { color: t.text2, size: 12 } } });
      layout["xaxis" + ax] = Object.assign({}, layout.xaxis, { anchor: "y" + ax, matches: i === 0 ? undefined : "x", showticklabels: i === tickers.length - 1 });
    });
    Plotly.newPlot(div, traces, layout, PLOT_CONFIG);
    return c;
  }

  function renderNav(data) {
    const t = theme();
    const s = data.series;
    const base = s.nav[0];
    const idx = s.nav.map((v) => (v == null ? null : (v / base) * 100));
    const c = card("Equity curve", "Indexed to 100 at inception. Order markers sit on the NAV at fill date.");
    const div = chartDiv();
    c.appendChild(div);
    const traces = [{
      type: "scatter", mode: "lines", name: "Strategy", x: s.dates, y: idx,
      line: { width: 2, color: t.s1 }, hovertemplate: "Strategy %{y:.1f}<extra></extra>",
    }];
    if (s.benchmark && s.benchmark.some((v) => v != null)) {
      const b0 = s.benchmark.find((v) => v != null);
      traces.push({
        type: "scatter", mode: "lines", name: data.meta.benchmark || "Benchmark", x: s.dates,
        y: s.benchmark.map((v) => (v == null ? null : (v / b0) * 100)),
        line: { width: 1.5, color: t.muted, dash: "dot" }, hovertemplate: "Benchmark %{y:.1f}<extra></extra>",
      });
    }
    const navAt = Object.fromEntries(s.dates.map((d, j) => [d, idx[j]]));
    tradeMarkers(data.trades || [], t, "date", (tr) => navAt[tr.date]).forEach((m) => traces.push(m));
    Plotly.newPlot(div, traces, baseLayout(t, { yaxis: Object.assign({}, baseLayout(t).yaxis, { title: { text: "Indexed value" } }) }), PLOT_CONFIG);
    return c;
  }

  function renderDrawdown(data) {
    const t = theme();
    const s = data.series;
    const c = card("Drawdown", "Distance below the running peak.");
    const div = chartDiv();
    c.appendChild(div);
    Plotly.newPlot(div, [{
      type: "scatter", mode: "lines", name: "Drawdown", x: s.dates, y: s.drawdown,
      fill: "tozeroy", line: { width: 1.5, color: t.s8 }, fillcolor: hexA(t.s8, 0.25),
      hovertemplate: "%{y:.2%}<extra></extra>",
    }], baseLayout(t, { showlegend: false, yaxis: Object.assign({}, baseLayout(t).yaxis, { tickformat: ".0%" }) }), PLOT_CONFIG);
    return c;
  }

  function renderMonthly(data) {
    const rows = data.monthly_returns || [];
    if (!rows.length) return null;
    const t = theme();
    const years = [...new Set(rows.map((r) => r.year))].sort();
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const z = years.map(() => Array(12).fill(null));
    rows.forEach((r) => { z[years.indexOf(r.year)][r.month - 1] = r.ret; });
    const maxAbs = Math.max(0.01, ...rows.map((r) => Math.abs(r.ret)));
    const c = card("Monthly returns", "Blue is positive, red negative, grey is flat. Compounded from daily NAV.");
    const div = chartDiv();
    c.appendChild(div);
    Plotly.newPlot(div, [{
      type: "heatmap", z, x: months, y: years.map(String), zmin: -maxAbs, zmax: maxAbs,
      colorscale: [[0, t.s8], [0.5, t.divMid], [1, t.s1]], xgap: 2, ygap: 2,
      text: z.map((row) => row.map((v) => (v == null ? "" : (v * 100).toFixed(1) + "%"))),
      texttemplate: "%{text}", textfont: { size: 11, color: t.text },
      hovertemplate: "%{y} %{x}: %{z:.2%}<extra></extra>", colorbar: { tickformat: ".0%", thickness: 10, outlinewidth: 0 },
    }], baseLayout(t, { hovermode: "closest", height: Math.max(220, 40 * years.length + 80), yaxis: { autorange: "reversed", type: "category" }, xaxis: { type: "category" } }), PLOT_CONFIG);
    return c;
  }

  function renderReturnsHist(data) {
    const t = theme();
    const r = (data.series.returns || []).filter((v) => v != null);
    if (!r.length) return null;
    const risk = data.risk || {};
    const c = card("Daily return distribution", "Dashed lines mark historical VaR at 95% and 99%.");
    const div = chartDiv();
    c.appendChild(div);
    const shapes = [];
    const annotations = [];
    [["var_95", "VaR 95"], ["var_99", "VaR 99"]].forEach(([k, label]) => {
      if (risk[k] == null) return;
      shapes.push({ type: "line", x0: -risk[k], x1: -risk[k], y0: 0, y1: 1, yref: "paper", line: { color: t.s8, width: 1.5, dash: "dash" } });
      annotations.push({ x: -risk[k], y: 1, yref: "paper", text: label, showarrow: false, yanchor: "bottom", font: { color: t.s8, size: 11 } });
    });
    Plotly.newPlot(div, [{
      type: "histogram", x: r, nbinsx: 60, marker: { color: t.s1, line: { width: 1, color: t.surface } },
      hovertemplate: "%{x:.2%}: %{y} days<extra></extra>", name: "Daily returns",
    }], baseLayout(t, { showlegend: false, hovermode: "closest", shapes, annotations, xaxis: Object.assign({}, baseLayout(t).xaxis, { tickformat: ".1%" }), bargap: 0.05 }), PLOT_CONFIG);
    return c;
  }

  function histTrace(hist, color, name, t) {
    const centers = hist.edges.slice(0, -1).map((e, i) => (e + hist.edges[i + 1]) / 2);
    const widths = hist.edges.slice(0, -1).map((e, i) => hist.edges[i + 1] - e);
    return { type: "bar", x: centers, y: hist.counts, width: widths, name, marker: { color, line: { width: 1, color: t.surface } }, hovertemplate: name + "<br>%{x:.2f}: %{y}<extra></extra>" };
  }

  function renderSignificance(data) {
    const sig = data.significance;
    const c = card("Statistical significance", null);
    if (!sig) {
      c.appendChild(el("p", { class: "muted", text: "Not computed (disabled, or fewer than 30 daily returns)." }));
      return c;
    }
    const t = theme();
    const verdictCls = sig.p_value_sharpe < 0.05 && sig.prob_sharpe_ratio > 0.95 ? "strong" : (sig.p_value_sharpe < 0.15 || sig.prob_sharpe_ratio > 0.85 ? "weak" : "none");
    const verdictText = {
      strong: "Strong evidence the strategy's Sharpe is genuinely positive: the sign-flip null rarely reaches the observed Sharpe and the Probabilistic Sharpe Ratio exceeds 95%.",
      weak: "Weak evidence. The observed Sharpe sits in the upper tail of the null distribution but not far enough to rule out luck at the 5% level.",
      none: "No evidence of skill beyond chance. A random-sign process produces a Sharpe this high about as often as the strategy did.",
    }[verdictCls];
    c.appendChild(el("div", { class: "verdict " + verdictCls, text: verdictText }));

    const grid = el("div", { class: "grid-2", style: "margin-top:12px" });
    // Bootstrap distribution of Sharpe with CI band
    const bootCard = el("div", { class: "card" });
    bootCard.appendChild(el("h3", { text: "Bootstrap distribution of Sharpe" }));
    bootCard.appendChild(el("p", { class: "chart-note", text: sig.n_samples + " stationary-bootstrap resamples of " + sig.n_observations + " daily returns. Shaded band is the 95% confidence interval; the line is the observed Sharpe." }));
    const bootDiv = chartDiv();
    bootCard.appendChild(bootDiv);
    const [lo, hi] = sig.sharpe_ci_95;
    Plotly.newPlot(bootDiv, [histTrace(sig.bootstrap_sharpe_hist, t.s1, "Bootstrap Sharpe", t)], baseLayout(t, {
      showlegend: false, hovermode: "closest", bargap: 0,
      shapes: [
        { type: "rect", x0: lo, x1: hi, y0: 0, y1: 1, yref: "paper", fillcolor: hexA(t.s1, 0.12), line: { width: 0 } },
        { type: "line", x0: sig.observed_sharpe, x1: sig.observed_sharpe, y0: 0, y1: 1, yref: "paper", line: { color: t.text, width: 2 } },
      ],
      annotations: [{ x: sig.observed_sharpe, y: 1, yref: "paper", yanchor: "bottom", text: "observed " + fmt.num(sig.observed_sharpe), showarrow: false, font: { color: t.text, size: 11 } }],
      xaxis: Object.assign({}, baseLayout(t).xaxis, { title: { text: "Annualised Sharpe" } }),
      yaxis: Object.assign({}, baseLayout(t).yaxis, { title: { text: "Resamples" } }),
    }), PLOT_CONFIG);
    grid.appendChild(bootCard);

    // Null distribution (sign flip)
    const nullCard = el("div", { class: "card" });
    nullCard.appendChild(el("h3", { text: "Null distribution (sign-flip test)" }));
    nullCard.appendChild(el("p", { class: "chart-note", text: "Sharpe of the same returns with random signs — what a strategy with no directional edge would produce. p = " + fmt.num(sig.p_value_sharpe, 4) + " is the share of null samples at or above the observed value." }));
    const nullDiv = chartDiv();
    nullCard.appendChild(nullDiv);
    Plotly.newPlot(nullDiv, [histTrace(sig.permutation_sharpe_hist, t.s2, "Null Sharpe", t)], baseLayout(t, {
      showlegend: false, hovermode: "closest", bargap: 0,
      shapes: [{ type: "line", x0: sig.observed_sharpe, x1: sig.observed_sharpe, y0: 0, y1: 1, yref: "paper", line: { color: t.text, width: 2 } }],
      annotations: [{ x: sig.observed_sharpe, y: 1, yref: "paper", yanchor: "bottom", text: "observed", showarrow: false, font: { color: t.text, size: 11 } }],
      xaxis: Object.assign({}, baseLayout(t).xaxis, { title: { text: "Annualised Sharpe under H0" } }),
      yaxis: Object.assign({}, baseLayout(t).yaxis, { title: { text: "Samples" } }),
    }), PLOT_CONFIG);
    grid.appendChild(nullCard);
    c.appendChild(grid);

    const kv = el("div", { class: "kv", style: "margin-top:12px" });
    const pcs = sig.bootstrap_sharpe_percentiles || {};
    const cpcs = sig.bootstrap_cagr_percentiles || {};
    [
      ["Observed Sharpe", fmt.num(sig.observed_sharpe)],
      ["Sharpe 95% CI (bootstrap)", "[" + fmt.num(lo) + ", " + fmt.num(hi) + "]"],
      ["Sharpe percentiles p5 / p50 / p95", fmt.num(pcs.p5) + " / " + fmt.num(pcs.p50) + " / " + fmt.num(pcs.p95)],
      ["Observed CAGR", fmt.pct(sig.observed_cagr)],
      ["CAGR 95% CI (bootstrap)", "[" + fmt.pct(sig.cagr_ci_95[0]) + ", " + fmt.pct(sig.cagr_ci_95[1]) + "]"],
      ["CAGR percentiles p5 / p50 / p95", fmt.pct(cpcs.p5) + " / " + fmt.pct(cpcs.p50) + " / " + fmt.pct(cpcs.p95)],
      ["Probabilistic Sharpe Ratio vs 0", fmt.pct(sig.prob_sharpe_ratio, 1)],
      ["Sign-flip p-value (one-sided)", fmt.num(sig.p_value_sharpe, 4)],
      ["t-statistic of mean daily return", fmt.num(sig.t_stat) + " (two-sided p = " + fmt.num(sig.p_value_t, 4) + ")"],
    ].forEach(([k, v]) => { kv.appendChild(el("div", { class: "k", text: k })); kv.appendChild(el("div", { class: "v", text: v })); });
    c.appendChild(kv);
    return c;
  }

  function renderStats(data) {
    const m = data.metrics || {}, r = data.risk || {}, ts = data.trade_stats || {};
    const wrap = el("div", { class: "grid-2" });
    const kvCard = (title, rows) => {
      const c = el("div", { class: "card" });
      c.appendChild(el("h2", { text: title }));
      const kv = el("div", { class: "kv" });
      rows.forEach(([k, v]) => { kv.appendChild(el("div", { class: "k", text: k })); kv.appendChild(el("div", { class: "v", text: v })); });
      c.appendChild(kv);
      return c;
    };
    const perf = [
      ["Total return", fmt.pct(m.total_return)], ["CAGR", fmt.pct(m.cagr)],
      ["Annualised volatility", fmt.pct(m.annualised_volatility)], ["Sharpe", fmt.num(m.sharpe)],
      ["Sortino", fmt.num(m.sortino)], ["Calmar", fmt.num(m.calmar)],
      ["Max drawdown", fmt.pct(m.max_drawdown)], ["Skew / kurtosis", fmt.num(m.skew) + " / " + fmt.num(m.kurtosis)],
      ["Best / worst day", fmt.pct(m.best_day) + " / " + fmt.pct(m.worst_day)],
      ["Positive days", fmt.pct(m.positive_days_pct, 1)], ["Trading days", fmt.int(m.n_days)],
    ];
    if (m.beta != null) perf.push(["Alpha (ann.) / Beta", fmt.pct(m.alpha) + " / " + fmt.num(m.beta)], ["Information ratio", fmt.num(m.information_ratio)]);
    wrap.appendChild(kvCard("Performance", perf));
    wrap.appendChild(kvCard("Risk", [
      ["VaR 95% (1-day, historical)", fmt.pct(r.var_95)], ["VaR 99% (1-day, historical)", fmt.pct(r.var_99)],
      ["CVaR 95% (expected shortfall)", fmt.pct(r.cvar_95)],
      ["Drawdown episodes > 5%", fmt.int((data.recovery_periods || []).length)],
    ]));
    wrap.appendChild(kvCard("Trades", ts.n_trades ? [
      ["Round trips", fmt.int(ts.n_trades) + " (" + fmt.int(ts.n_wins) + " W / " + fmt.int(ts.n_losses) + " L)"],
      ["Win rate", fmt.pct(ts.win_rate, 1)], ["Profit factor", fmt.num(ts.profit_factor)],
      ["Expectancy per trade", fmt.money2(ts.expectancy)], ["Average return per trade", fmt.pct(ts.avg_return_pct)],
      ["Avg win / avg loss", fmt.money2(ts.avg_win) + " / " + fmt.money2(ts.avg_loss)],
      ["Best / worst trade", fmt.money2(ts.best_trade) + " / " + fmt.money2(ts.worst_trade)],
      ["Avg holding period", fmt.num(ts.avg_holding_days, 1) + " days"],
      ["Max consecutive wins / losses", fmt.int(ts.max_consecutive_wins) + " / " + fmt.int(ts.max_consecutive_losses)],
      ["Total PnL (net)", fmt.money2(ts.total_pnl)], ["Total commission", fmt.money2(ts.total_commission)],
      ["Fills", fmt.int((data.trades || []).length)],
    ] : [["Round trips", "0"], ["Fills", fmt.int((data.trades || []).length)]]));
    return wrap;
  }

  function table(columns, rows, limit) {
    const wrap = el("div", { class: "table-wrap" });
    const tbl = el("table");
    const thead = el("thead"); const trh = el("tr");
    columns.forEach((c) => trh.appendChild(el("th", { class: c.num ? "num" : "", text: c.label })));
    thead.appendChild(trh); tbl.appendChild(thead);
    const tbody = el("tbody");
    const render = (n) => {
      tbody.innerHTML = "";
      rows.slice(0, n).forEach((r) => {
        const tr = el("tr");
        columns.forEach((c) => {
          const v = c.get(r);
          const cls = [c.num ? "num" : "", c.signed && typeof c.raw === "function" ? (c.raw(r) > 0 ? "pos" : c.raw(r) < 0 ? "neg" : "") : ""].join(" ").trim();
          tr.appendChild(el("td", { class: cls, text: v }));
        });
        tbody.appendChild(tr);
      });
    };
    render(limit || rows.length);
    tbl.appendChild(tbody);
    wrap.appendChild(tbl);
    if (limit && rows.length > limit) {
      const btn = el("button", { class: "ghost", text: "Show all " + rows.length + " rows" });
      btn.addEventListener("click", () => { render(rows.length); btn.remove(); });
      wrap.appendChild(btn);
    }
    return wrap;
  }

  function renderRoundTrips(data) {
    const rows = data.round_trips || [];
    const c = card("Round trips", rows.length ? "FIFO-matched entries and exits, net of commission." : null);
    if (!rows.length) { c.appendChild(el("p", { class: "muted", text: "No completed round trips." })); return c; }
    c.appendChild(table([
      { label: "Ticker", get: (r) => r.ticker },
      { label: "Entry", get: (r) => fmt.date(r.entry_date) },
      { label: "Exit", get: (r) => fmt.date(r.exit_date) },
      { label: "Qty", num: true, get: (r) => fmt.money(r.quantity) },
      { label: "Entry px", num: true, get: (r) => fmt.money2(r.entry_price) },
      { label: "Exit px", num: true, get: (r) => fmt.money2(r.exit_price) },
      { label: "PnL", num: true, signed: true, raw: (r) => r.pnl, get: (r) => fmt.money2(r.pnl) },
      { label: "Return", num: true, signed: true, raw: (r) => r.return_pct, get: (r) => fmt.pct(r.return_pct) },
      { label: "Days", num: true, get: (r) => fmt.int(r.holding_days) },
    ], rows, 25));
    return c;
  }

  function renderFills(data) {
    const rows = data.trades || [];
    const c = card("Order fills", rows.length ? "Every executed order in chronological sequence." : null);
    if (!rows.length) { c.appendChild(el("p", { class: "muted", text: "No orders were executed." })); return c; }
    c.appendChild(table([
      { label: "Date", get: (r) => fmt.date(r.date) },
      { label: "Ticker", get: (r) => r.ticker },
      { label: "Side", get: (r) => (r.direction === 1 ? "▲ Buy" : "▼ Sell") },
      { label: "Qty", num: true, get: (r) => fmt.money(r.quantity) },
      { label: "Fill px", num: true, get: (r) => fmt.money2(r.fill_price) },
      { label: "Value", num: true, get: (r) => fmt.money(r.value) },
      { label: "Fee", num: true, get: (r) => fmt.money2(r.commission) },
      { label: "Cash after", num: true, get: (r) => fmt.money(r.cash_after) },
    ], rows, 25));
    return c;
  }

  function renderRecovery(data) {
    const rows = data.recovery_periods || [];
    const c = card("Drawdown episodes", rows.length ? "Episodes deeper than 5%, peak to recovery." : null);
    if (!rows.length) { c.appendChild(el("p", { class: "muted", text: "No drawdown deeper than 5%." })); return c; }
    c.appendChild(table([
      { label: "Peak", get: (r) => fmt.date(r.peak_date) },
      { label: "Trough", get: (r) => fmt.date(r.trough_date) },
      { label: "Recovery", get: (r) => (r.recovery_date ? fmt.date(r.recovery_date) : "ongoing") },
      { label: "Depth", num: true, signed: true, raw: (r) => r.drawdown, get: (r) => fmt.pct(r.drawdown) },
      { label: "Days", num: true, get: (r) => fmt.int(r.duration_days) },
    ], rows, 15));
    return c;
  }

  function renderCorrelation(data) {
    const corr = data.correlation;
    if (!corr || corr.tickers.length < 2) return null;
    const t = theme();
    const c = card("Asset return correlation", null);
    const div = chartDiv();
    c.appendChild(div);
    Plotly.newPlot(div, [{
      type: "heatmap", z: corr.matrix, x: corr.tickers, y: corr.tickers, zmin: -1, zmax: 1,
      colorscale: [[0, t.s8], [0.5, t.divMid], [1, t.s1]], xgap: 2, ygap: 2,
      text: corr.matrix.map((row) => row.map((v) => v.toFixed(2))), texttemplate: "%{text}", textfont: { color: t.text, size: 11 },
      hovertemplate: "%{y} vs %{x}: %{z:.2f}<extra></extra>", colorbar: { thickness: 10, outlinewidth: 0 },
    }], baseLayout(t, { hovermode: "closest", height: Math.max(240, 40 * corr.tickers.length + 100), yaxis: { autorange: "reversed", type: "category" }, xaxis: { type: "category" } }), PLOT_CONFIG);
    return c;
  }

  function hexA(hex, a) {
    const h = hex.replace("#", "");
    if (h.length !== 6) return hex;
    const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    return "rgba(" + r + "," + g + "," + b + "," + a + ")";
  }

  // ── entry point ─────────────────────────────────────────────────────────
  function renderReport(container, data) {
    container.innerHTML = "";
    if (!data || !data.series || !data.series.nav || !data.series.nav.length) {
      container.appendChild(el("p", { class: "error", text: "Run contains no NAV series." }));
      return;
    }
    const sections = [
      renderHeader(data),
      renderTiles(data),
      el("div", { style: "height:12px" }),
      renderPriceCharts(data),
      renderNav(data),
    ];
    const pair = el("div", { class: "grid-2 section" });
    [renderDrawdown(data), renderMonthly(data)].forEach((c) => c && pair.appendChild(c));
    sections.push(pair);
    sections.push(renderSignificance(data));
    const pair2 = el("div", { class: "grid-2 section" });
    [renderReturnsHist(data), renderCorrelation(data)].forEach((c) => c && pair2.appendChild(c));
    sections.push(pair2);
    sections.push(renderStats(data));
    sections.push(el("div", { style: "height:12px" }));
    sections.push(renderRoundTrips(data));
    sections.push(renderFills(data));
    sections.push(renderRecovery(data));
    sections.forEach((s) => s && container.appendChild(s));
  }

  window.renderReport = renderReport;
  window.reportFormat = fmt;
})();
