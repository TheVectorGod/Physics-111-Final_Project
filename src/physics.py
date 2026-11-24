"""RampForce v2 physics engine, ported from the user's Arduino C++ source.

Only Python standard library required. Calculations are theoretical; the software
is not a force sensor, workplace safety device, or structural ramp verifier.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

G = 9.81
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
        failures = []
        if not self.space_ok:
            failures.append("SPACE")
        if not self.angle_ok:
            failures.append("ANGLE")
        if not self.force_ok:
            failures.append("FORCE")
        return "FEASIBLE" if not failures else "FAIL: " + ", ".join(failures)

    @property
    def plain_status(self) -> str:
        """Everyday wording for screens (the coded `status` stays for CSV files)."""
        reasons = []
        if not self.space_ok:
            reasons.append("too long for your space")
        if not self.angle_ok:
            reasons.append("too steep")
        if not self.force_ok:
            reasons.append("too much force to get started")
        return "Feasible" if not reasons else ", ".join(reasons).capitalize()


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
    validate(inputs, limits)
    if not math.isfinite(run_m) or not 0 < run_m <= 200:
        raise ValueError("Candidate horizontal run must be greater than 0 and at most 200 m.")
    m, h = inputs.total_mass_kg, inputs.height_m
    length = math.hypot(h, run_m)
    sin_theta, cos_theta = h / length, run_m / length
    theta = math.degrees(math.atan2(h, run_m))
    normal = m * G * cos_theta
    gravity = m * G * sin_theta
    resistance = inputs.kinetic_coefficient * normal
    steady = gravity + resistance
    inertial = m * limits.acceleration_mps2
    if inputs.mode == "SLIDING":
        breakaway = m * G * (sin_theta + inputs.mu_s * cos_theta)
        peak = max(breakaway, steady + inertial)
        # Only a STATIC sliding-load test; releasing a load that is moving
        # does not imply it instantaneously stops or remains at rest.
        hold = max(0.0, m * G * (sin_theta - inputs.mu_s * cos_theta))
        holding = hold <= 1e-9
    else:
        breakaway = None  # Wheeled stiction/holding cannot be inferred from Crr.
        peak = steady + inertial
        hold = None
        holding = None
    work = steady * length
    return RampResult(
        run_m=run_m, length_m=length, angle_deg=theta,
        normal_n=normal, gravity_n=gravity, resistance_n=resistance,
        steady_n=steady, breakaway_n=breakaway, inertial_n=inertial,
        peak_n=peak, work_j=work,
        efficiency=inputs.load_kg * G * h / work,
        ideal_mechanical_advantage=length / h,
        actual_mechanical_advantage=inputs.load_kg * G / steady,
        holding_force_n=hold, holding_at_rest=holding,
        space_ok=run_m <= inputs.max_run_m + EPS,
        angle_ok=theta <= limits.max_angle_deg + EPS,
        force_ok=peak <= limits.max_peak_n + EPS,
    )


def theta_for_force(total_mass_kg: float, coefficient: float, added_force_n: float, force_limit_n: float) -> float:
    """Upper allowed angle (radians) in the implemented 0–45° domain.

    This uses the monotonic branch of sin(theta)+k*cos(theta) applicable here.
    May return <=0 if even a near-flat ramp exceeds the force limit.
    """
    factor = total_mass_kg * G
    arg = (force_limit_n - added_force_n) / (factor * math.sqrt(1.0 + coefficient ** 2))
    if arg >= 1.0:
        return math.pi / 2
    return math.asin(max(-1.0, arg)) - math.atan(coefficient)


def analyze(inputs: Inputs, limits: PlanningLimits) -> Analysis:
    validate(inputs, limits)
    mass = inputs.total_mass_kg
    if inputs.mode == "SLIDING":
        force_angle = min(
            theta_for_force(mass, inputs.mu_s, 0.0, limits.max_peak_n),
            theta_for_force(mass, inputs.mu_k, mass * limits.acceleration_mps2, limits.max_peak_n),
        )
    else:
        force_angle = theta_for_force(
            mass, inputs.c_rr, mass * limits.acceleration_mps2, limits.max_peak_n
        )
    cap = math.radians(limits.max_angle_deg)
    allow = min(cap, force_angle)
    x_angle = inputs.height_m / math.tan(cap)
    at_max = calculate_at_run(inputs, limits, inputs.max_run_m)
    limiting = "FORCE" if force_angle < cap - 1e-12 else "ANGLE"
    if allow <= 1e-9:
        return Analysis(False, "Force limit cannot be met, even on an almost-flat ramp.",
                        x_angle, None, math.degrees(force_angle),
                        math.degrees(allow), limiting, at_max, None)
    x_required = inputs.height_m / math.tan(allow)
    # Longest run qualifies if and only if shortest required <= xmax.
    if x_required > inputs.max_run_m + EPS:
        if limiting == "FORCE":
            reason = "The force constraint requires more horizontal space than available."
        else:
            reason = "The angle limit requires more horizontal space than available."
        return Analysis(False, reason, x_angle, x_required,
                        math.degrees(force_angle), math.degrees(allow),
                        limiting, at_max, None)
    at_min = calculate_at_run(inputs, limits, min(x_required, inputs.max_run_m))
    return Analysis(True, "Qualifies under all three user-defined planning constraints.",
                    x_angle, x_required, math.degrees(force_angle),
                    math.degrees(allow), limiting, at_max, at_min)




def reference_slopes(inputs: Inputs, limits: PlanningLimits) -> list[tuple[str, RampResult]]:
    return [(f"1:{ratio}", calculate_at_run(inputs, limits, inputs.height_m * ratio))
            for ratio in RATIOS]


def force_derivative(inputs: Inputs, run_m: float) -> float:
    """dF_steady/dx used to explain analytic endpoint selection."""
    m, h, k = inputs.total_mass_kg, inputs.height_m, inputs.kinetic_coefficient
    return m * G * h * (k * h - run_m) / math.pow(h * h + run_m * run_m, 1.5)


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




def release_note(inputs: Inputs, result: RampResult) -> str:
    """What happens if the load is let go (shown on screen and in the calculation steps)."""
    if inputs.mode == "SLIDING":
        if result.holding_at_rest:
            return "If released while at rest, friction should hold the load (static check only)."
        return (f"If released, the load would slide back unless held with about "
                f"{result.holding_force_n:.0f} N.")
    return ("A wheeled load can roll back when released: hold or brake the cart. "
            "This app cannot predict holding or braking.")


def graph_samples(inputs: Inputs, limits: PlanningLimits, proposed_run_m: float,
                  points: int = 75) -> list[RampResult]:
    """Sample the continuous force/work curves for GRAPHING ONLY.

    These plotted points are not optimization candidates or research observations.
    Recommendations always come directly from `analyze()` and not from sampling.
    """
    validate(inputs, limits)
    if not math.isfinite(proposed_run_m) or not 0 < proposed_run_m <= 200:
        raise ValueError("Proposed run must be between 0 and 200 m.")
    if points < 2:
        raise ValueError("Graphs require two or more plot positions.")
    a = analyze(inputs, limits)
    finite_needed = a.x_required_m if a.x_required_m is not None else 0.0
    span = max(inputs.max_run_m, proposed_run_m, a.x_angle_m, finite_needed)
    end = min(200.0, max(0.12, span * 1.05))
    begin = max(0.05, min(inputs.max_run_m, proposed_run_m, a.x_angle_m) * 0.65)
    begin = min(begin, end * 0.85)
    return [calculate_at_run(inputs, limits, begin + (end - begin) * k / (points - 1))
            for k in range(points)]
