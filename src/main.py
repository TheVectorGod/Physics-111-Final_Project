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
        super().__init__()
        self.title("RampForce — Inclined-Plane Push & Pull Planner")
        self.geometry("1220x780")
        self.minsize(980, 640)

        self.vars = {k: tk.StringVar(value=v) for k, v in DEFAULTS.items()}
        self.error_vars = {k: tk.StringVar() for k in FIELDS}
        self.entries = {}
        self.error_labels = {}

        self.text_size = 10
        self._after_id = None
        self.inputs = None
        self.limits = None
        self.analysis = None
        self.rows = []
        self.ref_rows = []
        self._wrap_labels = []
        self.fig = None

        self._fonts()
        self._style()
        self._build()
        self._bind_keys()

        for var in self.vars.values():
            var.trace_add("write", self._schedule_analysis)

        self.bind("<Configure>", lambda e: self._rewrap(e.width) if e.widget is self else None)
        self.run_analysis()
 
    # ------------------------------------------------------------------ fonts and style
    def _fonts(self):
        self.text_size = getattr(self, "text_size", 10)
        family = tkfont.nametofont("TkDefaultFont").actual("family")
        mono = tkfont.nametofont("TkFixedFont").actual("family")
        size = self.text_size
        self.fonts = {
            "body": tkfont.Font(root=self, family=family, size=size),
            "bold": tkfont.Font(root=self, family=family, size=size, weight="bold"),
            "header": tkfont.Font(root=self, family=family, size=size + 4, weight="bold"),
            "small": tkfont.Font(root=self, family=family, size=max(7, size - 1)),
            "mono": tkfont.Font(root=self, family=mono, size=size),
        }
        self._apply_sizes()
 
    def _apply_sizes(self):
        size = self.text_size
        sizes = {"body": size, "bold": size, "header": size + 4,
                 "small": max(7, size - 1), "mono": size}
        for name, font in self.fonts.items():
            font.configure(size=sizes[name])
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkFixedFont"):
            tkfont.nametofont(name).configure(size=size)
        style = ttk.Style(self)
        style.configure("Treeview", font=self.fonts["body"],
                        rowheight=self.fonts["body"].metrics("linespace") + 8)
        style.configure("Treeview.Heading", font=self.fonts["bold"])
 
    def change_text_size(self, delta):
        self.text_size = 10 if delta == 0 else max(8, min(24, self.text_size + delta))
        self._apply_sizes()
        self.run_analysis()                      
 
    def _style(self):
        if not hasattr(self, "fonts"):
            self._fonts()
        bg, fg, accent = "#f4f5f7", "#1f2933", "#1d4ed8"
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        self.configure(background=bg)
        style.configure(".", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TLabelframe", background=bg)
        style.configure("TLabelframe.Label", background=bg, foreground=fg, font=self.fonts["bold"])
        style.configure("TEntry", fieldbackground="#ffffff", padding=3)
        style.configure("TNotebook", background=bg)
        style.configure("TNotebook.Tab", padding=(12, 6), font=self.fonts["bold"])
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")])
        style.configure("TButton", padding=6)
        style.configure("Accent.TButton", background=accent, foreground="#ffffff", padding=6)
        style.map("Accent.TButton", background=[("active", "#1e40af"), ("pressed", "#1e3a8a")])
        style.configure("Treeview", fieldbackground="#ffffff", background="#ffffff")
        style.configure("Treeview.Heading", background="#e2e8f0", foreground=fg)
        style.configure("Header.TLabel", font=self.fonts["header"], foreground="#0f172a")
        style.configure("Title.TLabel", font=self.fonts["header"], foreground="#0f172a")
        style.configure("Hint.TLabel", font=self.fonts["small"], foreground="#4b5563")
        style.configure("Error.TLabel", font=self.fonts["small"], foreground="#b91c1c")
        style.configure("CardTitle.TLabel", font=self.fonts["small"], foreground="#374151")
        style.configure("CardValue.TLabel", font=self.fonts["header"], foreground="#0f172a")
        self._apply_sizes()
 
    def _bind_keys(self):
        def run_enter(_event=None):
            after_id = getattr(self, "_after_id", None)
            if after_id is not None:                 
                self.after_cancel(after_id)
                self._after_id = None
            self.run_analysis()

        def resizer(delta):
            def handler(_event=None):
                self.change_text_size(delta)
                return "break"
            return handler

        for seq in ("<Return>", "<KP_Enter>"):
            self.bind(seq, run_enter)
        for seq in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.bind(seq, resizer(1))
        for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.bind(seq, resizer(-1))
        for seq in ("<Control-0>", "<Control-KP_0>"):
            self.bind(seq, resizer(0))
 
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
        box = ttk.Frame(parent)
        box.pack(fill="both", expand=True)
        ids = [f"c{n}" for n in range(len(columns))]
        tree = ttk.Treeview(box, columns=ids, show="headings", selectmode="browse")
        for cid, col in zip(ids, columns):
            heading, width = col if isinstance(col, (tuple, list)) else (col, 110)
            tree.heading(cid, text=heading)
            tree.column(cid, width=width, minwidth=60, anchor="center", stretch=True)
        tree.tag_configure("ok", background="#e6f4ea")
        tree.tag_configure("bad", background="#fdecea")
        ybar = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
        xbar = ttk.Scrollbar(box, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        return tree
 
       @staticmethod
    def _text_box(parent, font):
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)

        text_widget = tk.Text(
            container,
            wrap="word",
            font=font,
            padx=10,
            pady=10,
            relief="flat",
            borderwidth=0,
            state="disabled"
        )

        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=text_widget.yview
        )

        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        text_widget.tag_configure(
            "step_heading",
            foreground="#1d4ed8",
            font=(font.actual("family"), font.actual("size"), "bold")
        )
        return text_widget
    @staticmethod
    def _set_text(widget, content):
               widget.configure(state="normal")
        widget.delete("1.0", "end")
        if content:
            lines = str(content).splitlines()
            for index, line in enumerate(lines):
                if index > 0:
                    widget.insert("end", "\n")

                if line.strip().upper().startswith("STEP"):
                    widget.insert("end", line, "step_heading")
                else:
                    widget.insert("end", line)
        widget.configure(state="disabled")
    def _rewrap(self, width):
        target = max(320, width - 380)
        for lbl in getattr(self, "_wrap_labels", []):
            if lbl.winfo_exists():
                lbl.configure(wraplength=target)
 
    # ------------------------------------------------------------------ layout
    def _build(self):
        top = ttk.Frame(self, padding=(12, 8))
        top.pack(fill="x")
        ttk.Label(top, text="RampForce", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="  Inclined-plane push/pull calculator (theoretical model only)",
                  style="Hint.TLabel").pack(side="left")

        right = ttk.Frame(top)
        right.pack(side="right")
        ttk.Label(right, text="Text size:").pack(side="left", padx=(0, 4))
        ttk.Button(right, text="A-", width=3, command=lambda: self.change_text_size(-1)).pack(side="left", padx=1)
        ttk.Button(right, text="A", width=3, command=lambda: self.change_text_size(0)).pack(side="left", padx=1)
        ttk.Button(right, text="A+", width=3, command=lambda: self.change_text_size(1)).pack(side="left", padx=1)
        ttk.Button(right, text="Export summary CSV", command=lambda: self.save_csv("summary")).pack(side="left", padx=(10, 0))

        body = ttk.Frame(self, padding=(12, 0, 12, 12))
        body.pack(fill="both", expand=True)
        self._build_inputs(body)

        self.notebook = ttk.Notebook(body)
        self.notebook.pack(side="left", fill="both", expand=True, padx=(10, 0))

        tabs = [
            ("Overview & verdict", self._build_overview),
            ("Sweep & graphs", self._build_comparison),
            ("How it was calculated", self._build_steps),
            ("Reference QA", self._build_references),
            ("Models & limits", self._build_models),
        ]
        for label, builder in tabs:
            page = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(page, text=label)
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
        card = ttk.Frame(parent, padding=10, relief="solid")
        card.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        ttk.Label(
            card,
            text=title,
            style="CardTitle.TLabel"
        ).pack(anchor="w")

        value = tk.StringVar(value="—")

        ttk.Label(
            card,
            textvariable=value,
            style="CardValue.TLabel"
        ).pack(anchor="w", pady=(5, 0))

        return value

 
    def _build_overview(self, page):
         # Status banner
        self.banner = tk.Frame(page, padx=12, pady=10)
        self.banner.pack(fill="x", pady=(0, 10))

        self.banner_icon = ttk.Label(self.banner, font=self.fonts["header"])
        self.banner_icon.pack(side="left", padx=(0, 10))

        banner_text = ttk.Frame(self.banner)
        banner_text.pack(side="left", fill="x", expand=True)

        self.banner_title = ttk.Label(
            banner_text, font=self.fonts["bold"]
        )
        self.banner_title.pack(anchor="w")

        self.banner_message = ttk.Label(
            banner_text, wraplength=700, justify="left"
        )
        self.banner_message.pack(anchor="w")

        # Result cards
        cards = ttk.Frame(page)
        cards.pack(fill="x", pady=5)

        self.card_vars = {
            "least_force": self._card(cards, "Least force"),
            "least_work": self._card(cards, "Least work"),
            "recommended_run": self._card(cards, "Recommended run"),
        }

        # Ramp drawing area
        ramp_frame = ttk.LabelFrame(page, text="Ramp illustration", padding=8)
        ramp_frame.pack(fill="both", expand=True, pady=8)

        self.ramp_canvas = tk.Canvas(
            ramp_frame,
            height=220,
            background="white",
            highlightthickness=1,
            highlightbackground="#d1d5db"
        )
        self.ramp_canvas.pack(fill="both", expand=True)

        # Custom run checker
        custom_frame = ttk.LabelFrame(
            page, text="Check a custom ramp run", padding=10
        )
        custom_frame.pack(fill="x", pady=5)

        ttk.Label(
            custom_frame,
            text="Enter a run in metres or a slope such as 1:12:"
        ).pack(anchor="w")

        custom_entry = ttk.Entry(
            custom_frame, textvariable=self.vars["custom"]
        )
        custom_entry.pack(fill="x", pady=5)
        custom_entry.bind("<Return>", self._on_check_return)

        ttk.Button(
            custom_frame,
            text="Check this ramp",
            command=self.check_custom
        ).pack(anchor="w")

        self.custom_result = tk.StringVar(value="")
        ttk.Label(
            custom_frame,
            textvariable=self.custom_result,
            wraplength=850,
            justify="left"
        ).pack(anchor="w", pady=(8, 0))

        self._show_banner(
            "warn",
            "⚠",
            "Waiting for analysis",
            "Enter your ramp details to see the results."
        )
 
    def _on_check_return(self, _event=None):
        self.check_custom()
        return "break"                           
 
    def _build_comparison(self, page):
        self.table_mode = tk.StringVar(value="runs")
        self.table_note = tk.StringVar(value="")
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Table shows:").pack(side="left")
        for text, value in (("Candidate runs", "runs"), ("Standard slopes (1:N)", "slopes")):
            ttk.Radiobutton(bar, text=text, value=value, variable=self.table_mode,
                            command=lambda: self._update_table(self.table_mode.get())
                            ).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Save graph (PNG)", command=self.save_graph).pack(side="right")
        ttk.Button(bar, text="Save candidates (CSV)",
                   command=lambda: self.save_csv("candidates")).pack(side="right", padx=6)

        self.fig = Figure(figsize=(8, 4.6), dpi=100, layout="constrained")
        self.plot_canvas = FigureCanvasTkAgg(self.fig, master=page)
        self.plot_canvas.get_tk_widget().pack(fill="both", expand=True)

        ttk.Label(page, textvariable=self.table_note, style="Hint.TLabel").pack(anchor="w", pady=(6, 2))
        holder = ttk.Frame(page)
        holder.pack(fill="x")
        self.ramp_table = self._table(holder, [
            ("Ramp", 90), ("Run (m)", 80), ("Angle (\u00b0)", 80), ("Steady (N)", 90),
            ("Peak (N)", 90), ("Work (J)", 90), ("Status", 260)])
        self.ramp_table.configure(height=7)
 
    def _build_steps(self, page):
    self.steps_text = self._text_box(
        page,
        self.fonts["body"]
    )

    self._set_text(
        self.steps_text,
        "Run an analysis to see the step-by-step calculations."
    )
 
    def _build_references(self, page):
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Button(bar, text="Load supplied 10 cases", command=self._load_supplied).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Import reference CSV...", command=self.import_refs).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Export comparison CSV...", command=lambda: self.save_csv("refs")).pack(side="left")

        self.ref_summary_var = tk.StringVar(
            value="Load the supplied 10 reference cases or import a CSV to check implementation accuracy."
        )
        summary_lbl = ttk.Label(page, textvariable=self.ref_summary_var, style="Hint.TLabel", wraplength=820, justify="left")
        summary_lbl.pack(anchor="w", pady=(0, 8))
        self._wrap_labels.append(summary_lbl)

        cols = (
            ("Case", 65),
            ("Mode", 85),
            ("Ref Steady (N)", 110),
            ("Calc Steady (N)", 115),
            ("Steady Err", 95),
            ("Ref Peak (N)", 105),
            ("Calc Peak (N)", 110),
            ("Peak Err", 95),
            ("Ref Work (J)", 105),
            ("Calc Work (J)", 110),
            ("Work Err", 95),
        )
        self.ref_table = self._table(page, cols)
 
    def _build_models(self, page):
        self.models_text = self._text_box(
            page,
            self.fonts["body"]
        )

        self.models_text.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=8
        )

        self._set_text(
            self.models_text,
            MODEL_TEXT
        )
 
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
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None

        inputs, limits, errors = self._read_values()
        self._show_field_errors(errors)
        if errors or inputs is None or limits is None:
            self.inputs = None
            self.limits = None
            self._clear_results()
            return

        try:
            analysis = analyze(inputs, limits)
            rows = sweep(inputs, limits)
        except Exception as exc:
            self.inputs = None
            self.limits = None
            self._clear_results()
            self._show_banner("bad", "\u2716", "Calculation error", str(exc))
            return

        self.inputs = inputs
        self.limits = limits
        self.analysis = analysis
        self.rows = rows

        icon, title, detail = verdict_text(inputs, limits, analysis)
        level = "ok" if analysis.feasible else "bad"
        self._show_banner(level, icon, title, detail)

        c = analysis.at_max
        card_vars = getattr(self, "card_vars", None)
        if isinstance(card_vars, dict):
            if analysis.feasible and analysis.at_min is not None:
                s = analysis.at_min
                self._fill(card_vars, {
                    "least_force": f"{c.steady_n:.1f} N (at {c.run_m:.2f} m)",
                    "least_work": f"{s.work_j:.0f} J (at {s.run_m:.2f} m)",
                    "recommended_run": f"{s.run_m:.2f} – {c.run_m:.2f} m",
                })
            else:
                needed = f"{analysis.x_required_m:.2f} m" if analysis.x_required_m is not None else "None"
                self._fill(card_vars, {
                    "least_force": f"{c.steady_n:.1f} N (at xmax)",
                    "least_work": f"{c.work_j:.0f} J (at xmax)",
                    "recommended_run": f"Needs {needed}",
                })

        steps = getattr(self, "steps_text", None)
        if steps is not None:
            self._set_text(steps, explain_steps(inputs, limits, analysis))

        self._draw_ramp()
        self._update_graphs()
        self._update_table(self.table_mode.get())
        if self.vars["custom"].get().strip():
            self.check_custom(quiet=True)
 
    @staticmethod
    def _fill(vars_, texts):
                if isinstance(vars_, tk.Variable):
            vars_.set("" if texts is None else str(texts))

        elif isinstance(vars_, dict):
            if isinstance(texts, dict):
                for key, variable in vars_.items():
                    if key in texts:
                        RampForceApp._fill(variable, texts[key])

        elif isinstance(vars_, (list, tuple)):
            if isinstance(texts, (list, tuple)):
                for variable, text in zip(vars_, texts):
                    RampForceApp._fill(variable, text)
 
    def _clear_results(self):
        self.analysis, self.rows = None, []
        self._show_banner("warn", "\u26a0", "Check your inputs",
                          "Fix the highlighted boxes to see results.")

        def blank(obj):
            if isinstance(obj, tk.Variable):
                obj.set("")
            elif isinstance(obj, dict):
                for value in obj.values():
                    blank(value)
            elif isinstance(obj, (list, tuple)):
                for value in obj:
                    blank(value)

        blank(getattr(self, "card_vars", None))          
        blank(getattr(self, "custom_result", None))      
        canvas = getattr(self, "ramp_canvas", None)      
        if canvas is not None:
            canvas.delete("all")
        steps = getattr(self, "steps_text", None)      
        if steps is not None:
            self._set_text(steps, "")
        self._update_table(self.table_mode.get())        
        self._update_graphs()                           
 
    def _show_banner(self, level, icon, title, text):
                background, foreground = LEVEL_COLORS.get(
            level,
            LEVEL_COLORS["warn"]
        )

        self.banner.configure(background=background)

        style = ttk.Style(self)

        style.configure(
            "BannerIcon.TLabel",
            background=background,
            foreground=foreground,
            font=self.fonts["header"]
        )

        style.configure(
            "BannerTitle.TLabel",
            background=background,
            foreground=foreground,
            font=self.fonts["bold"]
        )

        style.configure(
            "BannerMessage.TLabel",
            background=background,
            foreground=foreground,
            font=self.fonts["body"]
        )

        self.banner_icon.configure(
            text=icon,
            style="BannerIcon.TLabel"
        )

        self.banner_title.configure(
            text=title,
            style="BannerTitle.TLabel"
        )

        self.banner_message.configure(
            text=text,
            style="BannerMessage.TLabel"
        )
 
    # ------------------------------------------------------------------ drawings
    def _draw_ramp(self):
        # === Ace — RampForceApp._draw_ramp ===
        # GOAL: Draw scaled ramp geometry, x and xmax labels on Tk Canvas.
        # Keep function name/parameters/return contract unchanged.
        raise NotImplementedError("Ace: implement RampForceApp._draw_ramp")
 
    def check_custom(self, quiet=False):
        def show(text):
            var = getattr(self, "custom_result", None)
            if var is not None:
                var.set(text)

        i, l, errors = self._read_values()
        if errors:
            show("Fix the highlighted input boxes first.")
            return None
        try:
            run = parse_run(self.vars["custom"].get(), i.height_m)
        except ValueError as exc:
            show("Type a run in metres (for example 2.5) or a slope such as 1:12, then press Enter."
                 if quiet else f"\u26a0 {exc}")
            return None
        r = calculate_at_run(i, l, run)
        mark = lambda ok: "\u2714" if ok else "\u2716"
        show("\n".join([
            (f"{mark(r.feasible)} This ramp works within your limits." if r.feasible
             else f"{mark(False)} This ramp does not meet your limits.")
            + f"  (run {r.run_m:.2f} m, slope {r.angle_deg:.1f}\u00b0, ramp length {r.length_m:.2f} m)",
            f"{mark(r.space_ok)} Space: needs {r.run_m:.2f} m of floor; you have {i.max_run_m:.2f} m.",
            f"{mark(r.angle_ok)} Slope: {r.angle_deg:.1f}\u00b0 against your limit of {l.max_angle_deg:g}\u00b0.",
            f"{mark(r.force_ok)} First push: {r.peak_n:.0f} N against your limit of {l.max_peak_n:g} N.",
            f"Keeping it moving takes {r.steady_n:.0f} N; the total work is {r.work_j:.0f} J.",
        ]))
        return r
 
    def _update_graphs(self):
        fig = getattr(self, "fig", None)
        if fig is None:
            return
        a, i, l = (getattr(self, name, None) for name in ("analysis", "inputs", "limits"))
        size = self.text_size - 1
        fig.clear()
        if a is None or i is None or l is None:
            fig.text(0.5, 0.5, "Enter valid inputs to see the graphs.", ha="center", va="center",
                     fontsize=size + 1)
            self.plot_canvas.draw_idle()
            return
        rows = list(self.rows) if a.feasible else what_if_sweep(i, l)
        if not rows:
            fig.text(0.5, 0.5, "No data to plot.", ha="center", va="center", fontsize=size + 1)
            self.plot_canvas.draw_idle()
            return

        c_steady, c_peak, c_work, c_grey, c_bad = "#1d4ed8", "#c2410c", "#15803d", "#6b7280", "#b91c1c"
        x = [r.run_m for r in rows]
        ax_f, ax_w = fig.subplots(2, 1, sharex=True)
        ax_f.plot(x, [r.steady_n for r in rows], "-", color=c_steady, linewidth=2,
                  label="Steady force (keep moving)")
        ax_f.plot(x, [r.peak_n for r in rows], "--", color=c_peak, linewidth=2,
                  label="Peak force (get started)")
        ax_f.axhline(l.max_peak_n, color=c_grey, linestyle=":", linewidth=1.5,
                     label=f"Your force limit ({l.max_peak_n:g} N)")
        ax_w.plot(x, [r.work_j for r in rows], "-", color=c_work, linewidth=2, label="Work")
        for ax in (ax_f, ax_w):
            ax.axvline(i.max_run_m, color=c_grey, linestyle="-.", linewidth=1.2,
                       label=f"Available run xmax ({i.max_run_m:g} m)")
            if not a.feasible and a.x_required_m is not None:
                ax.axvline(a.x_required_m, color=c_bad, linestyle=":", linewidth=1.5,
                           label=f"Run needed ({a.x_required_m:.2f} m)")
        if a.feasible and a.x_required_m > x[0]:
            for ax in (ax_f, ax_w):
                ax.axvspan(x[0], a.x_required_m, color=c_bad, alpha=0.08, linewidth=0,
                           label="Breaks a limit" if ax is ax_f else None)
        if a.feasible:
            ax_f.plot([a.at_max.run_m], [a.at_max.steady_n], "o", color=c_steady, markersize=8,
                      label=f"Least force: {a.at_max.run_m:.2f} m")
            ax_w.plot([a.at_min.run_m], [a.at_min.work_j], "s", color=c_work, markersize=8,
                      label=f"Least work: {a.at_min.run_m:.2f} m")
            ax_f.set_title(f"Feasible: runs from {a.x_required_m:.2f} m to {i.max_run_m:.2f} m work",
                           fontsize=size + 1)
        else:
            ax_f.set_title("What-if curves: NO ramp meets all your limits (diagnostic only)",
                           fontsize=size + 1)
        ax_f.set_ylabel("Force (N)", fontsize=size)
        ax_w.set_ylabel("Work (J)", fontsize=size)
        ax_w.set_xlabel("Ramp run x (m)", fontsize=size)
        for ax in (ax_f, ax_w):
            ax.grid(True, alpha=0.3)
            ax.tick_params(labelsize=size)
            ax.legend(fontsize=max(6, size - 1), loc="best")
        self.plot_canvas.draw_idle()
 
    def _update_table(self, which):
        tree = getattr(self, "ramp_table", None)
        if tree is None:
            return
        tree.delete(*tree.get_children())
        a, i, l = (getattr(self, name, None) for name in ("analysis", "inputs", "limits"))
        if a is None or i is None or l is None:
            self.table_note.set("")
            return
        if which in ("slopes", "standard", "reference"):
            entries = list(reference_slopes(i, l))
            self.table_note.set("Standard slopes 1:N (run = N \u00d7 height). \u2714 means all three limits are met.")
        else:
            rows = list(self.rows) if a.feasible else what_if_sweep(i, l)
            entries = [(f"Run {n}", r) for n, r in enumerate(rows, 1)]
            if a.feasible:
                self.table_note.set(f"{len(rows)} candidate runs from the angle-limit run to xmax. "
                                    "\u2714 means all three limits are met.")
            else:
                self.table_note.set("No ramp meets all limits. These what-if runs are diagnostic only.")
        for label, r in entries:
            icon = "\u2714" if r.feasible else "\u2716"
            tree.insert("", "end", tags=("ok" if r.feasible else "bad",), values=(
                label, f"{r.run_m:.2f}", f"{r.angle_deg:.1f}", f"{r.steady_n:.1f}",
                f"{r.peak_n:.1f}", f"{r.work_j:.0f}", f"{icon} {r.plain_status}"))
 
    # ------------------------------------------------------------------ files
    def _choose_file(self, filename, kind="csv", save=True):
        if kind == "png":
            filetypes = [("PNG image", "*.png"), ("All files", "*.*")]
            defaultext = ".png"
        else:
            filetypes = [("CSV file", "*.csv"), ("All files", "*.*")]
            defaultext = ".csv"

        if save:
            return filedialog.asksaveasfilename(
                parent=self,
                initialfile=filename,
                defaultextension=defaultext,
                filetypes=filetypes,
            )
        return filedialog.askopenfilename(
            parent=self,
            initialfile=filename,
            filetypes=filetypes,
        )
 
    def save_graph(self):
        if self.fig is None:
            messagebox.showwarning("No graph", "Run a valid analysis before saving the graph.", parent=self)
            return
        scen = self.vars["scenario"].get().strip() or "S01"
        path = self._choose_file(f"{scen}_rampforce_plot.png", kind="png", save=True)
        if not path:
            return
        try:
            self.fig.savefig(path, dpi=150, bbox_inches="tight")
            messagebox.showinfo("Graph saved", f"Saved plot image to:\n{path}", parent=self)
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save graph:\n{exc}", parent=self)
 
    def save_csv(self, kind):
        scen = self.vars["scenario"].get().strip() or "S01"
        if kind == "refs":
            if not self.ref_rows:
                messagebox.showwarning("No reference data", "Load or import reference cases first.", parent=self)
                return
            path = self._choose_file(f"{scen}_reference_comparison.csv", kind="csv", save=True)
            if not path:
                return
            try:
                export_comparison(path, self.ref_rows)
                messagebox.showinfo("CSV saved", f"Saved reference comparison to:\n{path}", parent=self)
            except (OSError, ValueError) as exc:
                messagebox.showerror("Export failed", str(exc), parent=self)
            return

        inputs, limits, errors = self._read_values()
        if errors or inputs is None or limits is None:
            messagebox.showwarning("Invalid inputs", "Fix the highlighted input errors before exporting.", parent=self)
            return

        default_name = f"{scen}_summary.csv" if kind == "summary" else f"{scen}_candidates.csv"
        path = self._choose_file(default_name, kind="csv", save=True)
        if not path:
            return
        try:
            if kind == "summary":
                export_summary(path, inputs, limits, scen)
                messagebox.showinfo("CSV saved", f"Saved scenario summary to:\n{path}", parent=self)
            else:
                count = export_candidates(path, inputs, limits, scen)
                messagebox.showinfo("CSV saved", f"Saved {count} candidate rows to:\n{path}", parent=self)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
 
    def import_refs(self):
        path = self._choose_file("reference_cases.csv", kind="csv", save=False)
        if path:
            self._load_refs(path)
 
    def _load_supplied(self):
        sample_path = BASE / "samples" / "reference_cases.csv"
        if sample_path.is_file():
            self._load_refs(sample_path)
            return
        try:
            rows = compare_reference_text(SUPPLIED_REFERENCE_CSV)
        except ValueError as exc:
            messagebox.showerror("Reference error", str(exc), parent=self)
            return
        self._show_references(rows)
 
    def _load_refs(self, path):
        try:
            rows = compare_references(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not load reference CSV", str(exc), parent=self)
            return
        self._show_references(rows)
 
    def _show_references(self, rows):
        self.ref_rows = rows
        for item in self.ref_table.get_children():
            self.ref_table.delete(item)

        for r in rows:
            self.ref_table.insert("", "end", values=(
                r["case"],
                r["mode"],
                f"{r['ref_steady']:.3f}",
                f"{r['calc_steady']:.3f}",
                f"{r['steady_err']:.6f}",
                f"{r['ref_peak']:.3f}",
                f"{r['calc_peak']:.3f}",
                f"{r['peak_err']:.6f}",
                f"{r['ref_work']:.3f}",
                f"{r['calc_work']:.3f}",
                f"{r['work_err']:.6f}",
            ))

        n = len(rows)
        mae_steady = sum(r["steady_err"] for r in rows) / n
        mae_peak = sum(r["peak_err"] for r in rows) / n
        mae_work = sum(r["work_err"] for r in rows) / n
        self.ref_summary_var.set(
            f"Loaded {n} reference cases — Mean Absolute Error: "
            f"Steady = {mae_steady:.6f} N, Peak = {mae_peak:.6f} N, Work = {mae_work:.6f} J "
            "(implementation QA against declared equations)."
        )
 
 
def _enable_sharp_text_on_windows():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
 
 
if __name__ == "__main__":
    _enable_sharp_text_on_windows()
    RampForceApp().mainloop()
