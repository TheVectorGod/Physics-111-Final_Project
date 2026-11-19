"""RampForce v2 physics engine, ported from the user's Arduino C++ source.
 
Only Python standard library required. Calculations are theoretical; the software
is not a force sensor, workplace safety device, or structural ramp verifier.
"""
from __future__ import annotations
 
from dataclasses import dataclass
import math

# IMPORT GUIDE (kept from the patched source):
# `dataclass` generates the Inputs/PlanningLimits/RampResult/Analysis constructors.
# `math` supplies trigonometry, square roots, finite-number checks, and degree conversion.
# `__future__.annotations` permits references to types defined later in the file.
 
G = 9.81
GRID_POINTS = 101
RATIOS = (5, 8, 10, 12, 16, 20)
EPS = 1e-9
 
 
@dataclass(frozen=True)
class Inputs:
    mode: str = "SLIDING"
    load_kg: float = 30.0
    carrier_kg: float = 5.0
    height_m: float = 0.60
    max_run_m: float = 3.00
    mu_k: float = 0.30
    mu_s: float = 0.40
    wheel_radius_cm: float = 10.0
    roll_arm_mm: float = 2.0
 
    @property
    def total_mass_kg(self) -> float:
       return self.load_kg + self.carrier_kg
 
    @property
    def c_rr(self) -> float:
        return (self.roll_arm_mm / 1000.0) / (self.wheel_radius_cm / 100.0)
 
    @property
    def kinetic_coefficient(self) -> float:
       return self.mu_k if self.mode == "SLIDING" else self.c_rr
 
    @property
    def start_coefficient(self) -> float:
        return self.mu_s if self.mode == "SLIDING" else self.c_rr
 
 
@dataclass(frozen=True)
class PlanningLimits:
    max_peak_n: float = 222.0
    max_angle_deg: float = 20.0
    acceleration_mps2: float = 0.20
 
 
@dataclass(frozen=True)
class RampResult:
    run_m: float
    length_m: float
    angle_deg: float
    normal_n: float
    gravity_n: float
    resistance_n: float
    steady_n: float
    breakaway_n: float | None
    inertial_n: float
    peak_n: float
    work_j: float
    efficiency: float
    ideal_mechanical_advantage: float
    actual_mechanical_advantage: float
    holding_force_n: float | None
    holding_at_rest: bool | None
    space_ok: bool
    angle_ok: bool
    force_ok: bool
 
    @property
    def feasible(self) -> bool:
        # === MEMBER 2 — RampResult.feasible ===
        # GOAL: True only if space_ok, angle_ok and force_ok are all true.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Member 2: implement RampResult.feasible")
 
    @property
    def status(self) -> str:
        # === MEMBER 2 — RampResult.status ===
        # GOAL: Return the existing machine-readable FEASIBLE / FAIL: SPACE, ANGLE, FORCE status.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Member 2: implement RampResult.status")
 
    @property
    def plain_status(self) -> str:
        # === MEMBER 2 — RampResult.plain_status ===
        # GOAL: Return the existing friendly wording for failed conditions.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Member 2: implement RampResult.plain_status")
 
 
@dataclass(frozen=True)
class Analysis:
    feasible: bool
    reason: str
    x_angle_m: float
    x_required_m: float | None
    theta_force_deg: float
    theta_allowed_deg: float
    limiting_constraint: str
    at_max: RampResult
    at_min: RampResult | None
 
 
def _in_range(value: float, minimum: float, maximum: float, name: str, exclusive_min: bool = False) -> None:
    if not math.isfinite(value) or (value <= minimum if exclusive_min else value < minimum) or value > maximum:
           op = "greater than" if exclusive_min else "between"
           allowed = f"{op} {minimum} and at most {maximum}" if exclusive_min else f"{minimum} and {maximum}"
           raise ValueError(f"{name} must be {allowed}.")
 
 
def field_errors(inputs: Inputs, limits: PlanningLimits) -> dict[str, str]:
    """Every invalid value as {field_key: message}.  An empty dict means the inputs are valid.
 
    Keys match the entry boxes in main.py ("load", "carrier", "height", "max_run", "mu_k",
    "mu_s", "radius", "arm", "fmax", "angle", "accel"), so each message can be shown
    next to its own box.  Check order is unchanged, so the FIRST message equals the one
    the old validate() raised.
    """
    errors: dict[str, str] = {}
 
    def check(key: str, value: float, minimum: float, maximum: float, name: str,
              exclusive_min: bool = False) -> None:
        try:
            _in_range(value, minimum, maximum, name, exclusive_min)
        except ValueError as exc:
            errors[key] = str(exc)
 
    if inputs.mode not in ("SLIDING", "WHEELED"):
        errors["mode"] = "Transport mode must be Sliding or Wheeled."
    check("load", inputs.load_kg, 0, 500, "Cargo mass (kg)", True)
    check("carrier", inputs.carrier_kg, 0, 200, "Sled/cart mass (kg)")
    check("height", inputs.height_m, 0, 10, "Platform height (m)", True)
    check("max_run", inputs.max_run_m, 0.1, 100, "Maximum horizontal run (m)")
    if inputs.mode == "SLIDING":
        check("mu_k", inputs.mu_k, 0.01, 1.0, "Kinetic friction coefficient")
        check("mu_s", inputs.mu_s, inputs.mu_k if "mu_k" not in errors else 0.01, 1.0,
              "Static friction coefficient")
    else:
        check("radius", inputs.wheel_radius_cm, 2, 50, "Wheel radius (cm)")
        check("arm", inputs.roll_arm_mm, 0.1, 20, "Rolling-resistance arm (mm)")
        if "radius" not in errors and "arm" not in errors and inputs.c_rr > 0.30 + EPS:
            errors["arm"] = "Calculated rolling coefficient b/r must be no more than 0.30."
    check("fmax", limits.max_peak_n, 0, 5000, "Peak-force planning limit (N)", True)
    check("angle", limits.max_angle_deg, 1, 45, "Maximum angle (degrees)")
    check("accel", limits.acceleration_mps2, 0, 2, "Assumed acceleration (m/s²)")
    return errors
 
 
