# Trading Algorithm Testing System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, importable trading algorithm testing system with LSEG data feed, backtest engine, simulated execution, and markdown evaluation reports.

**Architecture:** A `Pipeline` class wires four modules together: `LSEGDataFeed` fetches OHLCV/fundamentals from LSEG Workspace API (with yfinance fallback), `BacktestEngine.run()` drives the simulation loop date-by-date, `FillSimulator` applies slippage and commission to orders, and `Evaluator` + `MarkdownReporter` compute risk-adjusted metrics and write a report.

**Tech Stack:** Python 3.11+, pandas, numpy, scipy, matplotlib, lseg-data (LSEG Workspace API), yfinance, pytest

---

## File Map

**Create:**
- `execution/__init__.py`
- `execution/order.py` — `Order` and `Fill` dataclasses
- `execution/fill.py` — `FillSimulator`
- `data/lseg.py` — `LSEGDataFeed`
- `evaluation/__init__.py`
- `evaluation/evaluator.py` — `BacktestReport` dataclass + `Evaluator`
- `evaluation/reporter.py` — `MarkdownReporter`
- `pipeline/__init__.py`
- `pipeline/pipeline.py` — `Pipeline` class
- `scripts/run_pipeline.py` — CLI wrapper
- `tests/test_execution.py`
- `tests/test_engine.py`
- `tests/test_lseg_feed.py`
- `tests/test_evaluator.py`
- `tests/test_pipeline.py`

**Modify:**
- `backtesting/engine.py` — implement `BacktestEngine.run()`
- `requirements.txt` — add `lseg-data`

---

## Task 1: Execution Layer

**Files:**
- Create: `execution/__init__.py`
- Create: `execution/order.py`
- Create: `execution/fill.py`
- Test: `tests/test_execution.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_execution.py`:

```python
import math
import pytest
from execution.order import Order, Fill
from execution.fill import FillSimulator
import pandas as pd


def _order(direction: int, qty: float = 100.0) -> Order:
    return Order(
        ticker="EQNR.OL",
        direction=direction,
        quantity=qty,
        timestamp=pd.Timestamp("2024-01-02", tz="UTC"),
    )


def test_fill_buy_applies_slippage():
    sim = FillSimulator(slippage=0.001, commission_rate=0.001)
    fill = sim.execute(_order(1), close_price=100.0)
    assert fill.fill_price == pytest.approx(100.1)   # 100 * (1 + 1 * 0.001)


def test_fill_sell_applies_slippage():
    sim = FillSimulator(slippage=0.001, commission_rate=0.001)
    fill = sim.execute(_order(-1), close_price=100.0)
    assert fill.fill_price == pytest.approx(99.9)    # 100 * (1 + -1 * 0.001)


def test_fill_hold_no_slippage():
    sim = FillSimulator(slippage=0.001, commission_rate=0.001)
    fill = sim.execute(_order(0), close_price=100.0)
    assert fill.fill_price == pytest.approx(100.0)


def test_fill_commission_rate_passed_through():
    sim = FillSimulator(slippage=0.0, commission_rate=0.002)
    fill = sim.execute(_order(1), close_price=50.0)
    assert fill.commission_rate == 0.002


def test_fill_preserves_order():
    order = _order(1, qty=200.0)
    sim = FillSimulator(slippage=0.0, commission_rate=0.001)
    fill = sim.execute(order, close_price=50.0)
    assert fill.order is order
    assert fill.order.quantity == 200.0
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_execution.py -v
```
Expected: `ModuleNotFoundError: No module named 'execution'`

- [ ] **Step 3: Create `execution/order.py`**

```python
"""Order and Fill dataclasses for the simulated execution layer."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Order:
    ticker: str
    direction: int          # {-1, 0, 1}
    quantity: float
    timestamp: pd.Timestamp


@dataclass
class Fill:
    order: Order
    fill_price: float
    commission_rate: float  # fraction, e.g. 0.001 for 0.1%
```

- [ ] **Step 4: Create `execution/fill.py`**

```python
"""FillSimulator: applies slippage and commission to an order."""
from __future__ import annotations

from execution.order import Fill, Order


class FillSimulator:
    """Stateless fill execution with configurable slippage and commission."""

    def __init__(self, slippage: float = 0.0005, commission_rate: float = 0.001) -> None:
        self.slippage = slippage
        self.commission_rate = commission_rate

    def execute(self, order: Order, close_price: float) -> Fill:
        """Apply directional slippage to close_price and return a Fill.

        Args:
            order: The order to fill.
            close_price: End-of-day close price for the ticker.

        Returns:
            Fill with slippage-adjusted fill_price and commission_rate.
        """
        fill_price = close_price * (1 + order.direction * self.slippage)
        return Fill(order=order, fill_price=fill_price, commission_rate=self.commission_rate)
```

- [ ] **Step 5: Create `execution/__init__.py`**

```python
from execution.fill import FillSimulator
from execution.order import Fill, Order

__all__ = ["Order", "Fill", "FillSimulator"]
```

- [ ] **Step 6: Run tests to verify they pass**

```
pytest tests/test_execution.py -v
```
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add execution/ tests/test_execution.py
git commit -m "feat: add execution layer (Order, Fill, FillSimulator)"
```

---

## Task 2: BacktestEngine.run()

**Files:**
- Modify: `backtesting/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_engine.py`:

```python
import math
import pandas as pd
import numpy as np
import pytest
from backtesting.engine import BacktestConfig, BacktestEngine
from backtesting.metrics import BacktestResult
from strategies.base import Strategy


