"""RampForce desktop interface. Run `python main.py` after `pip install -r requirements.txt`."""
from __future__ import annotations
 
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
 
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
 
from physics import (Inputs, PlanningLimits, analyze, calculate_at_run, field_errors, parse_run,
                     reference_slopes, release_note, sweep, what_if_sweep)
from datasets import (SUPPLIED_REFERENCE_CSV, compare_reference_text, compare_references,
                      export_candidates, export_comparison, export_summary)
from explain import explain_steps, verdict_text

# IMPORT GUIDE (keep these statements so other files integrate unchanged):
# `tkinter`/`ttk`: window, entries, buttons, canvases, notebook tabs, and tables.
# `filedialog`/`messagebox`: file selection and friendly error dialogs.
# `tkfont`: adjustable text sizes; `Figure` and `FigureCanvasTkAgg`: embedded plots.
# `physics`: all calculations, feasibility, slopes, and validation.
# `datasets`: CSV file export and comparing reference tests; `explain`: wording.
# `Path` and `sys`: locate packaged files such as sample CSVs.
 
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
FIELDS = {
    "load": "Cargo mass (kg)", "carrier": "Sled/cart mass (kg)",
    "height": "Platform height (m)", "max_run": "Available run xmax (m)",
    "mu_k": "Kinetic friction μk", "mu_s": "Static friction μs",
    "radius": "Wheel radius (cm)", "arm": "Rolling arm b (mm)",
    "fmax": "Peak-force limit (N)", "angle": "Angle limit (°)",
    "accel": "Assumed acceleration (m/s²)",
}
# Short help shown when the mouse hovers over, or the keyboard focuses, a box.
TIPS = {
    "load": "Weight of the thing you are moving. Do not include the sled or cart.",
    "carrier": "Weight of the sled, pallet or cart. It must be lifted too.",
    "height": "How high the load must be lifted.",
    "max_run": "Horizontal floor distance you can use for the ramp (xmax).",
    "mu_k": "Friction once the load is sliding: 0.01 is very slippery, 1 is very rough.",
    "mu_s": "Friction before the load starts to slide. Never lower than the kinetic friction.",
    "radius": "Half of the wheel's diameter. Bigger wheels roll more easily.",
    "arm": "How much wheel and floor squash together (b). Hard wheels on smooth floors: about 0.5-2 mm.",
    "fmax": "The hardest first push you are willing to make. YOUR planning limit, not a safety standard.",
    "angle": "The steepest ramp you will accept. YOUR planning limit, not a safety standard.",
    "accel": "How quickly you get the load moving. A gentle start is about 0.2 m/s².",
}
DEFAULTS = {
    "scenario": "S01", "mode": "SLIDING", "load": "30", "carrier": "5",
    "height": "0.60", "max_run": "3.00", "mu_k": "0.30", "mu_s": "0.40",
    "radius": "10", "arm": "2", "fmax": "222", "angle": "20",
    "accel": "0.20", "custom": "2.50",
}
# Banner colours. The banner ALWAYS also shows an icon and words, so colour is never the only signal.
LEVEL_COLORS = {"ok": ("#e6f4ea", "#14532d"), "bad": ("#fdecea", "#7f1d1d"), "warn": ("#fff4d6", "#6b4e00")}
MODEL_TEXT = """THEORETICAL MODELS (g = 9.81 m/s²)
M = cargo + carrier mass; x = horizontal run; h = platform height.
L = sqrt(x² + h²),   θ = atan2(h, x)
Normal = Mg cos θ;   Downhill gravity = Mg sin θ
 
SLIDING:
Steady = Mg(sin θ + μk cos θ)
Breakaway = Mg(sin θ + μs cos θ)
Peak = max(Breakaway, Steady + Ma)
Static holding is only checked for a load that is already at rest
(see "How it was calculated", step 6).
 
WHEELED:
Effective Crr = b/r (both in the same length unit)
Steady = Mg(sin θ + Crr cos θ)
Peak = Steady + Ma
Stationary wheel holding/braking is NOT predicted: a released cart
may roll back, so hold or brake it.
 
WORK AND CALCULUS:
W = Steady × L = Mg(h + kx), where k = μk or Crr
Steady-force derivative = Mgh(kh − x)/(h² + x²)^(3/2)
Work derivative = Mgk
Within the model's restricted angle/coefficients, the longest qualifying
run gives the least steady force; the shortest gives the least work.
 
A candidate qualifies only when all three conditions are met:
x ≤ xmax,  θ ≤ angle limit,  Peak ≤ force limit.
The 101-point sweep is for comparison, NOT physical measurements.
 
LIMITATIONS:
The ramp is idealized as straight and rigid; the push is parallel to it;
coefficients are assumed constant. Start-up is a simplified estimate.
The application does not measure human effort, structural strength, braking,
or workplace safety. Planning limits are user-defined examples, NOT standards.
Independent reference equations verify implementation, not physical accuracy.
"""
 
 
class Tooltip:
    """Small help bubble shown on mouse hover or keyboard focus."""
 
    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        for event, handler in (("<Enter>", self.show), ("<FocusIn>", self.show), ("<Leave>", self.hide),
                               ("<FocusOut>", self.hide), ("<Escape>", self.hide)):
            widget.bind(event, handler, add="+")
 
    def show(self, _event=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 24
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, justify="left", background="#fffbe0", foreground="#222222",
                 relief="solid", borderwidth=1, wraplength=320, padx=8, pady=6).pack()
 
    def hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None
 
 
