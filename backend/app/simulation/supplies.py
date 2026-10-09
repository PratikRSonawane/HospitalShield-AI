"""Supplies step (B3 step 6): consumption, deliveries, stock, cover hours.

Stock is in supply units (litres-equivalent for oxygen, doses for meds).
Consumption is tied to weighted occupied beds. When stock plus deliveries
cannot cover demand, served consumption is capped at availability and the
shortfall is reported as ``unmet`` — stock never goes negative and the
stock identity (stock_change = delivered - served) holds exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import HospitalConfig


@dataclass(frozen=True)
class SupplyOutcome:
    """Per-item supply state for one hour."""

    stock: dict[str, float]
    consumption: dict[str, float]
    delivered: dict[str, float]
    unmet: dict[str, float]
    cover_hours: dict[str, float | None]
    stockout: dict[str, bool] = field(default_factory=dict)


def scheduled_delivery_rate(cfg: HospitalConfig, item: str, weighted_occupied_baseline: float) -> float:
    """Scheduled delivery per hour (units/hour) matching baseline demand.

    ``scheduled_resupply_fraction`` scales this baseline-matched rate; a
    fraction of 1.0 keeps cover constant in steady state.
    """
    rate = cfg.supplies.units_per_weighted_bed_hour.get(item, 0.0) * weighted_occupied_baseline
    return rate * cfg.supplies.scheduled_resupply_fraction


def compute_supplies(
    cfg: HospitalConfig,
    stock: dict[str, float],
    weighted_occupied_prev: float,
    delivery_fraction: float,
    emergency_arriving: dict[str, float],
) -> SupplyOutcome:
    """One hourly supplies step following B3 step 6.

    ``weighted_occupied_prev`` is the previous hour's weighted occupied beds;
    ``emergency_arriving`` holds emergency resupply units landing this hour.
    """
    new_stock: dict[str, float] = {}
    consumption: dict[str, float] = {}
    delivered: dict[str, float] = {}
    unmet: dict[str, float] = {}
    cover: dict[str, float | None] = {}
    stockout: dict[str, bool] = {}
    for item in cfg.supplies.items:
        rate = cfg.supplies.units_per_weighted_bed_hour.get(item, 0.0)
        cons = weighted_occupied_prev * rate
        sched = scheduled_delivery_rate(cfg, item, weighted_occupied_prev)
        deliv = sched * delivery_fraction + max(0.0, emergency_arriving.get(item, 0.0))
        available = stock.get(item, 0.0) + deliv
        served = min(cons, available)
        remaining = available - served
        shortfall = cons - served
        new_stock[item] = remaining
        consumed = served
        consumption[item] = consumed
        delivered[item] = deliv
        unmet[item] = shortfall
        cover[item] = (remaining / cons) if cons > 0 else None
        # B3/R11: stockout when stock reaches 0 while consumption > 0
        stockout[item] = bool(remaining <= 0 and cons > 0)
    return SupplyOutcome(stock=new_stock, consumption=consumption, delivered=delivered,
                         unmet=unmet, cover_hours=cover, stockout=stockout)