def _prices(n_days: int = 50, tickers: list[str] | None = None) -> pd.DataFrame:
    """Synthetic price DataFrame: flat prices, UTC-indexed."""
    if tickers is None:
        tickers = ["AAA"]
    idx = pd.date_range("2023-01-02", periods=n_days, freq="B", tz="UTC")
    data = {t: np.full(n_days, 100.0) for t in tickers}
    return pd.DataFrame(data, index=idx)


class AlwaysBuyStrategy(Strategy):
    name = "always_buy"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(1, index=data.index, columns=data.columns)


class AlwaysSellStrategy(Strategy):
    name = "always_sell"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(-1, index=data.index, columns=data.columns)


class HoldStrategy(Strategy):
    name = "hold"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(0, index=data.index, columns=data.columns)


def _config(start: str = "2023-01-02", end: str = "2023-04-01") -> BacktestConfig:
    return BacktestConfig(
        start=start,
        end=end,
        initial_capital=10_000.0,
        commission=0.0,
        slippage=0.0,
    )


def test_run_returns_backtest_result():
    prices = _prices()
    engine = BacktestEngine(_config())
    result = engine.run(AlwaysBuyStrategy(), prices)
    assert isinstance(result, BacktestResult)


def test_nav_series_not_empty():
    prices = _prices(50)
    engine = BacktestEngine(_config())
    result = engine.run(AlwaysBuyStrategy(), prices)
    assert len(result.nav) > 0


def test_hold_strategy_nav_stays_at_initial():
    prices = _prices(50)
    engine = BacktestEngine(_config())
    result = engine.run(HoldStrategy(), prices)
    # no trades — NAV = initial capital throughout
    assert result.nav.iloc[0] == pytest.approx(10_000.0)
    assert result.nav.iloc[-1] == pytest.approx(10_000.0)


def test_buy_signal_generates_trade():
    prices = _prices(50)
    engine = BacktestEngine(_config())
    result = engine.run(AlwaysBuyStrategy(), prices)
    assert not result.trades.empty
    assert "ticker" in result.trades.columns


def test_nav_stays_close_to_initial_on_flat_prices():
    """With flat prices and no commission, NAV should not drift far from initial."""
    prices = _prices(50)
    engine = BacktestEngine(_config())
    result = engine.run(AlwaysBuyStrategy(), prices)
    # Allow small rounding from share quantity flooring
    assert abs(result.nav.iloc[-1] - 10_000.0) < 500.0


