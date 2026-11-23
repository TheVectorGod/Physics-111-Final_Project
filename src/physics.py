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
        return self.space_ok and self.angle_ok and self.force_ok
     
    @property
    def status(self) -> str:      
        if self.feasible:
        return "FEASIBLE"

        if not self.space_ok:
            return "FAIL: SPACE"

        if not self.angle_ok:
            return "FAIL: ANGLE"

        if not self.force_ok:
            return "FAIL: FORCE"

        return "FEASIBLE"
    
 
    @property
    def plain_status(self) -> str:        
        if self.feasible:
        return "This ramp meets all planning limits."

    messages = []

    if not self.space_ok:
        messages.append("The ramp needs more floor space.")

    if not self.angle_ok:
        messages.append("The ramp is too steep.")

    if not self.force_ok:
        messages.append("The required pushing force is too high.")

    return " ".join(messages)
 
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
    mass = inputs.total_mass_kg
    height = inputs.height_m

    # Calculate ramp geometry
    length = math.hypot(run_m, height)
    angle = math.atan2(height, run_m)
    angle_deg = math.degrees(angle)

    # Calculate forces
    weight = mass * G
    normal = weight * math.cos(angle)
    gravity = weight * math.sin(angle)

    # Calculate resistance and steady force
    coefficient = inputs.kinetic_coefficient
    resistance = coefficient * normal
    steady = gravity + resistance

    # Additional force needed for acceleration
    inertial = mass * limits.acceleration_mps2

    # Calculate breakaway and holding values
    if inputs.mode == "SLIDING":
        breakaway = weight * (
            math.sin(angle) + inputs.mu_s * math.cos(angle)
        )

        holding_force = max(
            0.0,
            gravity - inputs.mu_s * normal
        )

        holding_at_rest = gravity <= inputs.mu_s * normal + EPS

        peak = max(breakaway, steady + inertial)

    else:
        breakaway = None
        holding_force = None
        holding_at_rest = None

        peak = steady + inertial

    # Calculate work and efficiency
    work = steady * length
    useful_work = weight * height

    efficiency = (
        useful_work / work if work > EPS else 0.0
    )

    # Calculate mechanical advantage
    ideal_ma = length / height if height > EPS else 0.0

    actual_ma = (
        weight / steady if steady > EPS else 0.0
    )

    # Check planning limits
    space_ok = run_m <= inputs.max_run_m + EPS

    angle_ok = angle_deg <= limits.max_angle_deg + EPS

    force_ok = peak <= limits.max_peak_n + EPS

    # Return all calculated results
    return RampResult(
        run_m=run_m,
        length_m=length,
        angle_deg=angle_deg,
        normal_n=normal,
        gravity_n=gravity,
        resistance_n=resistance,
        steady_n=steady,
        breakaway_n=breakaway,
        inertial_n=inertial,
        peak_n=peak,
        work_j=work,
        efficiency=efficiency,
        ideal_mechanical_advantage=ideal_ma,
        actual_mechanical_advantage=actual_ma,
        holding_force_n=holding_force,
        holding_at_rest=holding_at_rest,
        space_ok=space_ok,
        angle_ok=angle_ok,
        force_ok=force_ok,
    )
 
 
def theta_for_force(total_mass_kg: float, coefficient: float, added_force_n: float, force_limit_n: float) -> float:
    weight = total_mass_kg * G
    if weight <= 0:
        return math.pi / 2
    available = force_limit_n - added_force_n
    if available <= 0:
        return 0.0                      # the added force alone already exceeds the limit
    phase = math.atan(coefficient)
    ratio = available / (weight * math.sqrt(1.0 + coefficient * coefficient))
    if ratio >= 1.0:
        return math.pi / 2 - phase      # the limit can never be reached on any slope
    return max(0.0, math.asin(ratio) - phase)   # 0.0 means even a flat start is too hard
 
 
