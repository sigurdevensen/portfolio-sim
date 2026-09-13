"""HTMLReporter: renders a serialised run into one self-contained interactive page.

The page inlines ``web/static/report.js`` and ``web/static/style.css`` together
with the run JSON, so it opens from disk without the platform server. Plotly is
loaded from its CDN (the only external dependency).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"
PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"


class HTMLReporter:
    """Write ``report.html`` for a run dict produced by ``report_to_dict``."""

    def __init__(self, static_dir: Path | None = None) -> None:
        self.static_dir = Path(static_dir) if static_dir else STATIC_DIR

    def write(self, run: dict[str, Any], output_dir: str | Path = "reports/") -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "report.html"
        path.write_text(self.render(run), encoding="utf-8")
        return path

    def render(self, run: dict[str, Any]) -> str:
        css = (self.static_dir / "style.css").read_text(encoding="utf-8")
        js = (self.static_dir / "report.js").read_text(encoding="utf-8")
        meta = run.get("meta", {})
        title = f"{meta.get('strategy', 'strategy')} backtest report"
        # Escape "</" so a payload string can never terminate the script element.
        payload = json.dumps(run, ensure_ascii=False).replace("</", "<\\/")
        return TEMPLATE.format(
            title=_escape(title),
            css=css,
            js=js.replace("</script", "<\\/script"),
            payload=payload,
            plotly=PLOTLY_CDN,
        )


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
    <div class="brand"><span class="dot"></span><h1>portfolio-sim</h1><span class="muted">backtest report</span></div>
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
  function render() {{ window.renderReport(document.getElementById("report"), data); }}
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