def test_multi_ticker_both_traded():
    prices = _prices(50, tickers=["AAA", "BBB"])
    engine = BacktestEngine(_config())
    result = engine.run(AlwaysBuyStrategy(), prices)
    traded_tickers = set(result.trades["ticker"].unique())
    assert "AAA" in traded_tickers
    assert "BBB" in traded_tickers
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_engine.py -v
```
Expected: all FAIL with `NotImplementedError` from `engine.run()`

- [ ] **Step 3: Implement `BacktestEngine.run()` in `backtesting/engine.py`**

Replace the entire file:

```python
"""Core backtesting engine — drives the simulation loop."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

from backtesting.metrics import BacktestResult
from backtesting.portfolio import Portfolio
from execution.fill import FillSimulator
from execution.order import Order

if TYPE_CHECKING:
    from strategies.base import Strategy


@dataclass
class BacktestConfig:
    start: str
    end: str
    initial_capital: float = 100_000.0
    commission: float = 0.001   # fraction, e.g. 0.001 = 0.1%
    slippage: float = 0.0005    # fraction, e.g. 0.0005 = 5 bps


class BacktestEngine:
    """Runs a strategy against historical price data."""

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    def run(self, strategy: "Strategy", prices: pd.DataFrame) -> BacktestResult:
        """Execute backtest and return a result object.

        Args:
            strategy: A Strategy instance with generate_signals().
            prices: DataFrame with UTC DatetimeIndex, one column per ticker (adjusted close).

        Returns:
            BacktestResult with NAV series, trades DataFrame, and computed metrics.
        """
        start = pd.Timestamp(self.config.start, tz="UTC")
        end = pd.Timestamp(self.config.end, tz="UTC")
        prices_in_range = prices.loc[start:end]

        if prices_in_range.empty:
            raise ValueError(f"No price data between {self.config.start} and {self.config.end}")

        signals_df = strategy.generate_signals(prices_in_range)

        portfolio = Portfolio(self.config.initial_capital)
        fill_sim = FillSimulator(
            slippage=self.config.slippage,
            commission_rate=self.config.commission,
        )

        tickers = prices_in_range.columns.tolist()
        n_tickers = len(tickers)
        prior_signals: dict[str, int] = {t: 0 for t in tickers}
        fills_log: list[dict] = []

        for date in prices_in_range.index:
            if date not in signals_df.index:
                continue

            current_signals = signals_df.loc[date]
            prices_today = prices_in_range.loc[date]
            valid_prices = {
                t: float(prices_today[t])
                for t in tickers
                if not pd.isna(prices_today[t])
            }

            if not valid_prices:
                continue

            nav_start = portfolio.market_value(valid_prices)

            for ticker in tickers:
                if ticker not in valid_prices:
                    continue

                sig = int(current_signals.get(ticker, 0))
                prev_sig = prior_signals.get(ticker, 0)

                if sig == prev_sig:
                    continue

                price = valid_prices[ticker]

                if sig == 1 and ticker not in portfolio.positions:
                    target_alloc = nav_start / n_tickers
                    shares = math.floor(target_alloc / price)
                    if shares <= 0:
                        continue
                    order = Order(ticker=ticker, direction=1, quantity=float(shares), timestamp=date)
                    fill = fill_sim.execute(order, price)
                    try:
                        portfolio.buy(ticker, fill.order.quantity, fill.fill_price, fill.commission_rate)
                        fills_log.append({
                            "date": date,
                            "ticker": ticker,
                            "direction": 1,
                            "quantity": fill.order.quantity,
                            "fill_price": fill.fill_price,
                            "commission": fill.order.quantity * fill.fill_price * fill.commission_rate,
                        })
                    except ValueError:
                        pass

                elif sig == -1 and ticker in portfolio.positions:
                    shares = portfolio.positions[ticker].shares
                    order = Order(ticker=ticker, direction=-1, quantity=shares, timestamp=date)
                    fill = fill_sim.execute(order, price)
                    try:
                        portfolio.sell(ticker, fill.order.quantity, fill.fill_price, fill.commission_rate)
                        fills_log.append({
                            "date": date,
                            "ticker": ticker,
                            "direction": -1,
                            "quantity": fill.order.quantity,
                            "fill_price": fill.fill_price,
                            "commission": fill.order.quantity * fill.fill_price * fill.commission_rate,
                        })
                    except ValueError:
                        pass

            portfolio.record_nav(date, valid_prices)
            prior_signals = {t: int(current_signals.get(t, 0)) for t in tickers}

        trades_df = (
            pd.DataFrame(fills_log)
            if fills_log
            else pd.DataFrame(columns=["date", "ticker", "direction", "quantity", "fill_price", "commission"])
        )
        return BacktestResult(nav=portfolio.nav_series, trades=trades_df)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_engine.py -v
```
Expected: 6 passed

- [ ] **Step 5: Run the full existing test suite to check for regressions**

```
pytest tests/ -v
```
Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add backtesting/engine.py tests/test_engine.py
git commit -m "feat: implement BacktestEngine.run() simulation loop"
```

---

## Task 3: LSEG DataFeed

**Files:**
- Create: `data/lseg.py`
- Modify: `requirements.txt`
- Test: `tests/test_lseg_feed.py`

- [ ] **Step 1: Add lseg-data to requirements.txt**

Open `requirements.txt` and add at the end:

```
lseg-data>=2.0
```

Note: install via `pip install lseg-data`. LSEG Workspace desktop app must be running for live calls.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_lseg_feed.py`:

```python
"""Tests for LSEGDataFeed — mocks the lseg.data library to avoid requiring a Workspace session."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import pytest

from data.lseg import LSEGDataFeed


def _fake_history(tickers: list[str], n: int = 10) -> pd.DataFrame:
    """Simulate what ld.get_history() returns: DatetimeIndex, one column per ticker."""
    idx = pd.date_range("2024-01-02", periods=n, freq="B", tz="UTC")
    data = {t: np.random.uniform(80, 120, n) for t in tickers}
    df = pd.DataFrame(data, index=idx)
    df.columns.name = None
    return df


def _fake_history_with_off_close(tickers: list[str], n: int = 10) -> pd.DataFrame:
    """Simulate LSEG returning OFF_CLOSE instead of TRDPRC_1 (Norwegian listings)."""
    idx = pd.date_range("2024-01-02", periods=n, freq="B", tz="UTC")
    data = {}
    for t in tickers:
        inner = pd.DataFrame({"OFF_CLOSE": np.random.uniform(80, 120, n)}, index=idx)
        data[t] = inner["OFF_CLOSE"]
    return pd.DataFrame(data)


@patch("data.lseg.ld")
def test_fetch_prices_returns_dataframe(mock_ld):
    mock_ld.get_history.return_value = _fake_history(["EQNR.OL"])
    feed = LSEGDataFeed(use_cache=False)
    df = feed.fetch_prices(["EQNR.OL"], "2024-01-01", "2024-03-01")
    assert isinstance(df, pd.DataFrame)
    assert "EQNR.OL" in df.columns
    assert df.index.tz is not None  # UTC-aware


@patch("data.lseg.ld")
def test_fetch_prices_multiple_tickers(mock_ld):
    mock_ld.get_history.return_value = _fake_history(["EQNR.OL", "DNB.OL"])
    feed = LSEGDataFeed(use_cache=False)
    df = feed.fetch_prices(["EQNR.OL", "DNB.OL"], "2024-01-01", "2024-03-01")
    assert set(df.columns) == {"EQNR.OL", "DNB.OL"}


@patch("data.lseg.ld")
def test_fetch_prices_caches_result(mock_ld, tmp_path):
    mock_ld.get_history.return_value = _fake_history(["DNB.OL"])
    feed = LSEGDataFeed(use_cache=True, cache_dir=tmp_path)
    feed.fetch_prices(["DNB.OL"], "2024-01-01", "2024-03-01")
    feed.fetch_prices(["DNB.OL"], "2024-01-01", "2024-03-01")
    # second call should hit cache — ld.get_history called only once
    assert mock_ld.get_history.call_count == 1