def analyze(inputs: Inputs, limits: PlanningLimits) -> Analysis:
    m = inputs.total_mass_kg
    h = inputs.height_m

    theta_force = theta_for_force(m, inputs.kinetic_coefficient, m * limits.acceleration_mps2,
                                  limits.max_peak_n)
    if inputs.mode == "SLIDING":
        theta_force = min(theta_force,
                          theta_for_force(m, inputs.start_coefficient, 0.0, limits.max_peak_n))
    theta_angle = math.radians(limits.max_angle_deg)
    theta_allowed = min(theta_force, theta_angle)
    limiting = "FORCE" if theta_force < theta_angle else "ANGLE"

    x_angle = h / math.tan(theta_angle)
    x_required = h / math.tan(theta_allowed) if theta_allowed > EPS else None
    feasible = x_required is not None and x_required <= inputs.max_run_m + EPS

    at_max = calculate_at_run(inputs, limits, inputs.max_run_m)
    at_min = calculate_at_run(inputs, limits, min(x_required, inputs.max_run_m)) if feasible else None

    if feasible:
        reason = (f"FEASIBLE: any run from {x_required:.3f} m to {inputs.max_run_m:.3f} m "
                  f"meets the angle and force limits")
    elif x_required is None:
        reason = "FAIL: FORCE - even a nearly flat ramp needs more than the peak-force limit"
    else:
        reason = (f"FAIL: SPACE - needs a run of {x_required:.3f} m ({limiting.lower()} limit) "
                  f"but only {inputs.max_run_m:.3f} m is available")
    return Analysis(feasible, reason, x_angle, x_required, math.degrees(theta_force),
                    math.degrees(theta_allowed), limiting, at_max, at_min)
 
 
def sweep(inputs: Inputs, limits: PlanningLimits, points: int = GRID_POINTS) -> list[RampResult]:
    validate(inputs, limits)
    if points < 2:
        raise ValueError("Sweep requires at least 2 points.")
    x_angle = inputs.height_m / math.tan(math.radians(limits.max_angle_deg))
    if x_angle > inputs.max_run_m + EPS:
        return []
    start = min(x_angle, inputs.max_run_m)
    stop = inputs.max_run_m
    step = (stop - start) / (points - 1)
    return [calculate_at_run(inputs, limits, start + i * step) for i in range(points)]
 
def reference_slopes(inputs: Inputs, limits: PlanningLimits) -> list[tuple[str, RampResult]]:
    validate(inputs, limits)
    return [(f"1:{ratio}", calculate_at_run(inputs, limits, ratio * inputs.height_m)) for ratio in RATIOS]
 
def force_derivative(inputs: Inputs, run_m: float) -> float:
    m, h, k = inputs.total_mass_kg, inputs.height_m, inputs.kinetic_coefficient
    return m * G * h * (k * h - run_m) / (h * h + run_m * run_m) ** 1.5
 
 
def work_derivative(inputs: Inputs) -> float:
    return inputs.total_mass_kg * G * inputs.kinetic_coefficient
 
 
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
    validate(inputs, limits)
    if points < 2:
        raise ValueError("What-if sweep requires at least 2 points.")
    x_angle = inputs.height_m / math.tan(math.radians(limits.max_angle_deg))
    start = min(inputs.max_run_m, x_angle)
    stop = max(inputs.max_run_m, x_angle * 1.15)
    if stop <= start + EPS:
        stop = start * 1.5
    step = (stop - start) / (points - 1)
    return [calculate_at_run(inputs, limits, start + i * step) for i in range(points)]
 
 
def release_note(inputs: Inputs, result: RampResult) -> str:  
    if inputs.mode == "WHEELED":
        return (
            "CAUTION: This is a theoretical rolling-resistance estimate. "
            "It does not predict stationary wheel holding or braking. "
            "A released cart may roll backward, so keep it secured "
            "and use appropriate brakes or restraints."
        )

    if result.holding_at_rest:
        return (
            "CAUTION: The model estimates that static friction can hold "
            "the load at rest on this ramp. This is a theoretical estimate, "
            "not a guarantee of safety. Keep the load secured."
        )

    return (
        "CAUTION: The model estimates that static friction alone may not "
        "hold the load at rest on this ramp. Use an appropriate restraint "
        "and do not release the load unsecured."
    )

 
