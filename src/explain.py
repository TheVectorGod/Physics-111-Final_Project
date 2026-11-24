"""Plain-language wording for the screen (verdict) and the step-by-step calculation text.

No GUI code here, so every sentence can be tested.  Uses only the dataclasses in physics.py.
"""
from __future__ import annotations

from physics import (G, Analysis, Inputs, PlanningLimits, force_derivative, reference_slopes,
                     release_note, work_derivative, calculate_at_run)

DEG = "\u00b0"


# --------------------------------------------------------------------------- verdict banner
def verdict_text(i: Inputs, l: PlanningLimits, a: Analysis) -> tuple[str, str, str]:
    """(icon, headline, explanation in everyday words).  Icon and words both carry the meaning."""
    carrier = "sled" if i.mode == "SLIDING" else "cart"
    if a.feasible:
        extra = a.at_min.peak_n - a.at_max.peak_n
        return ("\u2714", "RAMP FEASIBLE",
                f"Any ramp with a run from {a.x_required_m:.2f} m to {i.max_run_m:.2f} m works. The longest one "
                f"needs the least effort: {a.at_max.steady_n:.0f} N to keep the load moving and "
                f"{a.at_max.peak_n:.0f} N to get it started. The shortest one saves space and work but needs "
                f"{extra:.0f} N more to get started.")
    if a.x_required_m is None:
        return ("\u2716", "NOT FEASIBLE: too hard to get moving",
                f"Even on almost flat ground, getting this load moving takes more than your limit of "
                f"{l.max_peak_n:.0f} N, so no ramp can work. Try: raise the force limit, reduce the load or "
                f"{carrier} weight, or lower the resistance"
                + (" (a bigger wheel helps)." if i.mode == "WHEELED" else "."))
    if a.limiting_constraint == "FORCE":
        cause = f"keep the first push under your limit of {l.max_peak_n:.0f} N"
        advice = "raise the force limit, lighten the load"
    else:
        cause = f"stay under your slope limit of {l.max_angle_deg:.0f}{DEG}"
        advice = "allow a steeper slope, lower the platform"
    return ("\u2716", "NOT FEASIBLE: not enough floor space",
            f"To {cause}, the ramp needs a run of at least {a.x_required_m:.2f} m, but you only have "
            f"{i.max_run_m:.2f} m. Try: find more floor space, {advice}, or reduce the resistance.")