@patch("data.lseg.ld")
def test_fetch_fundamentals_returns_dict(mock_ld):
    mock_ld.get_data.return_value = pd.DataFrame(
        {"P/E": [12.5], "EPS": [3.1]},
        index=["EQNR.OL"],
    )
    feed = LSEGDataFeed(use_cache=False)
    result = feed.fetch_fundamentals(["EQNR.OL"])
    assert isinstance(result, dict)
    assert "EQNR.OL" in result
    assert "P/E" in result["EQNR.OL"]


@patch("data.lseg.ld")
def test_fetch_index_constituents_returns_list(mock_ld):
    mock_ld.get_data.return_value = pd.DataFrame(
        {"TR.IndexConstituentRIC": ["EQNR.OL", "DNB.OL", "TEL.OL"]}
    )
    feed = LSEGDataFeed(use_cache=False)
    result = feed.fetch_index_constituents(".OSEBX")
    assert isinstance(result, list)
    assert "EQNR.OL" in result


@patch("data.lseg.ld")
def test_fetch_prices_raises_on_session_failure(mock_ld):
    mock_ld.get_history.side_effect = Exception("Workspace not running")
    feed = LSEGDataFeed(use_cache=False)
    with pytest.raises(RuntimeError, match="LSEG"):
        feed.fetch_prices(["EQNR.OL"], "2024-01-01", "2024-03-01")
```

- [ ] **Step 3: Run tests to verify they fail**

```
pytest tests/test_lseg_feed.py -v
```
Expected: `ModuleNotFoundError: No module named 'data.lseg'`

- [ ] **Step 4: Create `data/lseg.py`**

```python
"""LSEG Workspace API data feed for historical prices, fundamentals, and index constituents."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    import lseg.data as ld
except ImportError:
    ld = None  # type: ignore[assignment]

_LSEG_CACHE = Path(__file__).parent / "cache" / "lseg"
_LSEG_CACHE.mkdir(parents=True, exist_ok=True)

_FUNDAMENTAL_FIELDS = ["TR.PE", "TR.EPS", "TR.BookValuePerShare", "TR.CompanyMarketCap", "TR.DPS"]
_FUNDAMENTAL_FIELD_LABELS = ["P/E", "EPS", "BV/SH", "MKT_CAP", "DPS"]


class LSEGDataFeed:
    """Fetches market data from the LSEG Workspace API with local parquet caching.

    Requires the LSEG Workspace desktop application to be running.
    Falls back gracefully: raises RuntimeError with a clear message on session failure.
    """

    def __init__(self, use_cache: bool = True, cache_dir: Path | None = None) -> None:
        self.use_cache = use_cache
        self.cache_dir = Path(cache_dir) if cache_dir else _LSEG_CACHE
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_prices(
        self,
        tickers: list[str],
        start: str,
        end: str,
        frequency: str = "daily",
    ) -> pd.DataFrame:
        """Fetch OHLCV close prices for the given tickers.

        Args:
            tickers: LSEG RIC codes (e.g. ["EQNR.OL", "DNB.OL"]).
            start: Start date string (YYYY-MM-DD).
            end: End date string (YYYY-MM-DD).
            frequency: "daily", "weekly", or "monthly".

        Returns:
            DataFrame with UTC DatetimeIndex and one column per ticker (close price).

        Raises:
            RuntimeError: If the LSEG Workspace session is unavailable.
        """
        cache_key = "_".join(sorted(tickers)) + f"_{start}_{end}_{frequency}"
        cache_path = self.cache_dir / f"prices_{cache_key}.parquet"

        if self.use_cache and cache_path.exists():
            return pd.read_parquet(cache_path)

        if ld is None:
            raise RuntimeError(
                "LSEG Workspace API not installed. Run: pip install lseg-data"
            )

        try:
            raw = ld.get_history(
                universe=tickers,
                fields=["TRDPRC_1", "OFF_CLOSE"],
                interval=frequency,
                start=start,
                end=end,
            )
        except Exception as exc:
            raise RuntimeError(
                f"LSEG session error: {exc}. Ensure LSEG Workspace is running."
            ) from exc

        prices = self._normalise_price_df(raw, tickers)

        if self.use_cache:
            prices.to_parquet(cache_path)

        return prices

    def fetch_fundamentals(self, tickers: list[str]) -> dict[str, dict]:
        """Fetch key fundamental data for each ticker.

        Args:
            tickers: LSEG RIC codes.

        Returns:
            Nested dict: {ticker: {field: value}}.

        Raises:
            RuntimeError: If the LSEG Workspace session is unavailable.
        """
        if ld is None:
            raise RuntimeError(
                "LSEG Workspace API not installed. Run: pip install lseg-data"
            )

        try:
            df = ld.get_data(
                universe=tickers,
                fields=_FUNDAMENTAL_FIELDS,
            )
        except Exception as exc:
            raise RuntimeError(
                f"LSEG session error: {exc}. Ensure LSEG Workspace is running."
            ) from exc

        df.columns = _FUNDAMENTAL_FIELD_LABELS[: len(df.columns)]
        return {idx: row.to_dict() for idx, row in df.iterrows()}

    def fetch_index_constituents(self, index_ric: str) -> list[str]:
        """Fetch current constituent RICs for an index.

        Args:
            index_ric: LSEG index RIC (e.g. ".OSEBX").

        Returns:
            List of constituent RIC strings.

        Raises:
            RuntimeError: If the LSEG Workspace session is unavailable.
        """
        if ld is None:
            raise RuntimeError(
                "LSEG Workspace API not installed. Run: pip install lseg-data"
            )

        try:
            df = ld.get_data(
                universe=index_ric,
                fields=["TR.IndexConstituentRIC"],
            )
        except Exception as exc:
            raise RuntimeError(
                f"LSEG session error: {exc}. Ensure LSEG Workspace is running."
            ) from exc

        col = "TR.IndexConstituentRIC"
        if col not in df.columns:
            return []
        return df[col].dropna().tolist()

    @staticmethod
    def _normalise_price_df(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
        """Extract close prices, handling both TRDPRC_1 and OFF_CLOSE column names."""
        raw.index = pd.to_datetime(raw.index, utc=True)

        if set(tickers).issubset(set(raw.columns)):
            # ld.get_history returned a column per ticker directly
            prices = raw[tickers].copy()
        else:
            # Multi-level or single-ticker with field columns
            prices = pd.DataFrame(index=raw.index)
            for ticker in tickers:
                if ticker in raw.columns:
                    prices[ticker] = raw[ticker]
                elif "TRDPRC_1" in raw.columns:
                    prices[ticker] = raw["TRDPRC_1"]
                elif "OFF_CLOSE" in raw.columns:
                    prices[ticker] = raw["OFF_CLOSE"]

        return prices
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_lseg_feed.py -v
```
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add data/lseg.py tests/test_lseg_feed.py requirements.txt
git commit -m "feat: add LSEGDataFeed with caching and fallback error handling"
```

---

## Task 4: Evaluation — BacktestReport and Evaluator

**Files:**
- Create: `evaluation/__init__.py`
- Create: `evaluation/evaluator.py`
- Test: `tests/test_evaluator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_evaluator.py`:

```python
"""Tests for Evaluator — uses synthetic BacktestResult."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.metrics import BacktestResult
from evaluation.evaluator import BacktestReport, Evaluator