class RampForceApp(tk.Tk):
    def __init__(self):
        # === Christian — RampForceApp.__init__ ===
        # GOAL: Initialize the window, StringVars, state, fonts, style, tabs, bindings, and initial analysis.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp.__init__")
 
    # ------------------------------------------------------------------ fonts and style
    def _fonts(self):
        # === Cedric — RampForceApp._fonts ===
        # GOAL: Create shared Tkinter font objects.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp._fonts")
 
    def _apply_sizes(self):
        # === Cedric — RampForceApp._apply_sizes ===
        # GOAL: Apply current text size to Tk fonts and Treeview rows.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp._apply_sizes")
 
    def change_text_size(self, delta):
        # === Cedric — RampForceApp.change_text_size ===
        # GOAL: Change/reset base font size; reapply sizes and refresh the display.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp.change_text_size")
 
    def _style(self):
        # === Cedric — RampForceApp._style ===
        # GOAL: Configure ttk theme, colors and named label/button styles.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp._style")
 
    def _bind_keys(self):
        # === Cedric — RampForceApp._bind_keys ===
        # GOAL: Connect Enter, Ctrl+Plus, Ctrl+Minus and Ctrl+0 shortcuts.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp._bind_keys")
 
    # ------------------------------------------------------------------ building blocks
    def _field(self, parent, key):
        label = ttk.Label(parent, text=FIELDS[key])
        label.pack(anchor="w", pady=(7, 1))
        entry = ttk.Entry(parent, textvariable=self.vars[key])
        entry.pack(fill="x")
        self.entries[key] = entry
        self.error_labels[key] = ttk.Label(parent, textvariable=self.error_vars[key], style="Error.TLabel",
                                           wraplength=240, justify="left")
        Tooltip(entry, TIPS[key])
        Tooltip(label, TIPS[key])
 
    def _show_field_errors(self, errors):
        """Put each message right under its own box (instead of one popup at a time)."""
        for key, label in self.error_labels.items():
            message = errors.get(key, "")
            self.error_vars[key].set(f"⚠ {message}" if message else "")
            if message:
                label.pack(anchor="w", after=self.entries[key])
            else:
                label.pack_forget()
 
    @staticmethod
    def _table(parent, columns):
        # === Cedric — RampForceApp._table ===
        # GOAL: Create a ttk.Treeview with headings and horizontal/vertical scrollbars.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp._table")
 
    @staticmethod
    def _text_box(parent, font):
        # === Ace — RampForceApp._text_box ===
        # GOAL: Create a read-only, scrollable tkinter.Text widget.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Ace: implement RampForceApp._text_box")
 
    @staticmethod
    def _set_text(widget, content):
        # === Ace — RampForceApp._set_text ===
        # GOAL: Replace text in a read-only Text widget; highlight STEP headings.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Ace: implement RampForceApp._set_text")
 
    def _rewrap(self, width):
        # === Christian — RampForceApp._rewrap ===
        # GOAL: Update long label wraplengths when the window resizes.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp._rewrap")
 
    # ------------------------------------------------------------------ layout
    def _build(self):
        # === Christian — RampForceApp._build ===
        # GOAL: Construct main header, side inputs and original five notebook tabs.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp._build")
 
    def _build_inputs(self, parent):
        side = ttk.Frame(parent, width=300)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        ttk.Label(side, text="Input parameters", style="Header.TLabel").pack(anchor="w")
        ttk.Label(side, text="Results update as you type.", style="Hint.TLabel").pack(anchor="w")
        foot = ttk.Frame(side)
        foot.pack(side="bottom", fill="x", pady=7)
        ttk.Button(foot, text="Analyze ramps", command=self.run_analysis).pack(fill="x", pady=2)
        ttk.Button(foot, text="Restore defaults", command=self._reset).pack(fill="x", pady=2)
 
        canvas = tk.Canvas(side, highlightthickness=0)
        bar = ttk.Scrollbar(side, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        fields = ttk.Frame(canvas, padding=(0, 5, 9, 5))
        window = canvas.create_window((0, 0), window=fields, anchor="nw")
        fields.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
 
        wheel_events = ("<MouseWheel>", "<Button-4>", "<Button-5>")
 
        def on_wheel(event):                    # mouse-wheel scrolling for the input panel
            if getattr(event, "num", 0) == 4:
                step = -1
            elif getattr(event, "num", 0) == 5:
                step = 1
            else:
                step = -1 if event.delta > 0 else 1
            canvas.yview_scroll(step, "units")
 
        def grab_wheel(_event):
            for seq in wheel_events:
                canvas.bind_all(seq, on_wheel)
 
        def release_wheel(_event):
            for seq in wheel_events:
                canvas.unbind_all(seq)
        canvas.bind("<Enter>", grab_wheel)
        canvas.bind("<Leave>", release_wheel)
 
        ttk.Label(fields, text="Scenario ID").pack(anchor="w")
        ttk.Entry(fields, textvariable=self.vars["scenario"]).pack(fill="x")
        ttk.Label(fields, text="Transportation mode").pack(anchor="w", pady=(7, 1))
        mode = ttk.Combobox(fields, values=["SLIDING", "WHEELED"],
                            textvariable=self.vars["mode"], state="readonly")
        mode.pack(fill="x")
        mode.bind("<<ComboboxSelected>>", self._on_mode_selected)
        for key in ("load", "carrier", "height", "max_run"):
            self._field(fields, key)
        self.slide_fields = ttk.Frame(fields)
        self.wheel_fields = ttk.Frame(fields)
        for key in ("mu_k", "mu_s"):
            self._field(self.slide_fields, key)
        for key in ("radius", "arm"):
            self._field(self.wheel_fields, key)
        self.planning = ttk.LabelFrame(fields, text="Planning settings", padding=7)
        for key in ("fmax", "angle", "accel"):
            self._field(self.planning, key)
        self.planning.pack(fill="x", pady=(13, 5))
        ttk.Label(fields, text="User-defined limits are not safety standards.", wraplength=240).pack(anchor="w")
        self._switch_mode()
 
    def _on_mode_selected(self, _event=None):
        self._switch_mode()
        self.run_analysis()
 
    def _switch_mode(self):
        self.slide_fields.pack_forget()
        self.wheel_fields.pack_forget()
        target = self.slide_fields if self.vars["mode"].get() == "SLIDING" else self.wheel_fields
        target.pack(fill="x", before=self.planning)
 
    def _card(self, parent, title):
        # === Ace — RampForceApp._card ===
        # GOAL: Create one results card and return its display StringVars.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Ace: implement RampForceApp._card")
 
    def _build_overview(self, page):
        # === Ace — RampForceApp._build_overview ===
        # GOAL: Build verdict, selection cards, ramp canvas, and custom-run checker.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Ace: implement RampForceApp._build_overview")
 
    def _on_check_return(self, _event=None):
        # === Cedric — RampForceApp._on_check_return ===
        # GOAL: Run custom check and prevent global Enter handling from repeating analysis.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp._on_check_return")
 
    def _build_comparison(self, page):
        # === Cedric — RampForceApp._build_comparison ===
        # GOAL: Build Matplotlib plots, comparison controls, and ramp table.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp._build_comparison")
 
    def _build_steps(self, page):
        # === Ace — RampForceApp._build_steps ===
        # GOAL: Build the How it was calculated tab using explain_steps.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Ace: implement RampForceApp._build_steps")
 
    def _build_references(self, page):
        # === Christian — RampForceApp._build_references ===
        # GOAL: Build reference CSV import/fallback controls, table, and error summary.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp._build_references")
 
    def _build_models(self, page):
        # === Ace — RampForceApp._build_models ===
        # GOAL: Show the preserved MODEL_TEXT explanation in a scrollable text box.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Ace: implement RampForceApp._build_models")
 
    # ------------------------------------------------------------------ reading the boxes
    def _read_values(self):
        """Parse the boxes.  Returns (inputs, limits, errors); errors is {field_key: message}."""
        mode = self.vars["mode"].get()
        keys = ["load", "carrier", "height", "max_run", "fmax", "angle", "accel"]
        keys += ["mu_k", "mu_s"] if mode == "SLIDING" else ["radius", "arm"]
        values, errors = {}, {}
        for key in keys:
            try:
                values[key] = float(self.vars[key].get().strip().replace(",", "."))
            except ValueError:
                errors[key] = "Enter a number."
        if errors:
            return None, None, errors
        extra = ({"mu_k": values["mu_k"], "mu_s": values["mu_s"]} if mode == "SLIDING"
                 else {"wheel_radius_cm": values["radius"], "roll_arm_mm": values["arm"]})
        p = Inputs(mode=mode, load_kg=values["load"], carrier_kg=values["carrier"],
                   height_m=values["height"], max_run_m=values["max_run"], **extra)
        limits = PlanningLimits(values["fmax"], values["angle"], values["accel"])
        return p, limits, field_errors(p, limits)
 
    def _schedule_analysis(self, *_):
        """Wait 300 ms after the last keystroke, then recalculate (keeps typing smooth)."""
        if self._after_id is not None:
            self.after_cancel(self._after_id)
        self._after_id = self.after(300, self.run_analysis)
 
    def _reset(self):
        for key, value in DEFAULTS.items():
            self.vars[key].set(value)
        self._switch_mode()
        self.run_analysis()
 
    # ------------------------------------------------------------------ the one place inputs become results
    def run_analysis(self):
        # === Christian — RampForceApp.run_analysis ===
        # GOAL: Coordinate validation, physics.analyze/sweep, text/cards/graph/table and stale-result prevention.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp.run_analysis")
 
    @staticmethod
    def _fill(vars_, texts):
        # === Ace — RampForceApp._fill ===
        # GOAL: Set display StringVars from the provided texts.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Ace: implement RampForceApp._fill")
 
    def _clear_results(self):
        # === Cedric — RampForceApp._clear_results ===
        # GOAL: Clear old verdict, data tables, graph and explanation when input is invalid.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp._clear_results")
 
    def _show_banner(self, level, icon, title, text):
        # === Ace — RampForceApp._show_banner ===
        # GOAL: Style the status banner and set icon, title and explanation text.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Ace: implement RampForceApp._show_banner")
 
    # ------------------------------------------------------------------ drawings
    def _draw_ramp(self):
        # === Ace — RampForceApp._draw_ramp ===
        # GOAL: Draw scaled ramp geometry, x and xmax labels on Tk Canvas.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Ace: implement RampForceApp._draw_ramp")
 
    def check_custom(self, quiet=False):
        # === Cedric — RampForceApp.check_custom ===
        # GOAL: Evaluate a custom run as metres or 1:N; show plain-language constraints and results.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp.check_custom")
 
    def _update_graphs(self):
        # === Cedric — RampForceApp._update_graphs ===
        # GOAL: Draw steady/peak forces and work; handle infeasible cases with what-if data.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp._update_graphs")
 
    def _update_table(self, which):
        # === Cedric — RampForceApp._update_table ===
        # GOAL: Populate 101-run or standard-slope results with readable status values.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Cedric: implement RampForceApp._update_table")
 
    # ------------------------------------------------------------------ files
    def _choose_file(self, filename, kind="csv", save=True):
        # === Christian — RampForceApp._choose_file ===
        # GOAL: Open a tkinter file chooser for CSV/PNG save or import.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp._choose_file")
 
    def save_graph(self):
        # === Christian — RampForceApp.save_graph ===
        # GOAL: Save the Matplotlib figure as PNG and display status or file I/O errors.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp.save_graph")
 
    def save_csv(self, kind):
        # === Christian — RampForceApp.save_csv ===
        # GOAL: Save candidate, summary or reference-comparison CSV using datasets.py functions.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp.save_csv")
 
    def import_refs(self):
        # === Christian — RampForceApp.import_refs ===
        # GOAL: Choose a reference CSV to import.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp.import_refs")
 
    def _load_supplied(self):
        # === Christian — RampForceApp._load_supplied ===
        # GOAL: Load sample CSV from samples/ or use SUPPLIED_REFERENCE_CSV fallback.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp._load_supplied")
 
    def _load_refs(self, path):
        # === Christian — RampForceApp._load_refs ===
        # GOAL: Load/compare external CSV and show friendly errors.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp._load_refs")
 
    def _show_references(self, rows):
        # === Christian — RampForceApp._show_references ===
        # GOAL: Fill reference results table and compute mean absolute errors.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Christian: implement RampForceApp._show_references")
 
 
def _enable_sharp_text_on_windows():
    # === Christian — _enable_sharp_text_on_windows ===
    # GOAL: Apply optional Windows DPI awareness; skip gracefully on non-Windows systems.
    # Keep function name/parameters/return contract unchanged.
    raise NotImplementedError("Christian: implement _enable_sharp_text_on_windows")
 
 
if __name__ == "__main__":
    _enable_sharp_text_on_windows()
    RampForceApp().mainloop()
 