"""Random-signal control strategies — the null hypothesis made concrete.

A random strategy has no information about the future. Any framework that reports
edge for these is broken; a mass-testing lab should always include a few so the
multiple-testing controls can be seen to reject them.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy


class RandomSignal(Strategy):
    """Every ``hold`` bars, flip a coin per ticker: long with probability ``p_long``, else flat."""

    name = "random"

    def __init__(self, seed: int = 0, p_long: float = 0.5, hold: int = 5) -> None:
        self.seed, self.p_long, self.hold = seed, p_long, hold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        rng = np.random.default_rng(self.seed)
        n, k = data.shape
        n_blocks = int(np.ceil(n / max(self.hold, 1)))
        draws = rng.random((n_blocks, k)) < self.p_long
        state = np.repeat(draws, max(self.hold, 1), axis=0)[:n]
        out = np.where(state, 1, -1)
        return pd.DataFrame(out, index=data.index, columns=data.columns).astype(int)


RANDOM_FAMILIES = [RandomSignal]