def _make_result(n: int = 252, seed: int = 42) -> BacktestResult:
    """Build a synthetic BacktestResult with a plausible NAV series."""
    rng = np.random.default_rng(seed)
    daily_rets = rng.normal(0.0003, 0.01, n)
    nav_values = 100_000.0 * np.cumprod(1 + daily_rets)
    idx = pd.date_range("2023-01-02", periods=n, freq="B", tz="UTC")
    nav = pd.Series(nav_values, index=idx, name="NAV")
    trades = pd.DataFrame(columns=["date", "ticker", "direction", "quantity", "fill_price", "commission"])
    return BacktestResult(nav=nav, trades=trades)


def test_evaluate_returns_backtest_report():
    result = _make_result()
    report = Evaluator().evaluate(result, strategy_name="test")
    assert isinstance(report, BacktestReport)


def test_report_has_expected_metrics():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert "sharpe" in report.metrics
    assert "cagr" in report.metrics
    assert "max_drawdown" in report.metrics
    assert "total_return" in report.metrics


def test_var_95_is_positive():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert report.var_95 > 0


def test_var_99_greater_than_var_95():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert report.var_99 > report.var_95


def test_cvar_greater_than_var():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert report.cvar_95 >= report.var_95


def test_drawdown_series_nonpositive():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert (report.drawdown_series <= 0).all()


def test_strategy_name_default():
    result = _make_result()
    report = Evaluator().evaluate(result)
    assert report.strategy_name == "strategy"


def test_correlation_matrix_with_prices():
    result = _make_result()
    rng = np.random.default_rng(1)
    idx = result.nav.index
    prices = pd.DataFrame(
        {"EQNR.OL": rng.uniform(80, 120, len(idx)), "DNB.OL": rng.uniform(50, 80, len(idx))},
        index=idx,
    )
    report = Evaluator().evaluate(result, prices=prices)
    assert report.correlation_matrix is not None
    assert report.correlation_matrix.shape == (2, 2)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_evaluator.py -v