def validate(inputs: Inputs, limits: PlanningLimits) -> None:
    """Raise ValueError with the first problem found (kept for backwards compatibility)."""
    errors = field_errors(inputs, limits)
    if errors:
        raise ValueError(next(iter(errors.values())))
 
 
def calculate_at_run(inputs: Inputs, limits: PlanningLimits, run_m: float) -> RampResult:
    # === MEMBER 2 — calculate_at_run ===
    # GOAL: Construct RampResult for one given run; preserve geometry, steady/peak forces, work, and holding semantics.
    # Keep function name/parameters/return contract unchanged.
    raise NotImplementedError("Member 2: implement calculate_at_run")
 
 
def theta_for_force(total_mass_kg: float, coefficient: float, added_force_n: float, force_limit_n: float) -> float:
    # === MEMBER 3 — theta_for_force ===
    # GOAL: Solve the stated theoretical force inequality for its upper allowable angle in radians.
    # Keep function name/parameters/return contract unchanged.
    raise NotImplementedError("Member 3: implement theta_for_force")
 
 
def analyze(inputs: Inputs, limits: PlanningLimits) -> Analysis:
    # === MEMBER 3 — analyze ===
    # GOAL: Calculate allowed angle, minimum required run, feasibility, at_max and at_min; return Analysis.
    # Keep function name/parameters/return contract unchanged.
    raise NotImplementedError("Member 3: implement analyze")
 
 
def sweep(inputs: Inputs, limits: PlanningLimits, points: int = GRID_POINTS) -> list[RampResult]:
    # === MEMBER 4 — sweep ===
    # GOAL: Reproduce the existing 101-point angle-cap-to-xmax comparison list; preserve old CSV behavior for now.
    # Keep function name/parameters/return contract unchanged.
    raise NotImplementedError("Member 4: implement sweep")
 
 
def reference_slopes(inputs: Inputs, limits: PlanningLimits) -> list[tuple[str, RampResult]]:
    # === MEMBER 4 — reference_slopes ===
    # GOAL: Evaluate the existing standard 1:N slope list from RATIOS.
    # Keep function name/parameters/return contract unchanged.
    raise NotImplementedError("Member 4: implement reference_slopes")
 
 
def force_derivative(inputs: Inputs, run_m: float) -> float:
    # === MEMBER 3 — force_derivative ===
    # GOAL: Compute dFsteady/dx analytically for a specified run.
    # Keep function name/parameters/return contract unchanged.
    raise NotImplementedError("Member 3: implement force_derivative")
 
 
def work_derivative(inputs: Inputs) -> float:
    # === MEMBER 3 — work_derivative ===
    # GOAL: Compute dW/dx analytically for the current transport coefficient.
    # Keep function name/parameters/return contract unchanged.
    raise NotImplementedError("Member 3: implement work_derivative")
 
 
def parse_run(text: str, height_m: float) -> float:
    """Read a run typed as metres ("2.5", "2,5") or as a slope ("1:12" -> 12 x height)."""
    cleaned = text.strip().replace(",", ".")
    try:
        if ":" in cleaned:
            left, right = cleaned.split(":", 1)
            if float(left) != 1.0 or float(right) <= 0:
                raise ValueError
            run = float(right) * height_m
        else:
            run = float(cleaned)
    except ValueError:
        raise ValueError("Enter a run in metres (for example 2.5) or a slope such as 1:12.") from None
    if not math.isfinite(run) or not 0 < run <= 200:
        raise ValueError("The run must be greater than 0 and at most 200 m.")
    return run
 
 
def what_if_sweep(inputs: Inputs, limits: PlanningLimits, points: int = 60) -> list[RampResult]:
    # === MEMBER 4 — what_if_sweep ===
    # GOAL: Return diagnostic curve points even when the angle-cap run exceeds available space.
    # Keep function name/parameters/return contract unchanged.
    raise NotImplementedError("Member 4: implement what_if_sweep")
 
 
def release_note(inputs: Inputs, result: RampResult) -> str:
    # === MEMBER 2 — release_note ===
    # GOAL: Give the existing cautionary release wording; do NOT infer wheeled braking/holding from Crr.
    # Keep function name/parameters/return contract unchanged.
    raise NotImplementedError("Member 2: implement release_note")
 