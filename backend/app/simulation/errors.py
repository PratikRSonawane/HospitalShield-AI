"""Structured errors raised by the pure simulation engine.

The engine never performs IO; these exceptions carry machine-readable
details that the API layer maps onto HTTP 4xx responses.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    """One machine-readable validation problem.

    ``field`` is a dotted path into the request payload,
    ``rule`` names the constraint that was violated.
    """

    field: str
    reason: str
    rule: str = "bound"

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "reason": self.reason, "rule": self.rule}


class SimulationValidationError(ValueError):
    """Invalid scenario input (bounds, cross-field rules)."""

    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{i.field}: {i.reason}" for i in issues))


class InfeasibleInterventionError(ValueError):
    """An intervention violates a feasibility rule (B6); never silently clamped."""

    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{i.field}: {i.reason}" for i in issues))


class InvariantViolationError(RuntimeError):
    """An internal invariant (B4) was violated; a bug, not bad input."""