```
Expected: `ModuleNotFoundError: No module named 'evaluation'`

- [ ] **Step 3: Create `evaluation/evaluator.py`**

```python
"""Evaluator: assembles a BacktestReport from a BacktestResult."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from backtesting.metrics import BacktestResult
from risk.drawdown import RecoveryPeriod, drawdown_series, recovery_periods
from risk.var import conditional_var, value_at_risk


@dataclass
class BacktestReport:
    result: BacktestResult
    metrics: dict[str, float]
    var_95: float
    var_99: float
    cvar_95: float
    drawdown_series: pd.Series
    recovery_periods: list[RecoveryPeriod]
    correlation_matrix: pd.DataFrame | None
    strategy_name: str = "strategy"


class Evaluator:
    """Computes risk-adjusted metrics from a BacktestResult."""

    def evaluate(
        self,
        result: BacktestResult,
        strategy_name: str = "strategy",
        benchmark: pd.Series | None = None,
        prices: pd.DataFrame | None = None,
    ) -> BacktestReport:
        """Build a BacktestReport with all metrics and risk statistics.

        Args:
            result: Completed backtest result.
            strategy_name: Human-readable strategy label used in the report.
            benchmark: Optional benchmark NAV series for alpha/beta calculation.
            prices: Optional multi-ticker price DataFrame for correlation matrix.

        Returns:
            BacktestReport with full metrics, VaR, CVaR, drawdown, and correlations.
        """
        returns = result.nav.pct_change().dropna()

        var_95 = value_at_risk(returns, confidence=0.95, method="historical")
        var_99 = value_at_risk(returns, confidence=0.99, method="historical")
        cvar_95 = conditional_var(returns, confidence=0.95)
        dd_series = drawdown_series(result.nav)
        rec_periods = recovery_periods(result.nav)

        corr: pd.DataFrame | None = None
        if prices is not None and len(prices.columns) > 1:
            corr = prices.pct_change().dropna().corr()

        return BacktestReport(
            result=result,
            metrics=result.metrics,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            drawdown_series=dd_series,
            recovery_periods=rec_periods,
            correlation_matrix=corr,
            strategy_name=strategy_name,
        )
```

- [ ] **Step 4: Create `evaluation/__init__.py`**

```python
from evaluation.evaluator import BacktestReport, Evaluator

__all__ = ["BacktestReport", "Evaluator"]
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_evaluator.py -v
```
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add evaluation/evaluator.py evaluation/__init__.py tests/test_evaluator.py
git commit -m "feat: add Evaluator and BacktestReport with VaR, CVaR, and drawdown metrics"
```

---

## Task 5: Markdown Reporter

**Files:**
- Create: `evaluation/reporter.py`
- Test: inline in `tests/test_evaluator.py` (extend existing file)

- [ ] **Step 1: Add reporter tests to `tests/test_evaluator.py`**

Append to the bottom of `tests/test_evaluator.py`:

```python
# ── Reporter tests ─────────────────────────────────────────────────────────

from evaluation.reporter import MarkdownReporter


def test_reporter_writes_report_md(tmp_path):
    result = _make_result()
    report = Evaluator().evaluate(result, strategy_name="momentum")
    reporter = MarkdownReporter()
    md_path = reporter.write(report, output_dir=tmp_path)
    assert md_path.exists()
    assert md_path.name == "report.md"


def test_report_contains_strategy_name(tmp_path):
    result = _make_result()
    report = Evaluator().evaluate(result, strategy_name="momentum")
    reporter = MarkdownReporter()
    md_path = reporter.write(report, output_dir=tmp_path)
    content = md_path.read_text()
    assert "momentum" in content


def test_report_contains_sharpe_section(tmp_path):
    result = _make_result()
    report = Evaluator().evaluate(result)
    reporter = MarkdownReporter()
    md_path = reporter.write(report, output_dir=tmp_path)
    content = md_path.read_text()
    assert "Sharpe" in content
    assert "VaR" in content


def test_report_saves_charts(tmp_path):
    result = _make_result()
    report = Evaluator().evaluate(result)
    reporter = MarkdownReporter()
    reporter.write(report, output_dir=tmp_path)
    assert (tmp_path / "nav_curve.png").exists()
    assert (tmp_path / "drawdown.png").exists()
    assert (tmp_path / "returns_dist.png").exists()
```

- [ ] **Step 2: Run new tests to verify they fail**

```
pytest tests/test_evaluator.py::test_reporter_writes_report_md -v
```
Expected: `ImportError: cannot import name 'MarkdownReporter' from 'evaluation.reporter'`

- [ ] **Step 3: Create `evaluation/reporter.py`**

```python
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
    """Simple DataFrame → Markdown table without requiring tabulate."""
    cols = list(df.columns)
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = []
    for _, row in df.iterrows():
        rows.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join([header, sep] + rows)
```

- [ ] **Step 4: Update `evaluation/__init__.py`**

```python
from evaluation.evaluator import BacktestReport, Evaluator
from evaluation.reporter import MarkdownReporter

__all__ = ["BacktestReport", "Evaluator", "MarkdownReporter"]
```

- [ ] **Step 5: Run all evaluator tests**

```
pytest tests/test_evaluator.py -v
```
Expected: 12 passed

- [ ] **Step 6: Commit**

```bash
git add evaluation/reporter.py evaluation/__init__.py tests/test_evaluator.py
git commit -m "feat: add MarkdownReporter with NAV, drawdown, and returns charts"
```

---

## Task 6: Pipeline

**Files:**
- Create: `pipeline/__init__.py`
- Create: `pipeline/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline.py`:

```python
"""End-to-end Pipeline tests using yfinance data source (mocked)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from pipeline.pipeline import Pipeline
from strategies.buy_and_hold import BuyAndHold


def _fake_prices(tickers: list[str], n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    idx = pd.date_range("2023-01-02", periods=n, freq="B", tz="UTC")
    return pd.DataFrame(
        {t: 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, n)) for t in tickers},
        index=idx,
    )


@patch("data.loader.yf.download")
def test_pipeline_run_returns_pipeline(mock_dl):
    prices = _fake_prices(["AAPL"])
    mock_dl.return_value = pd.DataFrame({"Close": prices["AAPL"]}, index=prices.index)
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
        initial_capital=10_000.0,
    )
    result = p.run()
    assert result is p  # chainable


@patch("data.loader.yf.download")
def test_pipeline_get_result(mock_dl):
    prices = _fake_prices(["AAPL"])
    mock_dl.return_value = pd.DataFrame({"Close": prices["AAPL"]}, index=prices.index)
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
        initial_capital=10_000.0,
    )
    p.run()
    from backtesting.metrics import BacktestResult
    assert isinstance(p.get_result(), BacktestResult)