# --------------------------------------------------------------------------- step-by-step walkthrough
def explain_steps(i: Inputs, l: PlanningLimits, a: Analysis, proposed_run_m: float | None = None) -> str:
    """Every calculation step with the user's own numbers (what goes in, formula, result, plain words)."""
    sliding = i.mode == "SLIDING"
    m, c = i.total_mass_kg, a.at_max
    out: list[str] = []
    if proposed_run_m is not None:
        proposed = calculate_at_run(i, l, proposed_run_m)
        out.extend([
            "STEP 0 - Evaluate your proposed ramp",
            f"  Horizontal run = {proposed.run_m:.3f} m; ramp length = {proposed.length_m:.3f} m; angle = {proposed.angle_deg:.2f}°",
            f"  Steady force = {proposed.steady_n:.3f} N; estimated peak = {proposed.peak_n:.3f} N; modeled work = {proposed.work_j:.3f} J",
            f"  Limits: space {'PASS' if proposed.space_ok else 'FAIL'}, angle {'PASS' if proposed.angle_ok else 'FAIL'}, force {'PASS' if proposed.force_ok else 'FAIL'}.",
            "  The remaining steps show the model and explain how RampForce derives the feasible endpoint alternatives.", "",
        ])

    def step(title: str, goes_in: str, formula: str, result: str, plain: str) -> None:
        out.extend([title, f"  Goes in : {goes_in}", f"  Formula : {formula}",
                    f"  Result  : {result}", f"  In plain words: {plain}", ""])

    carrier = "sled" if sliding else "cart"
    step("STEP 1 - Your inputs",
         f"{i.load_kg:g} kg load + {i.carrier_kg:g} kg {carrier}; platform {i.height_m:g} m high; "
         f"{i.max_run_m:g} m of floor space; limits: peak force {l.max_peak_n:g} N, angle {l.max_angle_deg:g}{DEG}, "
         f"start-up acceleration {l.acceleration_mps2:g} m/s\u00b2",
         "(inputs are checked against allowed ranges)", "inputs accepted",
         "You describe the job: what you move, how high, how much room, and your limits.")

    if sliding:
        step("STEP 2 - Choose the physics model",
             f"friction while moving \u03bck = {i.mu_k:g}, friction to start \u03bcs = {i.mu_s:g}",
             f"total mass M = load + sled = {i.load_kg:g} + {i.carrier_kg:g}", f"M = {m:g} kg",
             "Dragging rubs the load against the surface, and getting it unstuck takes an extra shove.")
    else:
        step("STEP 2 - Choose the physics model",
             f"wheel radius r = {i.wheel_radius_cm:g} cm, rolling arm b = {i.roll_arm_mm:g} mm",
             f"M = load + cart = {i.load_kg:g} + {i.carrier_kg:g};  Crr = b \u00f7 r",
             f"M = {m:g} kg, Crr = {i.c_rr:.4f}",
             "Wheels roll instead of rubbing, so resistance is small, and bigger wheels roll more easily.")

    step("STEP 3 - Draw the ramp as a triangle (using all your floor space)",
         f"height {i.height_m:g} m, run {i.max_run_m:g} m",
         "angle \u03b8 = arctan(height \u00f7 run);  ramp length L = \u221a(run\u00b2 + height\u00b2)",
         f"\u03b8 = {c.angle_deg:.2f}{DEG}, L = {c.length_m:.3f} m",
         "A longer, gentler ramp has a smaller angle.")

    res_name = "friction" if sliding else "rolling resistance"
    sym, val = ("\u03bck", i.mu_k) if sliding else ("Crr", i.c_rr)
    forces = [
        f"pressing into ramp   = M g cos\u03b8 = {m:g} \u00d7 {G} \u00d7 cos({c.angle_deg:.2f}{DEG}) = {c.normal_n:.1f} N",
        f"gravity pulling back = M g sin\u03b8 = {c.gravity_n:.1f} N",
        f"{res_name:<20} = {sym} \u00d7 pressing = {val:.4f} \u00d7 {c.normal_n:.1f} = {c.resistance_n:.1f} N",
        f"STEADY (keep moving) = gravity + {res_name} = {c.steady_n:.1f} N",
    ]
    if sliding:
        forces.append(f"breakaway            = M g (sin\u03b8 + \u03bcs cos\u03b8) = {c.breakaway_n:.1f} N")
    forces.append(f"extra to speed up    = M \u00d7 a = {m:g} \u00d7 {l.acceleration_mps2:g} = {c.inertial_n:.1f} N")
    forces.append((f"PEAK (get started)   = larger of breakaway and steady + M a = {c.peak_n:.1f} N" if sliding
                   else f"PEAK (get started)   = steady + M a = {c.peak_n:.1f} N"))
    out.extend(["STEP 4 - Work out the forces on that ramp"] + ["  " + f for f in forces] + [
        f"  In plain words: you fight the hill pulling the load back and the {res_name}. "
        "Getting it moving takes more than keeping it moving.", ""])

    step("STEP 5 - Work and efficiency",
         "steady force and ramp length",
         "W = steady \u00d7 L;  payload work ratio = load weight \u00d7 height \u00f7 W;  "
         "mechanical advantage = L \u00f7 h (ideal), load weight \u00f7 steady (actual)",
         f"W = {c.work_j:.1f} J, payload work ratio = {c.efficiency * 100:.0f}%, "
         f"MA ideal {c.ideal_mechanical_advantage:.2f} / actual {c.actual_mechanical_advantage:.2f}",
         f"Only about {c.efficiency * 100:.0f}% of your effort raises the load; the rest fights {res_name}.")

    if sliding:
        step("STEP 6 - Release check (sliding load at rest only)",
             f"tan \u03b8 = {i.height_m / i.max_run_m:.3f} and friction to start \u03bcs = {i.mu_s:g}",
             "holds at rest if tan \u03b8 \u2264 \u03bcs;  hold force = M g (sin\u03b8 \u2212 \u03bcs cos\u03b8)",
             release_note(i, c),
             "Friction alone may, or may not, keep the load from sliding back.")
    else:
        step("STEP 6 - Release check (wheeled load)", "(none)", "(not predicted)", release_note(i, c),
             "Rolling resistance is far too small to hold a cart on a slope, so plan on holding or braking it.")

    step("STEP 7 - Find the steepest ramp that is still allowed",
         f"force limit {l.max_peak_n:g} N and angle limit {l.max_angle_deg:g}{DEG}",
         "\u03b8 = arcsin[(Fmax \u2212 extra) \u00f7 (M g \u221a(1 + C\u00b2))] \u2212 arctan C  "
         "(the smaller of this and the angle limit)",
         f"force limit allows {a.theta_force_deg:.2f}{DEG}; angle limit allows {l.max_angle_deg:.2f}{DEG}; "
         f"allowed = {a.theta_allowed_deg:.2f}{DEG} ({'force' if a.limiting_constraint == 'FORCE' else 'angle'} limit decides)"
         + (f"; shortest run needed = {a.x_required_m:.3f} m" if a.x_required_m is not None else ""),
         "How steep can the ramp be before the first push is too hard or the slope too steep? "
         "That sets the shortest ramp.")

    if a.feasible:
        verdict = (f"needed run {a.x_required_m:.3f} m \u2264 floor space {i.max_run_m:.3f} m: FEASIBLE "
                   f"(usable runs {a.x_required_m:.2f}-{i.max_run_m:.2f} m)")
        plain = "The gentlest acceptable ramp fits on your floor, so a usable ramp exists."
    elif a.x_required_m is None:
        verdict = "even a nearly flat ramp needs more than the force limit: NOT FEASIBLE"
        plain = "The very first push already exceeds your limit, whatever the ramp."
    else:
        verdict = f"needed run {a.x_required_m:.3f} m > floor space {i.max_run_m:.3f} m: NOT FEASIBLE"
        plain = "The gentlest acceptable ramp is longer than your floor."
    step("STEP 8 - Does it fit?", "needed run vs floor space", "compare the two lengths", verdict, plain)

    if a.feasible:
        s = a.at_min
        dfdx, dwdx = force_derivative(i, i.max_run_m), work_derivative(i)
        out.extend([
            "STEP 9 - Choose between the usable ramps",
            f"  Longest  ({c.run_m:.2f} m): steady {c.steady_n:.1f} N, peak {c.peak_n:.1f} N, work {c.work_j:.0f} J  <- least force",
            f"  Shortest ({s.run_m:.2f} m): steady {s.steady_n:.1f} N, peak {s.peak_n:.1f} N, work {s.work_j:.0f} J  <- least work",
            f"  Calculus: dF/dx at the longest run = {dfdx:.2f} N per m (negative: force falls as the ramp gets longer);",
            f"            dW/dx = {dwdx:.2f} J per m (positive: work rises as the ramp gets longer).",
            f"  In plain words: the longer ramp saves {s.peak_n - c.peak_n:.0f} N at the start but costs "
            f"{c.work_j - s.work_j:.0f} J more work and {c.length_m - s.length_m:.2f} m more ramp.", ""])
    else:
        out.extend(["STEP 9 - Choose between the usable ramps",
                    "  No usable ramp exists, so there is nothing to choose between.", ""])

    out.append("STEP 10 - Screen the standard slopes (1:N means run = N \u00d7 height)")
    for label, r in reference_slopes(i, l):
        mark = "\u2714" if r.feasible else "\u2716"
        out.append(f"  {label:<5} run {r.run_m:5.2f} m, {r.angle_deg:4.1f}{DEG}, peak {r.peak_n:6.1f} N  {mark} {r.plain_status}")
    out.append("  In plain words: the textbook gentle ramps are easiest to push but often need more room than you have.")
    return "\n".join(out)
