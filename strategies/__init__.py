from .base import Strategy
from .buy_and_hold import BuyAndHold
from .calendar import CALENDAR_FAMILIES, DayOfWeek, SellInMay, TurnOfMonth
from .cross_sectional import (
    CROSS_SECTIONAL_FAMILIES,
    DualMomentum,
    High52Week,
    LowVolatility,
    RelativeStrength,
    TimeSeriesMomentum,
)
from .equal_weight import EqualWeight
from .mean_reversion import MeanReversion
from .momentum import Momentum
from .random_control import RANDOM_FAMILIES, RandomSignal
from .regime import REGIME_FAMILIES, BuyTheDip, GapReversal, StreakReversal, VolatilityRegime
from .technical import (
    TECHNICAL_FAMILIES,
    ATRBreakout,
    BollingerBreakout,
    BollingerReversion,
    DonchianBreakout,
    EMACross,
    KeltnerBreakout,
    MACDSignal,
    PriceVsSMA,
    ROCMomentum,
    RSIReversal,
    RSITrend,
    SMACross,
    Stochastic,
)
from .volume import VOLUME_FAMILIES, OBVTrend, VolumeBreakout, VolumeZReversal

# Every concrete strategy class, used by the registry and the algorithm library.
ALL_FAMILIES: list[type[Strategy]] = [
    BuyAndHold, EqualWeight, Momentum, MeanReversion,
    *TECHNICAL_FAMILIES, *VOLUME_FAMILIES, *CROSS_SECTIONAL_FAMILIES,
    *CALENDAR_FAMILIES, *REGIME_FAMILIES, *RANDOM_FAMILIES,
]

__all__ = [
    "Strategy", "ALL_FAMILIES",
    "BuyAndHold", "EqualWeight", "Momentum", "MeanReversion",
    "SMACross", "EMACross", "PriceVsSMA", "MACDSignal", "RSIReversal", "RSITrend",
    "BollingerReversion", "BollingerBreakout", "KeltnerBreakout", "Stochastic",
    "ROCMomentum", "DonchianBreakout", "ATRBreakout",
    "VolumeBreakout", "OBVTrend", "VolumeZReversal",
    "LowVolatility", "DualMomentum", "RelativeStrength", "High52Week", "TimeSeriesMomentum",
    "TurnOfMonth", "DayOfWeek", "SellInMay",
    "VolatilityRegime", "BuyTheDip", "StreakReversal", "GapReversal",
    "RandomSignal",
]