@patch("data.loader.yf.download")
def test_pipeline_evaluate_returns_pipeline(mock_dl):
    prices = _fake_prices(["AAPL"])
    mock_dl.return_value = pd.DataFrame({"Close": prices["AAPL"]}, index=prices.index)
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
        initial_capital=10_000.0,
    )
    result = p.run().evaluate()
    assert result is p


@patch("data.loader.yf.download")
def test_pipeline_report_writes_files(mock_dl, tmp_path):
    prices = _fake_prices(["AAPL"])
    mock_dl.return_value = pd.DataFrame({"Close": prices["AAPL"]}, index=prices.index)
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
        initial_capital=10_000.0,
    )
    p.run().evaluate().report(output=tmp_path)
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "nav_curve.png").exists()


def test_pipeline_run_before_evaluate_raises():
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
    )
    with pytest.raises(RuntimeError, match="run\\(\\)"):
        p.evaluate()


def test_pipeline_evaluate_before_report_raises():
    p = Pipeline(
        strategy=BuyAndHold(),
        tickers=["AAPL"],
        start="2023-01-02",
        end="2023-04-01",
        data_source="yfinance",
    )
    with pytest.raises(RuntimeError, match="evaluate\\(\\)"):
        p.report()
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_pipeline.py -v
```
Expected: `ModuleNotFoundError: No module named 'pipeline'`

- [ ] **Step 3: Create `pipeline/pipeline.py`**

```python
"""Pipeline: the public API wiring data feed, backtest engine, and evaluation together."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from backtesting.engine import BacktestConfig, BacktestEngine
from backtesting.metrics import BacktestResult
from evaluation.evaluator import BacktestReport, Evaluator
from evaluation.reporter import MarkdownReporter
from strategies.base import Strategy


@dataclass
class _PipelineConfig:
    tickers: list[str]
    start: str
    end: str
    initial_capital: float = 1_000_000.0
    commission: float = 0.001
    slippage_bps: float = 5.0
    data_source: str = "yfinance"


class Pipeline:
    """Composable pipeline for strategy backtesting and evaluation.

    Usage::

        result = (
            Pipeline(
                strategy=MomentumStrategy(lookback=60, top_n=5),
                tickers=["EQNR.OL", "DNB.OL"],
                start="2018-01-01",
                end="2024-12-31",
                data_source="lseg",
                initial_capital=1_000_000,
            )
            .run()
            .evaluate()
            .report(output="reports/")
        )
    """

    def __init__(
        self,
        strategy: Strategy,
        tickers: list[str],
        start: str,
        end: str,
        data_source: str = "yfinance",
        initial_capital: float = 1_000_000.0,
        commission: float = 0.001,
        slippage_bps: float = 5.0,
    ) -> None:
        self.strategy = strategy
        self._cfg = _PipelineConfig(
            tickers=tickers,
            start=start,
            end=end,
            initial_capital=initial_capital,
            commission=commission,
            slippage_bps=slippage_bps,
            data_source=data_source,
        )
        self._result: BacktestResult | None = None
        self._report: BacktestReport | None = None
        self._prices: pd.DataFrame | None = None

    def run(self) -> "Pipeline":
        """Fetch data and run the backtest simulation. Returns self for chaining."""
        self._prices = self._fetch_prices()
        engine_cfg = BacktestConfig(
            start=self._cfg.start,
            end=self._cfg.end,
            initial_capital=self._cfg.initial_capital,
            commission=self._cfg.commission,
            slippage=self._cfg.slippage_bps / 10_000,
        )
        engine = BacktestEngine(engine_cfg)
        self._result = engine.run(self.strategy, self._prices)
        return self

    def evaluate(self, benchmark: pd.Series | None = None) -> "Pipeline":
        """Compute metrics and risk statistics. Call after run(). Returns self."""
        if self._result is None:
            raise RuntimeError("Call run() before evaluate()")
        evaluator = Evaluator()
        self._report = evaluator.evaluate(
            self._result,
            strategy_name=self.strategy.name,
            benchmark=benchmark,
            prices=self._prices,
        )
        return self

    def report(self, output: str | Path = "reports/") -> "Pipeline":
        """Write markdown report and chart images to output directory. Returns self."""
        if self._report is None:
            raise RuntimeError("Call evaluate() before report()")
        MarkdownReporter().write(self._report, output_dir=output)
        return self

    def get_result(self) -> BacktestResult:
        """Return the BacktestResult (available after run())."""
        if self._result is None:
            raise RuntimeError("Call run() first")
        return self._result

    def get_report(self) -> BacktestReport:
        """Return the BacktestReport (available after evaluate())."""
        if self._report is None:
            raise RuntimeError("Call evaluate() first")
        return self._report

    def _fetch_prices(self) -> pd.DataFrame:
        if self._cfg.data_source == "lseg":
            from data.lseg import LSEGDataFeed
            return LSEGDataFeed().fetch_prices(self._cfg.tickers, self._cfg.start, self._cfg.end)
        from data.loader import fetch_prices
        return fetch_prices(self._cfg.tickers, self._cfg.start, self._cfg.end)
```

- [ ] **Step 4: Create `pipeline/__init__.py`**

```python
from pipeline.pipeline import Pipeline

__all__ = ["Pipeline"]
```

- [ ] **Step 5: Run pipeline tests**

```
pytest tests/test_pipeline.py -v
```
Expected: 6 passed

- [ ] **Step 6: Run the full test suite**

```
pytest tests/ -v
```
Expected: all tests pass (existing + new)

- [ ] **Step 7: Commit**

```bash
git add pipeline/ tests/test_pipeline.py
git commit -m "feat: add Pipeline class — composable backtest, evaluate, report API"
```

---

## Task 7: CLI Script

**Files:**
- Create: `scripts/run_pipeline.py`

- [ ] **Step 1: Create `scripts/run_pipeline.py`**

```python
"""CLI entry point: run a strategy backtest end-to-end via Pipeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.pipeline import Pipeline
from strategies import BuyAndHold, EqualWeight, MomentumStrategy, MeanReversionStrategy

