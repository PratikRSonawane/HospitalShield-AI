"""Optimal action-sequence planner (B12): deterministic beam search over
the five interventions, evaluated with the real engine and the same
feasibility validator the API uses.

"Optimal" means best found within the stated budget (planning aid, never a
proof of optimality). Score = resilience_index - lambda * burden; both parts
are reported. Same input always yields the same plan.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Any

from app.simulation import HospitalConfig, InterventionsSpec, ScenarioSpec, run, validate_feasible
from app.simulation.interventions import EmergencyResupply, LoadShed, StaffMove, StaffRecall, SurgeActivation

BURDEN_PER_UNIT: dict[str, float] = {
    "activate_surge_beds": 0.3,   # per bed
    "reallocate_staff": 1.0,      # per nurse
    "reduce_noncritical_load_kw": 0.02,  # per kW
    "recall_staff": 2.0,          # per nurse (staff-fatigue cost)
    "emergency_resupply": 0.001,  # per litre / per supply unit
}

REFERENCE_RESERVE = 3  # simulations reserved for the reference plans
POOL_PER_KIND = 4      # top single actions per kind carried into beam expansion


@dataclass(frozen=True)
class PlannerBudget:
    max_simulations: int = 600
    max_seconds: float = 5.0
    max_actions: int = 5
    grid_hours: int = 3
    lambda_burden: float = 0.5
    epsilon: float = 0.1
    beam_width: int = 5


@dataclass(frozen=True)
class Candidate:
    kind: str
    detail: dict[str, Any]
    spec: InterventionsSpec

    @property
    def key(self) -> str:
        return f"{self.kind}:{sorted(self.detail.items())}"


@dataclass
class Partial:
    """A partial plan: ordered actions plus its merged spec and score."""

    actions: list[Candidate] = field(default_factory=list)
    spec: InterventionsSpec | None = None
    score: float = -1e9
    resilience: float = 0.0
    burden: float = 0.0
    result: Any = None


def plan_burden(cands: list[Candidate]) -> float:
    """Documented burden of a plan (sum of per-unit costs, B12)."""
    total = 0.0
    for c in cands:
        d = c.detail
        if c.kind == "activate_surge_beds":
            total += BURDEN_PER_UNIT[c.kind] * d.get("beds", 0)
        elif c.kind == "reallocate_staff":
            total += BURDEN_PER_UNIT[c.kind] * d.get("nurses", 0)
        elif c.kind == "reduce_noncritical_load_kw":
            total += BURDEN_PER_UNIT[c.kind] * d.get("kw", 0)
        elif c.kind == "recall_staff":
            total += BURDEN_PER_UNIT[c.kind] * d.get("nurses", 0)
        elif c.kind == "emergency_resupply":
            total += BURDEN_PER_UNIT[c.kind] * (d.get("fuel_l", 0) + sum(dict(d.get("items") or {}).values()))
    return round(total, 4)


def _merge_specs(parts: list[InterventionsSpec]) -> InterventionsSpec:
    return InterventionsSpec(
        activate_surge_beds=tuple(a for s in parts for a in s.activate_surge_beds),
        reallocate_staff=tuple(a for s in parts for a in s.reallocate_staff),
        reduce_noncritical_load=tuple(a for s in parts for a in s.reduce_noncritical_load),
        recall_staff=tuple(a for s in parts for a in s.recall_staff),
        emergency_resupply=tuple(a for s in parts for a in s.emergency_resupply),
    )


def enumerate_candidates(cfg: HospitalConfig, scenario: ScenarioSpec, grid_hours: int) -> list[Candidate]:
    """Deterministic candidate actions: five types at discrete sizes and
    start hours on the grid, plus scenario-critical hours (outage/access)."""
    t = scenario.duration_hours
    starts = list(range(0, t, max(1, grid_hours)))[:9]
    for extra in (scenario.outage.start_hour if scenario.outage else None,
                  scenario.access.start_hour if scenario.access else None):
        if extra is not None and extra not in starts:
            starts.append(extra)
    starts = sorted(h for h in starts if 0 <= h < t)

    cands: list[Candidate] = []
    for h in starts:
        for beds in (5, cfg.ward.surge_beds_available):
            n = min(beds, cfg.ward.surge_beds_available)
            cands.append(Candidate("activate_surge_beds",
                                   {"unit": "ward", "beds": n, "start_hour": h},
                                   InterventionsSpec(activate_surge_beds=(SurgeActivation("ward", n, h),))))
        for beds in (2, cfg.icu.surge_beds_available):
            n = min(beds, cfg.icu.surge_beds_available)
            cands.append(Candidate("activate_surge_beds",
                                   {"unit": "icu", "beds": n, "start_hour": h},
                                   InterventionsSpec(activate_surge_beds=(SurgeActivation("icu", n, h),))))
        for from_u, to_u in (("ed", "icu"), ("ward", "ed"), ("ward", "icu")):
            for nurses in (2,):
                cands.append(Candidate("reallocate_staff",
                                       {"from_unit": from_u, "to_unit": to_u, "nurses": nurses, "start_hour": h},
                                       InterventionsSpec(reallocate_staff=(StaffMove(from_u, to_u, nurses, h),))))
        for kw in (20, 40):
            cands.append(Candidate("reduce_noncritical_load_kw",
                                   {"kw": kw, "start_hour": h, "end_hour": t},
                                   InterventionsSpec(reduce_noncritical_load=(LoadShed(kw, h, t),))))
        for unit, cap_n in (("ed", int(cfg.recall.max_fraction_of_roster * cfg.ed.nurse_roster)),
                            ("ward", int(cfg.recall.max_fraction_of_roster * cfg.ward.nurse_roster)),
                            ("icu", int(cfg.recall.max_fraction_of_roster * cfg.icu.nurse_roster))):
            if cap_n >= 1:
                cands.append(Candidate("recall_staff",
                                       {"unit": unit, "nurses": cap_n, "start_hour": h},
                                       InterventionsSpec(recall_staff=(StaffRecall(unit, cap_n, h),))))
        fuel_cap = cfg.supplies.emergency_resupply_max_cover_hours * cfg.power.generator_capacity_kw * cfg.power.fuel_l_per_kwh
        for litres in (fuel_cap / 2, fuel_cap):
            cands.append(Candidate("emergency_resupply",
                                   {"fuel_l": round(litres, 1), "start_hour": h},
                                   InterventionsSpec(emergency_resupply=(EmergencyResupply(fuel_l=round(litres, 1), start_hour=h),))))
        for item in cfg.supplies.items:
            weighted = cfg.ward.initial_occupied + cfg.icu.initial_occupied * cfg.supplies.icu_weight \
                + int(cfg.arrivals.baseline_per_hour * cfg.ed.los_hours) * cfg.supplies.ed_weight
            item_cap = cfg.supplies.emergency_resupply_max_cover_hours * cfg.supplies.units_per_weighted_bed_hour.get(item, 0.0) * weighted
            cands.append(Candidate("emergency_resupply",
                                   {"items": {item: round(item_cap, 1)}, "start_hour": h},
                                   InterventionsSpec(emergency_resupply=(EmergencyResupply(items={item: round(item_cap, 1)}, start_hour=h),))))
    # dedupe, keep deterministic order
    seen: set[str] = set()
    unique: list[Candidate] = []
    for c in cands:
        if c.key not in seen:
            seen.add(c.key)
            unique.append(c)
    return unique


class _BudgetExhausted(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


def _search(cfg: HospitalConfig, scenario: ScenarioSpec, budget: PlannerBudget) -> tuple[Partial | None, list[Candidate], int, str, int]:
    """Beam search; returns (best, all_candidates, sims_used, stopped_reason, elapsed_ms).

    Phase 1 evaluates every single-action candidate; phase 2 beam-expands
    only the top pool. Budget exhaustion mid-round still yields the best
    partial found so far.
    """
    t0 = time.perf_counter()
    # reserve budget for reference plans (<=3) and the marginal-gain recompute
    # runs (<= max_actions) so total simulations stay within max_simulations
    sim_limit = max(4, budget.max_simulations - REFERENCE_RESERVE - budget.max_actions)
    state = {"sims": 0}

    def evaluate(spec: InterventionsSpec):
        if state["sims"] >= sim_limit:
            raise _BudgetExhausted("budget_simulations")
        if time.perf_counter() - t0 >= budget.max_seconds:
            raise _BudgetExhausted("budget_seconds")
        state["sims"] += 1
        return run(cfg, scenario, spec)

    def score_of(result: Any, burden: float) -> float:
        return result.summary["resilience_index"] - budget.lambda_burden * burden

    base = Partial(spec=InterventionsSpec())
    base.result = evaluate(InterventionsSpec())
    base.resilience = base.result.summary["resilience_index"]
    base.score = score_of(base.result, 0.0)
    best = base
    stopped = "no_feasible_actions"
    candidates = enumerate_candidates(cfg, scenario, budget.grid_hours)

    # Phase 1: every single action
    singles: list[tuple[float, str, Candidate, Any]] = []
    try:
        for cand in candidates:
            try:
                validate_feasible(cand.spec, cfg, scenario)
            except Exception:
                continue
            result = evaluate(cand.spec)
            singles.append((score_of(result, plan_burden([cand])), cand.key, cand, result))
    except _BudgetExhausted as exc:
        stopped = exc.reason
    singles.sort(key=lambda s: (-s[0], s[1]))
    if singles:
        top_score = singles[0][0]
        if top_score > best.score + budget.epsilon:
            first = singles[0]
            best = Partial(actions=[first[2]], spec=first[2].spec, score=first[0],
                           resilience=first[3].summary["resilience_index"],
                           burden=plan_burden([first[2]]), result=first[3])
            stopped = "improved"

    # Diverse pool: top few singles of each action kind, ordered by score.
    pool: list[Candidate] = []
    by_kind: dict[str, list[tuple[float, str, Candidate, Any]]] = {}
    for entry in singles:
        by_kind.setdefault(entry[2].kind, []).append(entry)
    for entries in by_kind.values():
        pool.extend(e[2] for e in entries[:POOL_PER_KIND])
    score_by_key = {s[2].key: s[0] for s in singles}
    pool.sort(key=lambda c: (-score_by_key[c.key], c.key))

    # Seed the beam with the top single-action partials (phase 1 already
    # evaluated them; expanding from base again would only duplicate).
    beam: list[Partial] = []
    for score, _key, cand, result in singles[:budget.beam_width]:
        beam.append(Partial(actions=[cand], spec=cand.spec, score=score,
                            resilience=result.summary["resilience_index"],
                            burden=plan_burden([cand]), result=result))

    if pool and not stopped.startswith("budget"):
        try:
            while True:
                expansions: list[tuple[float, str, Partial]] = []
                exhausted = False
                for partial in beam:
                    have = {a.key for a in partial.actions}
                    for cand in pool:
                        if cand.key in have or len(partial.actions) + 1 > budget.max_actions:
                            continue
                        merged = _merge_specs(list(filter(None, [partial.spec, cand.spec])))
                        try:
                            validate_feasible(merged, cfg, scenario)
                        except Exception:
                            continue
                        try:
                            result = evaluate(merged)
                        except _BudgetExhausted as exc:
                            stopped = exc.reason
                            exhausted = True
                            break
                        burden = plan_burden(partial.actions + [cand])
                        p = Partial(actions=partial.actions + [cand], spec=merged,
                                    score=score_of(result, burden),
                                    resilience=result.summary["resilience_index"],
                                    burden=burden, result=result)
                        expansions.append((p.score, p.actions[-1].key, p))
                    if exhausted:
                        break
                if expansions:
                    expansions.sort(key=lambda e: (-e[0], e[1]))
                    top_score, _, top_partial = expansions[0]
                    gain = top_score - best.score
                    if gain >= budget.epsilon:
                        best = top_partial
                        stopped = "improved"
                        beam = _dedupe_beam([e[2] for e in expansions[:budget.beam_width]])
                        continue
                    stopped = "marginal_gain"
                elif not exhausted:
                    stopped = stopped if stopped != "improved" else "complete"
                break
        except _BudgetExhausted as exc:
            stopped = exc.reason

    if best is base:
        stopped = "empty_plan" if stopped == "no_feasible_actions" else stopped
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return best, candidates, state["sims"], stopped, elapsed_ms


def _dedupe_beam(partials: list[Partial]) -> list[Partial]:
    """Keep the first occurrence of each action-set signature in beam order."""
    seen: set[str] = set()
    out: list[Partial] = []
    for p in partials:
        sig = "|".join(sorted(a.key for a in p.actions))
        if sig not in seen:
            seen.add(sig)
            out.append(p)
    return out


def _at_hour0(cand: Candidate) -> Candidate:
    detail = dict(cand.detail)
    detail["start_hour"] = 0
    spec_kwargs: dict[str, tuple] = {}
    for field_name in ("activate_surge_beds", "reallocate_staff", "reduce_noncritical_load",
                       "recall_staff", "emergency_resupply"):
        entries = getattr(cand.spec, field_name)
        if entries:
            spec_kwargs[field_name] = tuple(replace(e, start_hour=0) for e in entries)
    return Candidate(cand.kind, detail, InterventionsSpec(**spec_kwargs))


def plan(cfg: HospitalConfig, scenario: ScenarioSpec, budget: PlannerBudget | None = None) -> dict[str, Any]:
    """Build the optimal action sequence found within budget (B12).

    Returns action_plan[] ordered by start_hour with marginal gains, the
    three reference plans, search stats and failure points before/after.
    """
    budget = budget or PlannerBudget()
    best, _cands, sims_used, stopped, elapsed_ms = _search(cfg, scenario, budget)

    action_plan: list[dict[str, Any]] = []
    best_result = None
    if best is not None and best.result is not None:
        best_result = best.result
        ordered = sorted(best.actions, key=lambda a: (a.detail.get("start_hour", 0), a.kind, a.key))
        # marginal gain per step: recompute by adding actions one at a time
        cumulative: InterventionsSpec = InterventionsSpec()
        prev_score: float | None = None
        for cand in ordered:
            cumulative = _merge_specs([cumulative, cand.spec])
            r = run(cfg, scenario, cumulative)
            resilience = r.summary["resilience_index"]
            marginal = None if prev_score is None else round(resilience - prev_score, 2)
            prev_score = resilience
            detail = dict(cand.detail)
            if cand.kind == "activate_surge_beds":
                detail["effective_hour"] = detail.get("start_hour", 0) + cfg.surge.activation_delay_hours
            if cand.kind == "recall_staff":
                detail["effective_hour"] = detail.get("start_hour", 0) + cfg.recall.lead_time_hours
            if cand.kind == "emergency_resupply":
                detail["effective_hour"] = detail.get("start_hour", 0) + cfg.supplies.emergency_lead_time_hours
            action_plan.append({
                "action": cand.kind,
                "detail": detail,
                "start_hour": detail.get("start_hour", 0),
                "effective_hour": detail.get("effective_hour", detail.get("start_hour", 0)),
                "marginal_gain_resilience": marginal,
                "resilience_index": resilience,
                "reason": f"Targets {cand.kind.replace('_', ' ')}; chosen by deterministic beam search "
                          f"(score = resilience_index - {budget.lambda_burden} x burden).",
            })
        best_resilience = best_result.summary["resilience_index"]
    else:
        best_resilience = None

    baseline_run = run(cfg, scenario, None)
    no_action_score = baseline_run.summary["resilience_index"]

    references: list[dict[str, Any]] = [{
        "name": "no_action",
        "resilience_index": no_action_score,
        "actions": [],
    }]

    if best is not None and best.actions:
        hour0_spec = _merge_specs([_at_hour0(c).spec for c in best.actions])
        try:
            validate_feasible(hour0_spec, cfg, scenario)
            r0 = run(cfg, scenario, hour0_spec)
            references.append({"name": "everything_at_hour_0", "resilience_index": r0.summary["resilience_index"],
                               "actions": [c.kind for c in best.actions]})
        except Exception as exc:
            references.append({"name": "everything_at_hour_0", "resilience_index": None,
                               "actions": [c.kind for c in best.actions], "infeasible": str(exc)})
        reverse_spec = _merge_specs([c.spec for c in reversed(best.actions)])
        try:
            validate_feasible(reverse_spec, cfg, scenario)
            rr = run(cfg, scenario, reverse_spec)
            references.append({"name": "reverse_order", "resilience_index": rr.summary["resilience_index"],
                               "actions": [c.kind for c in reversed(best.actions)]})
        except Exception as exc:
            references.append({"name": "reverse_order", "resilience_index": None,
                               "actions": [c.kind for c in reversed(best.actions)], "infeasible": str(exc)})

    return {
        "label": "best found within budget",
        "action_plan": action_plan,
        "score": {"resilience_index": best_resilience, "burden": best.burden if best else 0.0,
                  "objective": (best_resilience - budget.lambda_burden * best.burden) if best else None},
        "references": references,
        "search_stats": {
            "simulations_used": sims_used + len(references) + len(action_plan),
            "max_simulations": budget.max_simulations,
            "seconds_ms": elapsed_ms,
            "max_seconds_ms": int(budget.max_seconds * 1000),
            "stopped_reason": stopped,
        },
        "failure_points_before": baseline_run.failure_points,
        "failure_points_after": (best_result.failure_points if best_result else baseline_run.failure_points),
        "objective_weights": {"lambda_burden": budget.lambda_burden, "burden_per_unit": BURDEN_PER_UNIT},
    }
