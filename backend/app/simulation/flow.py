"""Integer flow helpers: deterministic carry-forward rounding and seeded
stochastic samplers.

Deterministic mode converts an expected fractional rate into integers with
a carry-forward accumulator (no randomness, no drift). Stochastic mode
samples from Poisson/Binomial using a local ``numpy.random.Generator``
(PCG64) created by the caller; the engine never touches a global RNG.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class CarryForward:
    """Accumulates fractional expected counts and emits integers.

    The residual carry is bounded to [0, 1) after each draw so rounding
    error cannot accumulate without limit.
    """

    carry: float = 0.0

    def draw(self, expected: float) -> int:
        """Return the integer count for this hour given ``expected`` (count)."""
        if expected <= 0.0:
            self.carry = min(max(self.carry, 0.0), 0.999)
            return 0
        total = self.carry + expected
        take = int(math.floor(total))
        self.carry = total - take
        if self.carry >= 1.0:  # numeric safety; floor above already prevents this
            self.carry = 0.999
        return take


def split_cohorts(n: int, p_ward: float, p_icu: float, carry_ward: CarryForward,
                  carry_icu: CarryForward) -> tuple[int, int, int]:
    """Split ``n`` patients into (non_admit, ward_admit, icu_admit).

    Ward and ICU shares are drawn with separate carry-forward accumulators;
    non-admit is the remainder, so the split always sums to ``n``.
    """
    ward = carry_ward.draw(n * p_ward)
    icu = carry_icu.draw(n * p_icu)
    ward = min(ward, n)
    icu = min(icu, n - ward)
    return n - ward - icu, ward, icu


class StochasticFlows:
    """Seeded samplers for stochastic mode (Binomial/Poisson)."""

    def __init__(self, seed: int) -> None:
        self._rng = np.random.Generator(np.random.PCG64(seed))

    def arrivals(self, expected: float) -> int:
        """Poisson arrivals for one hour (patients)."""
        if expected <= 0.0:
            return 0
        return int(self._rng.poisson(expected))

    def completions(self, cohort: int, rate_per_hour: float) -> int:
        """Binomial completions: each patient completes with prob = rate (1/hour)."""
        if cohort <= 0:
            return 0
        p = min(max(rate_per_hour, 0.0), 1.0)
        return int(self._rng.binomial(cohort, p))

    def split_cohorts(self, n: int, p_ward: float, p_icu: float) -> tuple[int, int, int]:
        """Multinomial split of ``n`` into (non_admit, ward, icu)."""
        if n <= 0:
            return 0, 0, 0
        p_ward = min(max(p_ward, 0.0), 1.0)
        p_icu = min(max(p_icu, 0.0), 1.0)
        if p_ward + p_icu > 1.0:
            scale = 1.0 / (p_ward + p_icu)
            p_ward *= scale
            p_icu *= scale
        counts = self._rng.multinomial(n, [1.0 - p_ward - p_icu, p_ward, p_icu])
        return int(counts[0]), int(counts[1]), int(counts[2])