_STRATEGIES = {
    "buy_and_hold": lambda: BuyAndHold(),
    "equal_weight": lambda: EqualWeight(),
    "momentum": lambda: MomentumStrategy(),
    "mean_reversion": lambda: MeanReversionStrategy(),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a trading strategy backtest.")
    parser.add_argument("--strategy", choices=list(_STRATEGIES), default="buy_and_hold")
    parser.add_argument("--tickers", nargs="+", required=True, help="Ticker RICs, e.g. EQNR.OL DNB.OL")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--capital", type=float, default=1_000_000.0)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--data-source", choices=["yfinance", "lseg"], default="yfinance")
    parser.add_argument("--output", default="reports/", help="Directory for report output")
    args = parser.parse_args()

    strategy = _STRATEGIES[args.strategy]()

    print(f"Running {args.strategy} on {args.tickers} ({args.start} → {args.end}) ...")

    p = (
        Pipeline(
            strategy=strategy,
            tickers=args.tickers,
            start=args.start,
            end=args.end,
            data_source=args.data_source,
            initial_capital=args.capital,
            commission=args.commission,
            slippage_bps=args.slippage_bps,
        )
        .run()
        .evaluate()
        .report(output=args.output)
    )

    m = p.get_report().metrics
    print("\n── Results ───────────────────────────────")
    print(f"  Total Return:  {m.get('total_return', 0):.2%}")
    print(f"  CAGR:          {m.get('cagr', 0):.2%}")
    print(f"  Sharpe:        {m.get('sharpe', 0):.2f}")
    print(f"  Max Drawdown:  {m.get('max_drawdown', 0):.2%}")
    print(f"  Volatility:    {m.get('annualised_volatility', 0):.2%}")
    print(f"\nReport saved to: {args.output}/report.md")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Check that strategies __init__.py exports the needed classes**

Run:
```
python -c "from strategies import BuyAndHold, EqualWeight, MomentumStrategy, MeanReversionStrategy; print('OK')"
```

If this fails, open `strategies/__init__.py` and add the missing imports. The file should contain:

```python
from strategies.buy_and_hold import BuyAndHold
from strategies.equal_weight import EqualWeight
from strategies.momentum import MomentumStrategy
from strategies.mean_reversion import MeanReversionStrategy

__all__ = ["BuyAndHold", "EqualWeight", "MomentumStrategy", "MeanReversionStrategy"]
```

- [ ] **Step 3: Smoke-test the CLI with yfinance**

```
python scripts/run_pipeline.py --strategy buy_and_hold --tickers AAPL MSFT --start 2022-01-01 --end 2023-12-31 --output /tmp/test_report
```

Expected output (approximate):
```
Running buy_and_hold on ['AAPL', 'MSFT'] (2022-01-01 → 2023-12-31) ...

── Results ───────────────────────────────
  Total Return:  XX.XX%
  CAGR:          XX.XX%
  Sharpe:        X.XX
  Max Drawdown:  -XX.XX%
  Volatility:    XX.XX%

Report saved to: /tmp/test_report/report.md
```

- [ ] **Step 4: Run the full test suite one final time**

```
pytest tests/ -v
```
Expected: all tests pass

- [ ] **Step 5: Final commit**

```bash
git add scripts/run_pipeline.py strategies/__init__.py
git commit -m "feat: add run_pipeline.py CLI and wire strategies __init__ exports"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| LSEG DataFeed — OHLCV, fundamentals, constituents | Task 3 |
| LSEG caching to parquet | Task 3 |
| LSEG fallback RuntimeError | Task 3 |
| BacktestEngine.run() loop | Task 2 |
| Equal-weight position sizing | Task 2 |
| FillSimulator — slippage + commission | Task 1 |
| BacktestReport dataclass | Task 4 |
| Evaluator — VaR 95/99, CVaR, drawdown, metrics | Task 4 |
| MarkdownReporter — report.md + PNG charts | Task 5 |
| Pipeline — chainable .run().evaluate().report() | Task 6 |
| Pipeline — data_source="lseg" or "yfinance" | Task 6 |
| CLI script | Task 7 |
| Tests for all modules | Tasks 1–6 |

**Placeholder scan:** No TBDs, TODOs, or "similar to Task N" shortcuts found.

**Type consistency:** `Order`, `Fill`, `FillSimulator` defined in Task 1 and used identically in Task 2. `BacktestReport` defined in Task 4, used identically in Tasks 5 and 6. `Pipeline.run()` returns `self` (Pipeline) consistently.
