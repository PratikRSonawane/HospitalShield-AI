"""Power step (B3 step 4): demand build-up, supply, deficit/reserve, fuel burn.

All values in kW unless noted; energy in kWh (1 hour steps); fuel in litres.
Critical demand is never reduced; only explicitly shed non-critical load is.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import HospitalConfig


@dataclass(frozen=True)
class PowerOutcome:
    """Result of one hourly power step (kW unless noted; fuel in litres)."""

    critical_demand_kw: float
    noncritical_unshed_kw: float
    shed_kw: float
    demand_kw: float
    grid_supply_kw: float
    gen_available_kw: float
    gen_output_kw: float
    available_supply_kw: float
    deficit_kw: float
    reserve_kw: float
    critical_at_risk_kw: float
    fuel_l: float


def compute_power(
    cfg: HospitalConfig,
    hour: int,
    temperature_c: float,
    surge_open_total: int,
    requested_shed_kw: float,
    grid_fraction: float,
    gen_availability_fraction: float,
    fuel_l: float,
    fuel_resupply_l: float,
) -> PowerOutcome:
    """One hourly power step following B3 step 4 exactly.

    ``fuel_resupply_l`` is added before consumption (delivery at this hour);
    returned ``fuel_l`` is the stock after this hour's generator burn.
    """
    cooling_kw = cfg.power.cooling_base_kw + cfg.power.cooling_kw_per_deg_c_above * max(
        0.0, temperature_c - cfg.power.cooling_threshold_c)
    critical_cooling = cooling_kw * cfg.power.cooling_critical_fraction
    noncritical_cooling = cooling_kw * (1.0 - cfg.power.cooling_critical_fraction)

    critical_demand = cfg.power.critical_load_kw + critical_cooling + surge_open_total * cfg.power.surge_bed_kw
    noncritical_unshed = cfg.power.noncritical_load_kw * cfg.power.noncritical_diurnal_profile[hour % 24] + noncritical_cooling

    shed_cap = cfg.power.max_shed_fraction_of_noncritical * noncritical_unshed
    shed = min(max(0.0, requested_shed_kw), shed_cap, noncritical_unshed)

    demand = critical_demand + noncritical_unshed - shed
    grid_supply = cfg.power.grid_capacity_kw * grid_fraction

    fuel = max(0.0, fuel_l + max(0.0, fuel_resupply_l))
    gen_available = min(cfg.power.generator_capacity_kw * gen_availability_fraction,
                        fuel / cfg.power.fuel_l_per_kwh if cfg.power.fuel_l_per_kwh > 0 else 0.0)
    available_supply = grid_supply + gen_available

    deficit = max(0.0, demand - available_supply)
    reserve = max(0.0, available_supply - demand)
    critical_at_risk = max(0.0, critical_demand - available_supply)

    gen_output = min(gen_available, max(0.0, demand - grid_supply))
    fuel_after = max(0.0, fuel - gen_output * cfg.power.fuel_l_per_kwh)

    return PowerOutcome(
        critical_demand_kw=round(critical_demand, 4),
        noncritical_unshed_kw=round(noncritical_unshed, 4),
        shed_kw=round(shed, 4),
        demand_kw=round(demand, 4),
        grid_supply_kw=round(grid_supply, 4),
        gen_available_kw=round(gen_available, 4),
        gen_output_kw=round(gen_output, 4),
        available_supply_kw=round(available_supply, 4),
        deficit_kw=round(deficit, 4),
        reserve_kw=round(reserve, 4),
        critical_at_risk_kw=round(critical_at_risk, 4),
        fuel_l=round(fuel_after, 4),
    )
