"""MarkdownReporter: renders a BacktestReport to a .md file with chart images."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for file saving
import matplotlib.pyplot as plt

from evaluation.evaluator import BacktestReport
from visualization.performance import plot_nav, plot_returns_distribution
from visualization.risk import plot_drawdown


class MarkdownReporter:
    """Writes a BacktestReport to a Markdown file with accompanying chart PNGs."""

    def write(self, report: BacktestReport, output_dir: str | Path = "reports/") -> Path:
        """Render the report and save to disk.

        Args:
            report: The BacktestReport to render.
            output_dir: Directory where report.md and charts are saved.

        Returns:
            Path to the written report.md file.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        self._save_chart(
            plot_nav(report.result.nav, report.result.benchmark, title=f"{report.strategy_name} NAV"),
            output_dir / "nav_curve.png",
        )
        self._save_chart(
            plot_drawdown(report.result.nav),
            output_dir / "drawdown.png",
        )
        returns = report.result.nav.pct_change().dropna()
        self._save_chart(
            plot_returns_distribution(returns),
            output_dir / "returns_dist.png",
        )

        md_path = output_dir / "report.md"
        md_path.write_text(self._render(report), encoding="utf-8")
        return md_path

    @staticmethod
    def _save_chart(fig: plt.Figure, path: Path) -> None:
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)

    @staticmethod
    def _render(report: BacktestReport) -> str:
        m = report.metrics
        nav = report.result.nav
        start = nav.index[0].date()
        end = nav.index[-1].date()

        def pct(v: float) -> str:
            return f"{v:.2%}"

        def f2(v: float) -> str:
            return f"{v:.2f}"

        lines: list[str] = [
            f"# Backtest Report — {report.strategy_name}",
            "",
            f"**Period:** {start} → {end}",
            f"**NAV:** {nav.iloc[0]:,.0f} → {nav.iloc[-1]:,.0f}",
            "",
            "## Performance Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Return | {pct(m.get('total_return', 0))} |",
            f"| CAGR | {pct(m.get('cagr', 0))} |",
            f"| Sharpe Ratio | {f2(m.get('sharpe', 0))} |",
            f"| Annualised Volatility | {pct(m.get('annualised_volatility', 0))} |",
            f"| Max Drawdown | {pct(m.get('max_drawdown', 0))} |",
        ]

        if "alpha" in m:
            lines += [
                f"| Alpha (annualised) | {f2(m['alpha'])} |",
                f"| Beta | {f2(m['beta'])} |",
                f"| Information Ratio | {f2(m.get('information_ratio', 0))} |",
            ]

        lines += [
            "",
            "## Risk Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| VaR 95% (1-day, historical) | {pct(report.var_95)} |",
            f"| VaR 99% (1-day, historical) | {pct(report.var_99)} |",
            f"| CVaR 95% (Expected Shortfall) | {pct(report.cvar_95)} |",
            "",
            "## Drawdown Analysis",
            "",
        ]

        rp = report.recovery_periods
        if rp:
            lines += [
                "| Peak | Trough | Recovery | Drawdown | Days |",
                "|------|--------|----------|----------|------|",
            ]
            for period in rp[:10]:
                rec = str(period.recovery_date.date()) if period.recovery_date else "N/A"
                lines.append(
                    f"| {period.peak_date.date()} | {period.trough_date.date()} "
                    f"| {rec} | {pct(period.drawdown)} | {period.duration_days} |"
                )
        else:
            lines.append("No significant drawdown episodes (threshold: -5%).")

        lines += [
            "",
            "## Charts",
            "",
            "![NAV Curve](nav_curve.png)",
            "",
            "![Drawdown](drawdown.png)",
            "",
            "![Returns Distribution](returns_dist.png)",
            "",
            "## Trade Log",
            "",
        ]

        trades = report.result.trades
        if not trades.empty:
            lines.append(f"Total trades: {len(trades)}")
            lines.append("")
            lines.append(_df_to_markdown(trades.head(20)))
        else:
            lines.append("No trades executed.")

        return "\n".join(lines) + "\n"


def _df_to_markdown(df) -> str:
    """DataFrame -> Markdown table without requiring tabulate."""
    cols = list(df.columns)
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for _, row in df.iterrows()]
    return "\n".join([header, sep] + rows)
