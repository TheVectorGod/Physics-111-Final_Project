"""CSV export, source v2 reference-case comparison, and summary file creation."""
from __future__ import annotations
 
import csv
from datetime import datetime
import io
import math
from pathlib import Path
 
from physics import Inputs, PlanningLimits, RampResult, analyze, calculate_at_run, sweep, G
 
 
# The 10 supplied reference cases, embedded so the "Load supplied 10 cases" button still works if
# the samples/ folder is missing (for example in a packaged .exe built without --add-data).
SUPPLIED_REFERENCE_CSV = """case,mode,load_kg,carrier_kg,height_m,run_m,c1(muK|r_cm),c2(muS|b_mm),accel_mps2,ref_steady_N,ref_peak_N,ref_work_J
1,SLIDING,30,5,0.6,3.0,0.3,0.4,0.2,168.341187,202.009425,515.025000
2,SLIDING,30,0,0.6,2.0,0.25,0.35,0.2,155.038552,183.227379,323.730000
3,SLIDING,60,10,1.0,5.0,0.45,0.6,0.3,437.687087,538.691800,2231.775000
4,SLIDING,15,0,0.4,1.5,0.05,0.05,0.2,45.024133,48.024133,69.896250
5,SLIDING,80,20,1.2,8.0,0.6,0.9,0.1,727.609922,1018.653890,5886.000000
6,WHEELED,30,13.76,0.6,3.0,9.9,2.333,0.2,94.109776,102.861776,287.920551
7,WHEELED,30,15,0.6,2.0,10,2.0,0.2,135.306372,144.306372,282.528000
8,WHEELED,60,25,1.0,5.0,7.5,3.0,0.3,196.237727,221.737727,1000.620000
9,WHEELED,20,8,0.4,1.5,5.0,1.0,0.2,76.082885,81.682885,118.112400
10,WHEELED,80,30,1.2,8.0,15,4.0,0.1,188.531815,199.531815,1525.128000
"""
 
CSV_COLUMNS = [
    "scenario_id", "mode", "total_mass_kg", "load_kg", "carrier_kg", "height_m",
    "max_run_m", "force_max_N", "angle_cap_deg", "accel_mps2",
    "coeff_kinetic", "coeff_start", "wheel_radius_cm", "roll_arm_mm",
    "run_m", "length_m", "angle_deg", "gravity_N", "normal_N", "resist_N",
    "steady_force_N", "breakaway_N", "peak_force_N", "work_J", "efficiency",
    "space_ok", "angle_ok", "force_ok", "feasible", "status"
]
 
 
def csv_dict(inputs: Inputs, limits: PlanningLimits, r: RampResult, scenario: str) -> dict[str, str]:
    def f(v: float | None, n: int = 6) -> str:
        return "" if v is None else f"{v:.{n}f}"
    return dict(zip(CSV_COLUMNS, [
        scenario, inputs.mode, f(inputs.total_mass_kg), f(inputs.load_kg), f(inputs.carrier_kg),
        f(inputs.height_m), f(inputs.max_run_m), f(limits.max_peak_n),
        f(limits.max_angle_deg), f(limits.acceleration_mps2),
        f(inputs.kinetic_coefficient), f(inputs.start_coefficient),
        f(inputs.wheel_radius_cm) if inputs.mode == "WHEELED" else "",
        f(inputs.roll_arm_mm) if inputs.mode == "WHEELED" else "",
        f(r.run_m), f(r.length_m), f(r.angle_deg), f(r.gravity_n), f(r.normal_n),
        f(r.resistance_n), f(r.steady_n), f(r.breakaway_n), f(r.peak_n),
        f(r.work_j), f(r.efficiency),
        "YES" if r.space_ok else "NO", "YES" if r.angle_ok else "NO",
        "YES" if r.force_ok else "NO", "YES" if r.feasible else "NO", r.status,
    ]))
 
 
def export_candidates(path: str | Path, inputs: Inputs, limits: PlanningLimits, scenario: str = "S01") -> int:
    rows = sweep(inputs, limits)
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(csv_dict(inputs, limits, r, scenario))
    return len(rows)
 
 
