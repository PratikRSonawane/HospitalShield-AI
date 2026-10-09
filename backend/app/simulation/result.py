"""SimulationResult container with provenance metadata (B1).

Every result carries model_version, input_hash, seed, assumptions,
provenance and limitations so no output can be mistaken for real-hospital
or validated data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

MODEL_VERSION = "1.0.0"

ASSUMPTIONS: tuple[str, ...] = (
    "All hospital parameters are SYNTHETIC starting points documented in docs/assumptions.md.",
    "Heat-to-demand multipliers, derates and access fractions are SCENARIO ASSUMPTIONS, never empirical relationships.",
    "The demo runs on the synthetic baseline; NHS England and MIMIC-IV are optional calibration references only.",
    "Deterministic mode uses carry-forward integer flows; stochastic mode uses seeded Poisson/Binomial sampling.",
)

LIMITATIONS: tuple[str, ...] = (
    "Planning prototype only: NOT a clinical, engineering-safety or live-operations system.",
    "No claim of clinical validity or predictive accuracy; outputs support planning exploration.",
    "Power is an abstract operational constraint; no claim about real generator, ICU or life-support safety.",
    "No personal health information is used or produced.",
)


def canonical_json(data: object) -> str:
    """Deterministic JSON serialization (sorted keys, compact separators)."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def input_hash_for(scenario_dict: object) -> str:
    """SHA-256 hex digest of the canonical scenario input JSON."""
    return hashlib.sha256(canonical_json(scenario_dict).encode("utf-8")).hexdigest()


def run_id_for(scenario_dict: object) -> str:
    """run_id = first 16 hex chars of sha256(canonical input JSON + model_version)."""
    digest = hashlib.sha256((canonical_json(scenario_dict) + MODEL_VERSION).encode("utf-8")).hexdigest()
    return digest[:16]


@dataclass(frozen=True)
class SimulationResult:
    """Complete output of one engine run (all numbers CALCULATED)."""

    scenario: dict[str, Any]
    series: list[dict[str, Any]]
    summary: dict[str, Any]
    alerts: list[dict[str, Any]]
    failure_points: list[dict[str, Any]]
    seed: int
    stochastic: bool
    input_hash: str
    run_id: str
    assumptions: tuple[str, ...] = field(default=ASSUMPTIONS)
    limitations: tuple[str, ...] = field(default=LIMITATIONS)
    provenance: dict[str, Any] = field(default_factory=lambda: {
        "hospital_data": "SYNTHETIC",
        "weather": "SYNTHETIC_PROFILE",
        "outputs": "CALCULATED",
        "model_version": MODEL_VERSION,
        "warnings": [],
    })
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready result including provenance envelope."""
        return {
            "run_id": self.run_id,
            "model_version": self.model_version,
            "input_hash": self.input_hash,
            "seed": self.seed,
            "stochastic": self.stochastic,
            "scenario": self.scenario,
            "assumptions": list(self.assumptions),
            "provenance": self.provenance,
            "limitations": list(self.limitations),
            "summary": self.summary,
            "series": self.series,
            "alerts": self.alerts,
            "failure_points": self.failure_points,
        }
