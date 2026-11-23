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
        super().__init__()
        self.title("RampForce | Inclined-Plane Analysis")
        # never ask for more than the screen offers (many laptops are only 768 px tall)
        self.geometry(f"{min(1250, self.winfo_screenwidth() - 40)}x{min(790, self.winfo_screenheight() - 90)}")
        self.minsize(900, 600)
        self.vars = {key: tk.StringVar(value=value) for key, value in DEFAULTS.items()}
        self.error_vars = {key: tk.StringVar() for key in FIELDS}
        self.entries, self.error_labels = {}, {}
        self.status = tk.StringVar(value="Ready")
        self.inputs = self.limits = self.analysis = None
        self.candidates = []
        self.reference_rows = []
        self.table_choice = "candidates"
        self.diagram_choice = tk.StringVar(value="Least-force run")
        self.base_size = 11
        self.style = None
        self._after_id = None
        self._wrap_labels = []
        self._fonts()
        self._style()
        self._build()
        self._bind_keys()
        self.run_analysis()
        # live updates start only now, so building the window does not trigger recalculations
        for key in FIELDS:
            self.vars[key].trace_add("write", self._schedule_analysis)

    # ------------------------------------------------------------------ fonts and style
    def _fonts(self):
        self.f_default = tkfont.nametofont("TkDefaultFont")
        self.f_text = tkfont.nametofont("TkTextFont")
        self.f_fixed = tkfont.nametofont("TkFixedFont")
        family = self.f_default.actual("family")
        self.f_bold = tkfont.Font(family=family, weight="bold")
        self.f_head = tkfont.Font(family=family, weight="bold")
        self.f_verdict = tkfont.Font(family=family, weight="bold")
        self.f_icon = tkfont.Font(family=family, weight="bold")
        self._apply_sizes()

    def _apply_sizes(self):
        b = self.base_size
        for font, size in ((self.f_default, b), (self.f_text, b), (self.f_fixed, b), (self.f_bold, b),
                           (self.f_head, b + 3), (self.f_verdict, b + 7), (self.f_icon, b + 20)):
            font.configure(size=size)
        for name in ("TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
            try:
                tkfont.nametofont(name).configure(size=b)
            except tk.TclError:
                pass
        if self.style is not None:
            self.style.configure("Treeview", rowheight=int(b * 2.3))

    def change_text_size(self, delta):
        """delta = +1 / -1 to grow or shrink all text; 0 resets it."""
        self.base_size = max(9, min(20, self.base_size + delta)) if delta else 11
        self._apply_sizes()
        self.run_analysis()

    def _style(self):
        self.style = style = ttk.Style()
        style.theme_use("clam")
        self.configure(bg="#f2f6fa")
        style.configure("TButton", padding=(8, 5))
        style.configure("TNotebook.Tab", padding=(14, 8))
        style.configure("Treeview", rowheight=int(self.base_size * 2.3))
        style.configure("Header.TLabel", font=self.f_head)
        style.configure("Error.TLabel", foreground="#9b1c1c")
        style.configure("Hint.TLabel", foreground="#4a4a4a")
        style.configure("Value.TLabel", font=self.f_bold)

    def _bind_keys(self):
        self.bind("<Return>", lambda _: self.run_analysis())
        for seq in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.bind(seq, lambda _: self.change_text_size(1))
        for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.bind(seq, lambda _: self.change_text_size(-1))
        self.bind("<Control-0>", lambda _: self.change_text_size(0))

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
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, pady=7)
        tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings")
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="center", minwidth=70)
        vs = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hs = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree

    @staticmethod
    def _text_box(parent, font):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", font=font, padx=10, pady=10, state="disabled")
        bar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=bar.set)
        text.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        return text

    @staticmethod
    def _set_text(widget, content):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        for line in content.split("\n"):
            widget.insert("end", line + "\n", "step" if line.startswith("STEP") else ())
        widget.configure(state="disabled")

    def _rewrap(self, width):
        """Keep long labels inside the window however wide it is (they used to be clipped)."""
        for label, margin in self._wrap_labels:
            label.configure(wraplength=max(width - margin, 200))

    # ------------------------------------------------------------------ layout
    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=18, pady=(12, 5))
        ttk.Label(top, text="RAMPFORCE  |  Physics-Based Ramp Analysis", style="Header.TLabel").pack(side="left")
        larger = ttk.Button(top, text="A+", width=3, command=lambda: self.change_text_size(1))
        smaller = ttk.Button(top, text="A-", width=3, command=lambda: self.change_text_size(-1))
        larger.pack(side="right", padx=2)
        smaller.pack(side="right", padx=2)
        ttk.Label(top, text="Text size:").pack(side="right", padx=4)
        Tooltip(larger, "Larger text (Ctrl+Plus)")
        Tooltip(smaller, "Smaller text (Ctrl+Minus)")
        ttk.Label(self, textvariable=self.status).pack(side="bottom", fill="x", padx=18, pady=5)
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        self._build_inputs(body)
        tabs = ttk.Notebook(body)
        tabs.pack(side="left", fill="both", expand=True, padx=(12, 0))
        for label, builder in [
            ("Overview", self._build_overview),
            ("Ramp comparison", self._build_comparison),
            ("How it was calculated", self._build_steps),
            ("Reference verification", self._build_references),
            ("Models & limitations", self._build_models),
        ]:
            page = ttk.Frame(tabs, padding=12)
            tabs.add(page, text=label)
            builder(page)

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
        """A small box of label/value rows; returns (frame, StringVars to fill)."""
        box = ttk.LabelFrame(parent, text=title, padding=8)
        box.columnconfigure(1, weight=1)
        values = []
        for row, label in enumerate(("Run", "Angle", "Steady force (keep moving)",
                                     "Peak force (get started)", "Work")):
            var = tk.StringVar(value="-")
            ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12))
            ttk.Label(box, textvariable=var, style="Value.TLabel").grid(row=row, column=1, sticky="e")
            values.append(var)
        return box, values

    def _build_overview(self, page):
        self.summary, self.explain_text, self.icon_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.banner = tk.Frame(page, highlightthickness=3, padx=14, pady=10)
        self.banner.pack(fill="x", pady=(0, 8))
        self.banner.columnconfigure(1, weight=1)
        self.banner_icon = tk.Label(self.banner, textvariable=self.icon_var, font=self.f_icon, width=2)
        self.banner_title = tk.Label(self.banner, textvariable=self.summary, font=self.f_verdict, anchor="w")
        self.banner_text = tk.Label(self.banner, textvariable=self.explain_text, justify="left", anchor="w",
                                    font=self.f_default)
        self.banner_icon.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        self.banner_title.grid(row=0, column=1, sticky="ew")
        self.banner_text.grid(row=1, column=1, sticky="ew")

        cards = ttk.Frame(page)
        cards.pack(fill="x", pady=(0, 6))
        cards.columnconfigure((0, 1), weight=1, uniform="cards")
        box1, self.card_force = self._card(cards, "Least-force ramp (the longest that qualifies)")
        box2, self.card_work = self._card(cards, "Least-work ramp (the shortest that qualifies)")
        box1.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        box2.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        self.details = tk.StringVar()
        details = ttk.Label(page, textvariable=self.details, justify="left", style="Hint.TLabel")
        details.pack(anchor="w")
        toolbar = ttk.Frame(page)
        toolbar.pack(fill="x", pady=(8, 0))
        ttk.Label(toolbar, text="Diagram:").pack(side="left")
        choice = ttk.Combobox(toolbar, textvariable=self.diagram_choice, state="readonly",
                              values=["Least-force run", "Least-work run"], width=22)
        choice.pack(side="left", padx=7)
        choice.bind("<<ComboboxSelected>>", lambda _: self._draw_ramp())
        self.canvas = tk.Canvas(page, bg="white", height=230, highlightthickness=1)
        self.canvas.pack(fill="both", expand=True, pady=9)
        self.canvas.bind("<Configure>", lambda _: self._draw_ramp())
        line = ttk.Frame(page)
        line.pack(fill="x", pady=4)
        ttk.Label(line, text="Check a ramp (metres, or a slope such as 1:12):").pack(side="left")
        entry = ttk.Entry(line, textvariable=self.vars["custom"], width=10)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", self._on_check_return)
        ttk.Button(line, text="Check", command=self.check_custom).pack(side="left")
        self.custom_result = tk.StringVar(value="")
        custom = ttk.Label(page, textvariable=self.custom_result, justify="left")
        custom.pack(anchor="w")
        self._wrap_labels += [(self.banner_text, 140), (details, 40), (custom, 40)]
        page.bind("<Configure>", lambda e: self._rewrap(e.width))

    def _on_check_return(self, _event=None):
        self.check_custom()
        return "break"                          # stop Enter from also re-running the whole analysis

    def _build_comparison(self, page):
        bar = ttk.Frame(page)
        bar.pack(fill="x")
        for label, handler in [
            ("101 runs", lambda: self._update_table("candidates")),
            ("Standard slopes", lambda: self._update_table("ratios")),
            ("Save graph", self.save_graph),
            ("Export runs CSV", lambda: self.save_csv("runs")),
            ("Export summary CSV", lambda: self.save_csv("summary")),
        ]:
            ttk.Button(bar, text=label, command=handler).pack(side="left", padx=(0, 5))
        self.figure = Figure(figsize=(7, 4), dpi=90)
        self.chart = FigureCanvasTkAgg(self.figure, master=page)
        self.chart.get_tk_widget().pack(fill="both", expand=True)
        self.plot_force = self.figure.add_subplot(211)
        self.plot_work = self.figure.add_subplot(212, sharex=self.plot_force)
        self.table_label = tk.StringVar()
        ttk.Label(page, textvariable=self.table_label).pack(anchor="w")
        cols = [("run", "Run (m)", 85), ("angle", "Angle (°)", 90),
                ("steady", "Steady (N)", 100), ("peak", "Peak (N)", 95),
                ("work", "Work (J)", 105), ("status", "Constraint status", 230)]
        self.ramp_table = self._table(page, cols)

    def _build_steps(self, page):
        ttk.Label(page, text="Every step of the calculation, using your own numbers.",
                  style="Hint.TLabel").pack(anchor="w", pady=(0, 4))
        self.steps_text = self._text_box(page, self.f_fixed)
        self.steps_text.tag_configure("step", font=self.f_bold, spacing1=6)

    def _build_references(self, page):
        intro = ttk.Label(page, text="Compare model outputs to a reference CSV (not physical measurements).")
        intro.pack(anchor="w", pady=5)
        buttons = ttk.Frame(page)
        buttons.pack(fill="x", pady=8)
        for label, func in [
            ("Load supplied 10 cases", self._load_supplied),
            ("Import CSV", self.import_refs),
            ("Export comparison", lambda: self.save_csv("comparison")),
        ]:
            ttk.Button(buttons, text=label, command=func).pack(side="left", padx=(0, 6))
        self.ref_label = tk.StringVar(value="No reference data loaded.")
        ref_label = ttk.Label(page, textvariable=self.ref_label)
        ref_label.pack(anchor="w", pady=5)
        cols = [(k, text, 115) for k, text in [
            ("case", "Case"), ("mode", "Mode"), ("steady", "Ref steady (N)"),
            ("app", "App steady (N)"), ("err", "Steady error"),
            ("peak", "Peak error"), ("work", "Work error")]]
        self.ref_table = self._table(page, cols)
        note = ttk.Label(page, text="Reference-case agreement checks the implemented equations only. "
                         "It does not establish real-world force accuracy or safety.")
        note.pack(anchor="w", pady=7)
        self._wrap_labels += [(intro, 40), (ref_label, 40), (note, 40)]
        page.bind("<Configure>", lambda e: self._rewrap(e.width), add="+")

    def _build_models(self, page):
        text = self._text_box(page, self.f_fixed)
        self._set_text(text, MODEL_TEXT)

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
        self._after_id = None
        inputs, limits, errors = self._read_values()
        self._show_field_errors(errors)
        if errors:
            self._clear_results()
            return
        self.inputs, self.limits = inputs, limits
        self.analysis = a = analyze(inputs, limits)
        self.candidates = sweep(inputs, limits)
        icon, title, text = verdict_text(inputs, limits, a)
        self._show_banner("ok" if a.feasible else "bad", icon, title, text)

        def values(r):
            return [f"{r.run_m:.3f} m", f"{r.angle_deg:.2f}°", f"{r.steady_n:.1f} N",
                    f"{r.peak_n:.1f} N (limit {limits.max_peak_n:g} N)", f"{r.work_j:.0f} J"]
        if a.feasible:
            self._fill(self.card_force, values(a.at_max))
            self._fill(self.card_work, values(a.at_min))
        else:
            self._fill(self.card_force, ["no qualifying ramp"] + ["-"] * 4)
            self._fill(self.card_work, ["no qualifying ramp"] + ["-"] * 4)
        c = a.at_max
        self.details.set(f"At your full floor space ({c.run_m:.2f} m)"
                         f"{'' if a.feasible else ' - reference only, this ramp does not qualify'}: "
                         f"ramp length {c.length_m:.2f} m, work {c.work_j:.0f} J, "
                         f"payload work ratio {c.efficiency * 100:.0f}%.\n{release_note(inputs, c)}")
        if self.custom_result.get():
            self.check_custom(quiet=True)
        self._draw_ramp()
        self._update_graphs()
        self._update_table(self.table_choice)
        self._set_text(self.steps_text, explain_steps(inputs, limits, a))
        self.status.set(f"{self.vars['scenario'].get() or 'Scenario'}: "
                        f"{len(self.candidates)} theoretical candidates; no physical forces measured.")

    @staticmethod
    def _fill(vars_, texts):
        for var, text in zip(vars_, texts):
            var.set(text)

    def _clear_results(self):
        """Invalid inputs: remove the old answer so nothing stale can be read, exported or checked."""
        self.inputs = self.limits = self.analysis = None
        self.candidates = []
        self._show_banner("warn", "!", "Check your inputs",
                          "Fix the boxes marked with ⚠ on the left to see the answer.")
        self._fill(self.card_force, ["-"] * 5)
        self._fill(self.card_work, ["-"] * 5)
        self.details.set("")
        self.custom_result.set("")
        self._draw_ramp()
        self._update_graphs()
        self._update_table(self.table_choice)
        self._set_text(self.steps_text, "Fix the inputs marked with a warning sign to see the step-by-step calculation.")
        self.status.set("Inputs need attention: results cleared.")

    def _show_banner(self, level, icon, title, text):
        bg, fg = LEVEL_COLORS[level]
        self.banner.configure(background=bg, highlightbackground=fg, highlightcolor=fg)
        for widget in (self.banner_icon, self.banner_title, self.banner_text):
            widget.configure(background=bg, foreground=fg)
        self.icon_var.set(icon)
        self.summary.set(title)
        self.explain_text.set(text)

    # ------------------------------------------------------------------ drawings
    def _draw_ramp(self):
        cv = self.canvas
        cv.delete("all")
        if self.analysis is None:
            return
        width, height = max(cv.winfo_width(), 400), max(cv.winfo_height(), 220)
        p, a = self.inputs, self.analysis
        result = (a.at_min if self.diagram_choice.get() == "Least-work run" and a.at_min else a.at_max)
        right, ground = width - 85, height - 65
        left = 35
        full = right - left
        start = right - full * result.run_m / p.max_run_m
        rise = min(140, max(32, full * p.height_m / p.max_run_m))
        cv.create_line(15, ground, width - 12, ground, fill="#637187", width=2)
        cv.create_polygon(start, ground, right, ground - rise, right, ground, fill="#d8f0ed")
        cv.create_line(start, ground, right, ground - rise, fill="#185adb", width=4)
        cv.create_line(right, ground - rise, right, ground, fill="#087f8c", width=3)
        cv.create_text(right + 12, ground - rise / 2, text=f"h={p.height_m:g} m", anchor="w", font=self.f_default)
        # label sits ABOVE the ramp's highest point so it never overlaps the line
        cv.create_text((start + right) / 2, ground - rise - 16, font=self.f_default,
                       text=f"L={result.length_m:.2f} m  ·  θ={result.angle_deg:.1f}°")
        cv.create_line(start, ground + 16, right, ground + 16, fill="#cc7722", arrow="both", width=2)
        cv.create_text((start + right) / 2, ground + 6, text=f"x={result.run_m:.2f} m", fill="#a66418", font=self.f_default)
        cv.create_line(left, ground + 40, right, ground + 40, fill="#0a765d", arrow="both", width=2)
        cv.create_text((left + right) / 2, ground + 54, text=f"xmax={p.max_run_m:.2f} m", fill="#0a765d", font=self.f_default)
        if not a.feasible:
            cv.create_text(15, 14, anchor="w", fill="#9b1c1c", font=self.f_bold,
                           text="✖ NOT FEASIBLE - sketch shows your full floor space for reference only")

    def check_custom(self, quiet=False):
        """'Check a ramp': a run in metres or a slope such as 1:12, tested against all three limits."""
        if self.inputs is None:
            if not quiet:
                messagebox.showwarning("Check your inputs", "Please fix the boxes marked with ⚠ first.", parent=self)
            return
        try:
            run = parse_run(self.vars["custom"].get(), self.inputs.height_m)
            r = calculate_at_run(self.inputs, self.limits, run)
        except ValueError as error:
            self.custom_result.set(f"⚠ {error}")
            return
        mark = "✔ FEASIBLE" if r.feasible else "✖ NOT FEASIBLE"
        self.custom_result.set(f"{mark}: {r.plain_status}\n"
                               f"Run {run:.2f} m, angle {r.angle_deg:.1f}°, steady {r.steady_n:.0f} N, "
                               f"peak {r.peak_n:.0f} N (limit {self.limits.max_peak_n:g} N), work {r.work_j:.0f} J")

    def _update_graphs(self):
        top, bottom = self.plot_force, self.plot_work
        top.clear()
        bottom.clear()
        for old_legend in list(self.figure.legends):      # figure-level legend from the previous drawing
            old_legend.remove()
        fs = max(8, self.base_size - 2)
        if self.inputs is None:
            top.text(.5, .5, "Fix the inputs marked with a warning sign to see the graph.",
                     ha="center", va="center", transform=top.transAxes, fontsize=fs)
            self.chart.draw_idle()
            return
        p, lim, a = self.inputs, self.limits, self.analysis
        # When the angle limit cannot fit in the floor space there are no qualifying runs; the graph
        # then shows what-if curves out to the run that WOULD be needed, so the reason is visible.
        what_if = not self.candidates
        rows = self.candidates or what_if_sweep(p, lim)
        x = [r.run_m for r in rows]
        top.plot(x, [r.steady_n for r in rows], color="#1f5fa8", ls="-", lw=2.2, label="Steady force (keep moving)")
        top.plot(x, [r.peak_n for r in rows], color="#c2410c", ls="--", lw=2.2, label="Peak force (get started)")
        top.axhline(lim.max_peak_n, color="#7f1d1d", ls=":", lw=2, label=f"Your peak limit ({lim.max_peak_n:g} N)")
        bottom.plot(x, [r.work_j for r in rows], color="#1f5fa8", lw=2.2, label="Mechanical work")
        for ax in (top, bottom):
            ax.axvline(p.max_run_m, color="#444444", ls="-.", lw=1.2, label="Your floor space" if ax is top else None)
            if a.feasible:
                ax.axvspan(a.x_required_m, p.max_run_m, color="#c9f1df", alpha=0.5,
                           label="Qualifying runs" if ax is top else None)
            elif what_if:
                needed = a.x_required_m or a.x_angle_m
                ax.axvline(needed, color="#7f1d1d", ls=":", lw=1.4,
                           label="Run that would be needed" if ax is top else None)
        if what_if:
            top.set_title("No run satisfies the angle limit within your floor space - curves shown to explain why",
                          fontsize=fs)
        # legend BELOW the plots so it never covers the curves
        handles, labels = top.get_legend_handles_labels()
        self.figure.legend(handles, labels, loc="lower center", ncol=3, fontsize=fs, frameon=False)
        top.set_ylabel("Force (N)", fontsize=fs)
        bottom.set_ylabel("Work (J)", fontsize=fs)
        bottom.set_xlabel("Horizontal run x (m)", fontsize=fs)
        for ax in (top, bottom):
            ax.grid(alpha=.25)
            ax.tick_params(labelsize=fs)
        self.figure.tight_layout(rect=(0, 0.14, 1, 1))
        self.chart.draw_idle()

    def _update_table(self, which):
        self.table_choice = which
        self.ramp_table.delete(*self.ramp_table.get_children())
        if self.inputs is None:
            self.table_label.set("Fix the inputs marked with a warning sign to see the table.")
            return
        rows = ([("", item) for item in self.candidates] if which == "candidates"
                else reference_slopes(self.inputs, self.limits))
        if which == "candidates" and not rows:
            self.table_label.set("No run satisfies the angle limit within your floor space, so there is nothing to list.")
            return
        self.table_label.set(f"{len(rows)} theoretical configurations; 'Feasible' means all three of your limits pass.")
        for ratio, r in rows:
            run_label = f"{r.run_m:.3f}" + (f" ({ratio})" if ratio else "")
            self.ramp_table.insert("", "end", values=(run_label, f"{r.angle_deg:.2f}",
                f"{r.steady_n:.3f}", f"{r.peak_n:.3f}", f"{r.work_j:.2f}", r.plain_status))

    # ------------------------------------------------------------------ files
    def _choose_file(self, filename, kind="csv", save=True):
        files = [("CSV files", "*.csv")] if kind == "csv" else [("PNG image", "*.png")]
        args = dict(parent=self, filetypes=files, title="Save file" if save else "Open file")
        if save:
            return filedialog.asksaveasfilename(defaultextension=f".{kind}", initialfile=filename, **args)
        return filedialog.askopenfilename(**args)

    def save_graph(self):
        path = self._choose_file("RampForce_graph.png", kind="png")
        if path:
            try:
                self.figure.savefig(path, dpi=180)
                self.status.set(f"Saved: {path}")
            except OSError as error:
                messagebox.showerror("Save failed", str(error), parent=self)

    def save_csv(self, kind):
        if kind == "comparison" and not self.reference_rows:
            messagebox.showwarning("No comparison", "Load a reference CSV first.", parent=self)
            return
        if kind != "comparison" and self.inputs is None:
            messagebox.showwarning("Check your inputs", "Please fix the boxes marked with ⚠ first.", parent=self)
            return
        if kind == "runs" and not self.candidates:
            messagebox.showinfo("Nothing to export", "No run satisfies the angle limit within your floor space, "
                                "so there are no candidate rows to export.", parent=self)
            return
        scenario = self.vars["scenario"].get().strip() or "scenario"
        path = self._choose_file(f"RampForce_{scenario}_{kind}.csv")
        if not path:
            return
        try:
            if kind == "runs":
                count = export_candidates(path, self.inputs, self.limits, scenario)
                self.status.set(f"Exported {count} candidate rows to {path}")
            elif kind == "summary":
                export_summary(path, self.inputs, self.limits, scenario)
                self.status.set(f"Saved summary: {path}")
            else:
                export_comparison(path, self.reference_rows)
                self.status.set(f"Saved reference comparison: {path}")
        except (OSError, ValueError) as error:
            messagebox.showerror("Export failed", str(error), parent=self)

    def import_refs(self):
        path = self._choose_file("", save=False)
        if path:
            self._load_refs(path)

    def _load_supplied(self):
        """The 10 supplied cases: from samples/ if present, otherwise from the copy built into datasets.py."""
        path = BASE / "samples" / "reference_cases_v2.csv"
        if path.exists():
            self._load_refs(path)
        else:
            self._show_references(compare_reference_text(SUPPLIED_REFERENCE_CSV))

    def _load_refs(self, path):
        try:
            rows = compare_references(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Reference CSV error", str(error), parent=self)
            return
        self._show_references(rows)

    def _show_references(self, rows):
        self.reference_rows = rows
        self.ref_table.delete(*self.ref_table.get_children())
        for r in rows:
            self.ref_table.insert("", "end", values=(r["case"], r["mode"],
                f'{r["ref_steady"]:.4f}', f'{r["calc_steady"]:.4f}',
                f'{r["steady_err"]:.6f}', f'{r["peak_err"]:.6f}', f'{r["work_err"]:.6f}'))
        n = len(rows)
        self.ref_label.set(f"{n} cases  |  MAE steady: {sum(r['steady_err'] for r in rows)/n:.8f} N  |  "
                           f"MAE peak: {sum(r['peak_err'] for r in rows)/n:.8f} N  |  "
                           f"MAE work: {sum(r['work_err'] for r in rows)/n:.8f} J")


def _enable_sharp_text_on_windows():
    """Without this, Windows blurs the whole window on high-resolution screens."""
    try:
        from ctypes import windll              # only exists on Windows
        windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass


if __name__ == "__main__":
    _enable_sharp_text_on_windows()
    RampForceApp().mainloop()