def export_summary(path: str | Path, inputs: Inputs, limits: PlanningLimits, scenario: str = "S01") -> None:
    """Save a single study record; one row per scenario, not a measurement."""
    a = analyze(inputs, limits)
    chosen = a.at_max if a.feasible else None
    row = {
        "scenario_id": scenario, "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "model_version": "RampForce Tkinter v1 / source RampForce v2", "mode": inputs.mode,
        "load_kg": inputs.load_kg, "carrier_kg": inputs.carrier_kg,
        "height_m": inputs.height_m, "max_run_m": inputs.max_run_m,
        "mu_k": inputs.mu_k if inputs.mode == "SLIDING" else "",
        "mu_s": inputs.mu_s if inputs.mode == "SLIDING" else "",
        "wheel_radius_cm": inputs.wheel_radius_cm if inputs.mode == "WHEELED" else "",
        "roll_arm_mm": inputs.roll_arm_mm if inputs.mode == "WHEELED" else "",
        "max_peak_n": limits.max_peak_n, "max_angle_deg": limits.max_angle_deg,
        "acceleration_mps2": limits.acceleration_mps2, "feasible": a.feasible,
        "reason": a.reason, "shortest_feasible_run_m": a.x_required_m if a.feasible else "",
        "least_force_run_m": chosen.run_m if chosen else "",
        "least_steady_force_N": chosen.steady_n if chosen else "",
        "least_work_run_m": a.at_min.run_m if a.at_min else "",
        "least_work_J": a.at_min.work_j if a.at_min else "",
        "theoretical_model_only": "YES", "actual_observed_force_N": "",
        "external_reference_source": "", "researcher_notes": "",
    }
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
 
 
def compare_references(path: str | Path) -> list[dict]:
    """Compare a reference CSV file against this Python implementation.
 
    NOT experimental validation. The supplied dataset was generated from the same
    declared theoretical equations and should be treated as implementation QA.
    """
    with open(path, newline="", encoding="utf-8-sig") as file:
        return _compare_reader(csv.DictReader(file))
 
 
def compare_reference_text(text: str) -> list[dict]:
    """Same comparison for CSV text already in memory (used for the embedded cases)."""
    return _compare_reader(csv.DictReader(io.StringIO(text)))
 
 
def _compare_reader(reader: csv.DictReader) -> list[dict]:
    required = {"case", "mode", "load_kg", "carrier_kg", "height_m", "run_m",
                "c1(muK|r_cm)", "c2(muS|b_mm)", "accel_mps2",
                "ref_steady_N", "ref_peak_N", "ref_work_J"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError("Reference CSV is missing one or more required columns. Use the supplied tests/reference_cases.csv format.")
    rows = []
    for line, row in enumerate(reader, start=2):
        try:
            mode_name = row["mode"].strip().upper()
            if mode_name in ("S", "SLIDE", "SLIDING"):
                mode_name = "SLIDING"
            elif mode_name in ("W", "WHEEL", "WHEELED"):
                mode_name = "WHEELED"
            else:
                raise ValueError("Invalid mode")
            c1, c2 = float(row["c1(muK|r_cm)"]), float(row["c2(muS|b_mm)"])
            x = float(row["run_m"])
            # Maximum available run must be at least 0.10m per source v2
            # and doesn't influence the raw force computation at this x.
            p = Inputs(mode=mode_name, load_kg=float(row["load_kg"]),
                       carrier_kg=float(row["carrier_kg"]), height_m=float(row["height_m"]),
                       max_run_m=max(0.10, x), mu_k=c1 if mode_name == "SLIDING" else 0.30,
                       mu_s=c2 if mode_name == "SLIDING" else 0.40,
                       wheel_radius_cm=c1 if mode_name == "WHEELED" else 10.0,
                       roll_arm_mm=c2 if mode_name == "WHEELED" else 2.0)
            l = PlanningLimits(acceleration_mps2=float(row["accel_mps2"]))
            c = calculate_at_run(p, l, x)
            ref_steady, ref_peak, ref_work = (float(row[k]) for k in
                       ("ref_steady_N", "ref_peak_N", "ref_work_J"))
            if not all(math.isfinite(a) for a in (ref_steady, ref_peak, ref_work)):
                raise ValueError("Reference values must be finite")
            rows.append({
                "case": row["case"], "mode": mode_name,
                "ref_steady": ref_steady, "calc_steady": c.steady_n,
                "steady_err": abs(c.steady_n - ref_steady),
                "ref_peak": ref_peak, "calc_peak": c.peak_n,
                "peak_err": abs(c.peak_n - ref_peak),
                "ref_work": ref_work, "calc_work": c.work_j,
                "work_err": abs(c.work_j - ref_work),
            })
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid reference data on row {line}: {exc}") from exc
    if not rows:
        raise ValueError("The reference CSV contains no test cases.")
    return rows
 
 
def export_comparison(path: str | Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("No comparison data to export.")
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)