"""Self-contained interactive HTML reports.

``HTMLReporter`` renders one backtest run (``report.js`` / ``renderReport``);
``BatchHTMLReporter`` renders an algorithm-lab batch (``batch.js`` / ``renderBatch``).
Both inline ``web/static/style.css``, the renderer script and the JSON payload so
the page opens from disk without the platform server. Plotly comes from its CDN.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"
PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"


class HTMLReporter:
    """Write ``report.html`` for a run dict produced by ``report_to_dict``."""

    SCRIPT = "report.js"
    RENDER_FN = "renderReport"
    SUBTITLE = "backtest report"

    def __init__(self, static_dir: Path | None = None) -> None:
        self.static_dir = Path(static_dir) if static_dir else STATIC_DIR

    def write(self, doc: dict[str, Any], output_dir: str | Path = "reports/") -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "report.html"
        path.write_text(self.render(doc), encoding="utf-8")
        return path

    def title(self, doc: dict[str, Any]) -> str:
        return f"{doc.get('meta', {}).get('strategy', 'strategy')} backtest report"

    def render(self, doc: dict[str, Any]) -> str:
        css = (self.static_dir / "style.css").read_text(encoding="utf-8")
        js = (self.static_dir / self.SCRIPT).read_text(encoding="utf-8")
        # Escape "</" so a payload string can never terminate the script element.
        payload = json.dumps(doc, ensure_ascii=False).replace("</", "<\\/")
        return TEMPLATE.format(
            title=_escape(self.title(doc)),
            subtitle=_escape(self.SUBTITLE),
            css=css,
            js=js.replace("</script", "<\\/script"),
            payload=payload,
            plotly=PLOTLY_CDN,
            render_fn=self.RENDER_FN,
        )


class BatchHTMLReporter(HTMLReporter):
    """Write ``report.html`` for a batch dict produced by ``batch_to_dict``."""

    SCRIPT = "batch.js"
    RENDER_FN = "renderBatch"
    SUBTITLE = "algorithm lab report"

    def title(self, doc: dict[str, Any]) -> str:
        meta = doc.get("meta", {})
        return f"Algorithm lab — {meta.get('n_algorithms', '?')} algorithms on {', '.join(meta.get('tickers', []) or [])}"

    def write(self, doc: dict[str, Any], output_dir: str | Path = "reports/") -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        html = self.render(doc)
        (output_dir / "report.html").write_text(html, encoding="utf-8")
        path = output_dir / "batch.html"
        path.write_text(html, encoding="utf-8")
        return path


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{css}
</style>
<script src="{plotly}" charset="utf-8"></script>
</head>
<body>
<div class="shell">
  <div class="topbar">
    <div class="brand"><span class="dot"></span><h1>portfolio-sim</h1><span class="muted">{subtitle}</span></div>
    <div class="spacer"></div>
    <button class="ghost" id="theme-toggle" type="button">Toggle theme</button>
  </div>
  <div id="report"></div>
</div>
<script id="run-data" type="application/json">{payload}</script>
<script>
{js}
</script>
<script>
(function () {{
  var data = JSON.parse(document.getElementById("run-data").textContent);
  var root = document.documentElement;
  function render() {{ window.{render_fn}(document.getElementById("report"), data); }}
  document.getElementById("theme-toggle").addEventListener("click", function () {{
    var dark = root.getAttribute("data-theme") === "dark" ||
      (!root.getAttribute("data-theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
    root.setAttribute("data-theme", dark ? "light" : "dark");
    render();
  }});
  render();
}})();
</script>
</body>
</html>
"""
