"""Pure simulation engine package (no IO, no globals, no clock)."""

from .config import HospitalConfig, load_hospital_config, parse_hospital_config
from .engine import run
from .errors import InfeasibleInterventionError, InvariantViolationError, Issue, SimulationValidationError
from .interventions import InterventionsSpec, parse_interventions, validate_feasible
from .result import MODEL_VERSION, SimulationResult
from .scenario import ScenarioSpec, default_scenario, parse_scenario

__all__ = [
    "HospitalConfig", "load_hospital_config", "parse_hospital_config",
    "InfeasibleInterventionError", "InvariantViolationError", "Issue", "SimulationValidationError",
    "InterventionsSpec", "parse_interventions", "validate_feasible",
    "ScenarioSpec", "default_scenario", "parse_scenario",
    "run", "MODEL_VERSION", "SimulationResult",
]
