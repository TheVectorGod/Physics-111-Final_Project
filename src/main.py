"""RampForce desktop interface. Run this file directly.
Keep main.py, physics.py, datasets.py and explain.py together.
Install Matplotlib once in your Python environment: python -m pip install matplotlib.
No other project files are required.
"""
from __future__ import annotations

from pathlib import Path
import sys
import traceback

# Load the matching support modules from the folder containing this main.py,
# even when an IDE or another tool launches this script from a different folder.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) in sys.path:
    sys.path.remove(str(APP_DIR))
sys.path.insert(0, str(APP_DIR))

if __name__ == "__main__":
    print(f"Starting RampForce: {Path(__file__).resolve()}", flush=True)
    print(f"Python interpreter: {sys.executable}", flush=True)


def _report_startup_error(error: Exception) -> None:
    """Display startup failures even when main.py is opened by double-clicking on Windows."""
    folder = Path(__file__).resolve().parent
    log = folder / "RampForce_startup_error.log"
    details = traceback.format_exc()
    try:
        log.write_text(details, encoding="utf-8")
    except OSError:
        pass

    if isinstance(error, ModuleNotFoundError) and error.name == "matplotlib":
        suggestion = ("Matplotlib is missing. Install it in the Python environment running RampForce. "
                      "In PowerShell, run:\n"
                      f'& "{sys.executable}" -m pip install matplotlib')
    elif isinstance(error, ModuleNotFoundError) and error.name in ("tkinter", "_tkinter"):
        suggestion = ("Tkinter is missing from this Python installation. Install or repair "
                      "standard Python with Tcl/Tk support.")
    elif isinstance(error, (ImportError, ModuleNotFoundError)) and (
        any(name in str(error) for name in ("physics", "datasets", "explain"))
        or "cannot import name" in str(error)
    ):
        suggestion = ("Keep the matching main.py, physics.py, datasets.py, and explain.py "
                      "together in the same extracted folder. Do not mix older versions.")
    else:
        suggestion = ("Check your Python installation and dependencies, then read the "
                      "startup log for the complete error.")

    message = (f"RampForce could not start.\n\n{type(error).__name__}: {error}\n\n"
               f"{suggestion}\n\nError log: {log}")
    print(message, file=sys.stderr)
    try:
        # Tkinter is bundled with most standard Python installations on Windows.
        import tkinter as startup_tk
        from tkinter import messagebox as startup_messagebox
        root = startup_tk.Tk()
        root.withdraw()
        try:
            startup_messagebox.showerror("RampForce — startup problem", message, parent=root)
        finally:
            root.destroy()
    except Exception:
        # If Tcl/Tk itself is unavailable, stderr and the log still give diagnostics.
        pass


try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter import font as tkfont

    if __name__ == "__main__":
        print("Tkinter imported; loading Matplotlib...", flush=True)
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    if __name__ == "__main__":
        print("Matplotlib imported; loading RampForce modules...", flush=True)
    from physics import (Inputs, PlanningLimits, analyze, calculate_at_run, field_errors, parse_run,
                         release_note, graph_samples)
    from datasets import (SUPPLIED_REFERENCE_CSV, compare_reference_text, compare_references,
                          export_ramp_comparison, export_comparison, export_summary)
    from explain import explain_steps, verdict_text
except Exception as exc:
    if __name__ == "__main__":
        _report_startup_error(exc)
        raise SystemExit(1) from None
    raise

FIELDS = {
    "load": "Cargo mass (kg)", "carrier": "Sled/cart mass (kg)",
    "height": "Platform height (m)", "max_run": "Available run xmax (m)",
    "mu_k": "Kinetic friction μk", "mu_s": "Static friction μs",
    "radius": "Wheel radius (cm)", "arm": "Rolling arm b (mm)",
    "fmax": "Peak-force limit (N)", "angle": "Angle limit (°)",
    "accel": "Assumed acceleration (m/s²)",
    "proposed": "Proposed horizontal run (m or 1:N)",
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
    "proposed": "Your existing or planned ramp run. Enter metres (2.5) or slope (1:12). A proposed ramp may fail the limits.",
}
DEFAULTS = {
    "scenario": "S01", "mode": "SLIDING", "load": "30", "carrier": "5",
    "height": "0.60", "max_run": "3.00", "mu_k": "0.30", "mu_s": "0.40",
    "radius": "10", "arm": "2", "fmax": "222", "angle": "20",
    "accel": "0.20", "proposed": "2.50",
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
Graph points only draw smooth curves, NOT optimization candidates or measurements.
Directly compare the proposed, least-steady-force, and least-work configurations.

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
    def __init__(self, defer_analysis=False):
        super().__init__()
        if __name__ == "__main__":
            print("Tk root created; building interface...", flush=True)
        self.title("RampForce | Inclined-Plane Analysis")
        # never ask for more than the screen offers (many laptops are only 768 px tall)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(1250, max(320, sw - 40)), min(790, max(240, sh - 90))
        self.minsize(min(900, width), min(600, height))
        self.geometry(f"{width}x{height}+{max(0, (sw-width)//2)}+{max(0, (sh-height)//2)}")
        self.vars = {key: tk.StringVar(value=value) for key, value in DEFAULTS.items()}
        self.error_vars = {key: tk.StringVar() for key in FIELDS}
        self.entries, self.error_labels = {}, {}
        self.status = tk.StringVar(value="Ready")
        self.inputs = self.limits = self.analysis = None
        self.proposed_run = None
        self.proposed_result = None
        self.compare_rows = []
        self.reference_rows = []
        self.diagram_choice = tk.StringVar(value="Proposed ramp")
        self.base_size = 11
        self.style = None
        self._after_id = None
        self._wrap_labels = []
        self._fonts()
        self._style()
        self._build()
        self._bind_keys()
        if defer_analysis:
            self._show_banner("warn", "…", "Loading RampForce", "Preparing the initial analysis.")
        else:
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

    def _rewrap(self, width, page=None):
        """Update only this page and only if the wrap width actually changes."""
        for label, margin in self._wrap_labels:
            if page is not None and label is not page and not str(label).startswith(str(page) + "."):
                continue
            target = max(width - margin, 200)
            if str(label.cget("wraplength")) != str(target):
                label.configure(wraplength=target)

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
            ("Comparison", self._build_comparison),
            ("Steps", self._build_steps),
            ("References", self._build_references),
            ("Models", self._build_models),
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
        for key in ("load", "carrier", "height", "max_run", "proposed"):
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
        # A scrollable overview prevents diagram/labels from being clipped on small screens.
        holder = ttk.Frame(page)
        holder.pack(fill="both", expand=True)
        scroller = tk.Canvas(holder, highlightthickness=0)
        side = ttk.Scrollbar(holder, orient="vertical", command=scroller.yview)
        scroller.configure(yscrollcommand=side.set)
        side.pack(side="right", fill="y")
        scroller.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(scroller, padding=(1, 1, 9, 2))
        slot = scroller.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _: scroller.configure(scrollregion=scroller.bbox("all")))
        scroller.bind("<Configure>", lambda e: scroller.itemconfigure(slot, width=e.width))
        self.overview_scroller = scroller
        def scroll_overview(event):
            if getattr(event, "num", 0) == 4:
                units = -1
            elif getattr(event, "num", 0) == 5:
                units = 1
            else:
                units = -1 if event.delta > 0 else 1
            scroller.yview_scroll(units, "units")
        def enable_wheel(_):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                scroller.bind_all(seq, scroll_overview)
        def disable_wheel(_):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                scroller.unbind_all(seq)
        scroller.bind("<Enter>", enable_wheel)
        scroller.bind("<Leave>", disable_wheel)
        page = inner
        self.summary, self.explain_text, self.icon_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.banner = tk.Frame(page, highlightthickness=2, padx=12, pady=8)
        self.banner.pack(fill="x", pady=(0, 6))
        self.banner.columnconfigure(1, weight=1)
        self.banner_icon = tk.Label(self.banner, textvariable=self.icon_var, font=self.f_icon, width=2)
        self.banner_title = tk.Label(self.banner, textvariable=self.summary, font=self.f_verdict, anchor="w")
        self.banner_text = tk.Label(self.banner, textvariable=self.explain_text, justify="left", anchor="w",
                                    font=self.f_default)
        self.banner_icon.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        self.banner_title.grid(row=0, column=1, sticky="ew")
        self.banner_text.grid(row=1, column=1, sticky="ew")

        cards = ttk.Frame(page)
        cards.pack(fill="x", pady=(0, 5))
        cards.columnconfigure((0, 1), weight=1, uniform="cards")
        box1, self.card_force = self._card(cards, "Least-steady-force feasible ramp")
        box2, self.card_work = self._card(cards, "Least-modeled-work feasible ramp")
        box1.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        box2.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        self.proposed_overview = tk.StringVar()
        proposed_label = ttk.Label(page, textvariable=self.proposed_overview, justify="left", style="Hint.TLabel")
        proposed_label.pack(anchor="w", fill="x", pady=(2, 4))
        self.details = tk.StringVar()
        details = ttk.Label(page, textvariable=self.details, justify="left", style="Hint.TLabel")
        details.pack(anchor="w", fill="x")

        toolbar = ttk.Frame(page)
        toolbar.pack(fill="x", pady=(6, 0))
        ttk.Label(toolbar, text="Show ramp diagram:").pack(side="left")
        ttk.Combobox(toolbar, textvariable=self.diagram_choice, state="readonly",
                     values=["Proposed ramp", "Least-force ramp", "Least-work ramp"], width=22).pack(side="left", padx=7)
        self.diagram_choice.trace_add("write", lambda *_: self._draw_ramp())
        self.canvas = tk.Canvas(page, bg="white", height=210, highlightthickness=1,
                                highlightbackground="#b6c3d1")
        self.canvas.pack(fill="x", expand=False, pady=(6, 4))
        self.canvas.bind("<Configure>", lambda _: self._draw_ramp())
        self.custom_result = tk.StringVar()
        custom_label = ttk.Label(page, textvariable=self.custom_result, justify="left")
        custom_label.pack(anchor="w", fill="x", pady=(0, 3))
        self._wrap_labels += [(self.banner_text, 140), (proposed_label, 40),
                              (details, 40), (custom_label, 40)]
        page.bind("<Configure>", lambda e, owner=page: self._rewrap(e.width, owner), add="+")


    def _on_check_return(self, _event=None):
        self.check_custom()
        return "break"                          # stop Enter from also re-running the whole analysis

    def _build_comparison(self, page):
        # A fixed-height graph and a scrollable comparison prevent the table being
        # pushed below the visible screen on laptops.
        holder = ttk.Frame(page)
        holder.pack(fill="both", expand=True)
        scroll = tk.Canvas(holder, highlightthickness=0)
        vbar = ttk.Scrollbar(holder, orient="vertical", command=scroll.yview)
        scroll.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        scroll.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(scroll, padding=(1, 1, 9, 8))
        window_id = scroll.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda e: scroll.itemconfigure(window_id, width=e.width))
        self.comparison_scroller = scroll
        def wheel_scroll(event):
            step = (-1 if event.delta > 0 else 1) if not getattr(event, "num", 0) else (-1 if event.num == 4 else 1)
            scroll.yview_scroll(step, "units")
        def wheel_in(_):
            for name in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                scroll.bind_all(name, wheel_scroll)
        def wheel_out(_):
            for name in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                scroll.unbind_all(name)
        scroll.bind("<Enter>", wheel_in)
        scroll.bind("<Leave>", wheel_out)
        page = body
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, 3))
        ttk.Label(bar, text="Direct comparison: proposed / least force / least work").pack(side="left")
        ttk.Button(bar, text="Save graph", command=self.save_graph).pack(side="right", padx=(5, 0))
        ttk.Button(bar, text="Export comparison CSV", command=lambda: self.save_csv("ramp_comparison")).pack(side="right")
        self.figure = Figure(figsize=(7, 4), dpi=90)
        self.chart = FigureCanvasTkAgg(self.figure, master=page)
        self.chart.get_tk_widget().configure(height=330)
        self.chart.get_tk_widget().pack(fill="x", expand=False)
        self.plot_force = self.figure.add_subplot(211)
        self.plot_work = self.figure.add_subplot(212, sharex=self.plot_force)
        self.comparison_summary = tk.StringVar(value="Enter valid parameters to compare ramps.")
        compare_label = ttk.Label(page, textvariable=self.comparison_summary,
                                  justify="left", wraplength=680, style="Hint.TLabel")
        compare_label.pack(fill="x", pady=(4, 3))
        self._wrap_labels.append((compare_label, 40))
        self.table_label = tk.StringVar()
        ttk.Label(page, textvariable=self.table_label, style="Hint.TLabel").pack(anchor="w")
        cols = [("role", "Configuration", 155), ("run", "Run (m)", 88),
                ("angle", "Angle (°)", 90), ("length", "Length (m)", 98),
                ("steady", "Steady (N)", 108), ("peak", "Peak (N)", 108),
                ("work", "Work (J)", 104), ("status", "Constraint status", 200)]
        self.ramp_table = self._table(page, cols)
        self.ramp_table.configure(height=3)
        page.bind("<Configure>", lambda e, owner=page: self._rewrap(e.width, owner), add="+")


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
        page.bind("<Configure>", lambda e, owner=page: self._rewrap(e.width, owner), add="+")

    def _build_models(self, page):
        text = self._text_box(page, self.f_fixed)
        self._set_text(text, MODEL_TEXT)

    # ------------------------------------------------------------------ reading the boxes
    def _read_values(self):
        """Parse all parameters, including the proposed run. Returns inputs, limits, errors."""
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
            self.proposed_run = None
            return None, None, errors
        extra = ({"mu_k": values["mu_k"], "mu_s": values["mu_s"]} if mode == "SLIDING"
                 else {"wheel_radius_cm": values["radius"], "roll_arm_mm": values["arm"]})
        inputs = Inputs(mode=mode, load_kg=values["load"], carrier_kg=values["carrier"],
                        height_m=values["height"], max_run_m=values["max_run"], **extra)
        limits = PlanningLimits(values["fmax"], values["angle"], values["accel"])
        errors.update(field_errors(inputs, limits))
        try:
            self.proposed_run = parse_run(self.vars["proposed"].get(), inputs.height_m)
        except ValueError as exc:
            errors["proposed"] = str(exc)
            self.proposed_run = None
        return inputs, limits, errors


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
        if errors or inputs is None or limits is None or self.proposed_run is None:
            self._clear_results()
            return
        try:
            a = analyze(inputs, limits)
            proposed = calculate_at_run(inputs, limits, self.proposed_run)
        except (ValueError, ArithmeticError) as exc:
            self._clear_results()
            self._show_banner("bad", "✖", "Calculation error", str(exc))
            return

        self.inputs, self.limits, self.analysis = inputs, limits, a
        self.proposed_result = proposed
        self.compare_rows = [("Proposed ramp", proposed)]
        if a.feasible:
            self.compare_rows.extend([("Least-force ramp", a.at_max),
                                      ("Least-work ramp", a.at_min)])
        icon, title, text = verdict_text(inputs, limits, a)
        self._show_banner("ok" if a.feasible else "bad", icon, title, text)

        def values(r):
            return [f"{r.run_m:.3f} m", f"{r.angle_deg:.2f}°", f"{r.steady_n:.2f} N",
                    f"{r.peak_n:.2f} N", f"{r.work_j:.2f} J"]
        if a.feasible:
            self._fill(self.card_force, values(a.at_max))
            self._fill(self.card_work, values(a.at_min))
        else:
            self._fill(self.card_force, ["Not available"] + ["—"] * 4)
            self._fill(self.card_work, ["Not available"] + ["—"] * 4)

        self.proposed_overview.set(
            f"Proposed ramp — x={proposed.run_m:.3f} m, θ={proposed.angle_deg:.2f}°, "
            f"steady={proposed.steady_n:.2f} N, peak={proposed.peak_n:.2f} N, "
            f"work={proposed.work_j:.2f} J — {proposed.status}.")
        self.details.set(f"Available ground space: {inputs.max_run_m:.2f} m. "
                         + (f"Feasible run interval: {a.x_required_m:.3f}–{inputs.max_run_m:.3f} m. "
                            if a.feasible else "No qualifying run within this space. ")
                         + release_note(inputs, proposed))
        self.check_custom(quiet=True)
        self._update_comparison_summary()
        self._draw_ramp()
        self._update_graphs()
        self._update_table()
        self._set_text(self.steps_text, explain_steps(inputs, limits, a, self.proposed_run))
        self.status.set(f"{self.vars['scenario'].get() or 'Scenario'}: direct ramp comparison (model estimates, not measurements).")


    @staticmethod
    def _fill(vars_, texts):
        for var, text in zip(vars_, texts):
            var.set(text)

    def _clear_results(self):
        """On invalid inputs, clear ALL stale results and disable valid-only exporting."""
        self.inputs = self.limits = self.analysis = None
        self.proposed_result = None
        self.compare_rows = []
        self._show_banner("warn", "!", "Check your inputs",
                          "Correct the highlighted fields before analyzing or exporting.")
        self._fill(self.card_force, ["—"] * 5)
        self._fill(self.card_work, ["—"] * 5)
        self.proposed_overview.set("")
        self.details.set("")
        self.custom_result.set("")
        self.comparison_summary.set("Correct the input values to see a comparison.")
        self._draw_ramp()
        self._update_graphs()
        self._update_table()
        self._set_text(self.steps_text, "Fix the highlighted inputs to display calculations.")
        self.status.set("Invalid inputs: previous results cleared.")


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
        """Draw dimensioned, scale-correct ramp geometry with all labels inside canvas."""
        cv = getattr(self, "canvas", None)
        if cv is None:
            return
        cv.delete("all")
        if self.analysis is None or self.proposed_result is None:
            return
        w, ht = max(cv.winfo_width(), 400), max(cv.winfo_height(), 175)
        a, p = self.analysis, self.inputs
        choice = self.diagram_choice.get()
        if choice == "Least-force ramp" and a.feasible:
            r, subtitle = a.at_max, "Least-force feasible ramp"
        elif choice == "Least-work ramp" and a.feasible:
            r, subtitle = a.at_min, "Least-work feasible ramp"
        else:
            r, subtitle = self.proposed_result, "Proposed ramp"
        if choice != "Proposed ramp" and not a.feasible:
            subtitle += " unavailable; showing proposed ramp"

        x0, floor = 75, ht - 66
        scale = min((w - 195) / max(r.run_m, p.max_run_m), (ht - 135) / p.height_m)
        scale = max(scale, .01)
        x1, xmax1 = x0 + r.run_m * scale, x0 + p.max_run_m * scale
        y1 = floor - p.height_m * scale
        status_color = "#16734c" if r.feasible else "#ad3030"
        cv.create_text(12, 8, anchor="nw", font=self.f_bold,
                       text=f"{subtitle}  |  {'FEASIBLE' if r.feasible else 'NOT FEASIBLE'}",
                       fill=status_color)
        cv.create_text(12, 30, anchor="nw", font=self.f_default,
                       text=f"L={r.length_m:.2f} m    θ={r.angle_deg:.1f}°    x={r.run_m:.2f} m",
                       fill="#26384b")
        cv.create_line(45, floor, min(w - 10, max(x1, xmax1) + 22), floor,
                       fill="#627184", width=2)
        cv.create_polygon(x0, floor, x1, floor, x1, y1,
                          fill="#def4ed" if r.feasible else "#fbe6e6", outline="")
        cv.create_line(x0, floor, x1, y1, fill="#135b95", width=3)
        cv.create_line(x1, y1, x1, floor, fill="#287874", width=2)
        cv.create_text(min(x1 + 7, w - 55), (floor + y1) / 2, text=f"h={p.height_m:g} m",
                       anchor="w", font=self.f_default, fill="#204a47")
        # Both dimension labels remain within the canvas, including narrow laptop windows.
        cv.create_line(x0, floor + 12, x1, floor + 12, arrow="both", fill="#b3651c")
        cv.create_text((x0 + x1) / 2, floor + 24, text=f"x = {r.run_m:.2f} m",
                       font=self.f_default, fill="#925118")
        cv.create_line(x0, floor + 37, xmax1, floor + 37, arrow="both", fill="#0e7363")
        cv.create_text((x0 + xmax1) / 2, floor + 50, text=f"xmax = {p.max_run_m:.2f} m",
                       font=self.f_default, fill="#0e7363")


    def check_custom(self, quiet=False):
        """The proposed-run input is evaluated automatically with the full analysis."""
        if self.proposed_result is None or self.inputs is None:
            if not quiet:
                self.custom_result.set("Correct the highlighted inputs first.")
            return None
        r = self.proposed_result
        self.custom_result.set(
            f"Proposed ramp constraints — Space: {'PASS' if r.space_ok else 'FAIL'}, "
            f"Angle: {'PASS' if r.angle_ok else 'FAIL'}, "
            f"Peak force: {'PASS' if r.force_ok else 'FAIL'}. "
            f"{'All limits satisfied.' if r.feasible else r.plain_status}")
        return r


    def _update_graphs(self):
        top, bottom = self.plot_force, self.plot_work
        top.clear()
        bottom.clear()
        for item in list(self.figure.legends):
            item.remove()
        fontsize = max(8, self.base_size - 2)
        if self.inputs is None or self.proposed_result is None:
            top.text(.5, .5, "Enter valid inputs to display the graphs.",
                     ha="center", va="center", transform=top.transAxes, fontsize=fontsize)
            self.chart.draw_idle()
            return
        p, lim, a = self.inputs, self.limits, self.analysis
        # These points DRAW continuous curves. They are never ranked or exported as configurations.
        plot_points = graph_samples(p, lim, self.proposed_run)
        xs = [r.run_m for r in plot_points]
        top.plot(xs, [r.steady_n for r in plot_points], color="#225b94", lw=2,
                 label="Steady force")
        top.plot(xs, [r.peak_n for r in plot_points], color="#bb5426", lw=2,
                 ls="--", label="Estimated peak force")
        top.axhline(lim.max_peak_n, color="#7d3131", ls=":", lw=1.4,
                    label="Peak-force planning limit")
        bottom.plot(xs, [r.work_j for r in plot_points], color="#225b94", lw=2,
                    label="Modeled work")
        for ax in (top, bottom):
            ax.axvline(p.max_run_m, color="#5a626b", ls="-.", lw=1.2,
                       label="Available run" if ax is top else None)
            if a.feasible:
                ax.axvspan(a.x_required_m, p.max_run_m, color="#c5e9d8", alpha=.5,
                           label="Feasible interval" if ax is top else None)
            elif a.x_required_m is not None and a.x_required_m <= 200:
                ax.axvline(a.x_required_m, color="#9e2b2b", ls=":", lw=1.1,
                           label="Required run beyond available space" if ax is top else None)
        for name, r, color, ls in [
            ("Proposed", self.proposed_result, "#5e3aa6", "-"),
            ("Least force", a.at_max if a.feasible else None, "#237a46", "--"),
            ("Least work", a.at_min if a.feasible else None, "#c47720", ":")]:
            if r is None:
                continue
            top.axvline(r.run_m, color=color, ls=ls, lw=1.3, label=name)
            bottom.axvline(r.run_m, color=color, ls=ls, lw=1.1)
        if not a.feasible:
            top.set_title("No feasible ramp under these planning limits", fontsize=fontsize)
        top.set_ylabel("Force (N)", fontsize=fontsize)
        bottom.set_ylabel("Work (J)", fontsize=fontsize)
        bottom.set_xlabel("Horizontal run x (m)", fontsize=fontsize)
        for ax in (top, bottom):
            ax.grid(alpha=.22)
            ax.tick_params(labelsize=fontsize)
        handles, labels = top.get_legend_handles_labels()
        self.figure.legend(handles, labels, loc="lower center", ncol=3,
                           fontsize=max(7, fontsize-1), frameon=False)
        self.figure.tight_layout(rect=(0, .12, 1, 1))
        self.chart.draw_idle()


    def _update_table(self):
        self.ramp_table.delete(*self.ramp_table.get_children())
        if self.inputs is None:
            self.table_label.set("No valid ramp input: previous comparison cleared.")
            return
        self.table_label.set(f"{len(self.compare_rows)} directly calculated configurations; "
                             "only feasible alternatives are recommended.")
        for role, r in self.compare_rows:
            self.ramp_table.insert("", "end", values=(
                role, f"{r.run_m:.3f}", f"{r.angle_deg:.2f}",
                f"{r.length_m:.3f}", f"{r.steady_n:.3f}", f"{r.peak_n:.3f}",
                f"{r.work_j:.3f}", r.status))


    def _update_comparison_summary(self):
        if self.proposed_result is None or self.analysis is None:
            self.comparison_summary.set("Enter valid inputs to compare ramps.")
            return
        proposed, a = self.proposed_result, self.analysis
        if not a.feasible:
            self.comparison_summary.set(
                "Proposed ramp: " + proposed.status + ". "
                "No feasible alternatives satisfy the chosen angle, force, and space limits. "
                "A force/work improvement cannot be recommended for this scenario.")
            return
        best_f, best_w = a.at_max, a.at_min
        force_saved = proposed.steady_n - best_f.steady_n
        pct = 100 * force_saved / proposed.steady_n if proposed.steady_n > 0 else 0.0
        work_saved = proposed.work_j - best_w.work_j
        proposed_note = "feasible" if proposed.feasible else "NOT feasible under the selected limits"
        self.comparison_summary.set(
            f"Proposed ramp ({proposed_note}) vs. least-force ramp: "
            f"Δsteady force = {force_saved:+.2f} N ({pct:+.2f}% reduction relative to proposed); "
            f"Δwork (alternative − proposed) = {best_f.work_j - proposed.work_j:+.2f} J. "
            f"Least-work alternative: x={best_w.run_m:.3f} m; "
            f"work saved vs. proposed = {work_saved:+.2f} J. "
            "A negative saving means the alternative increases that quantity. "
            "All results are theoretical; an infeasible proposed ramp is only a comparison baseline.")

    # ------------------------------------------------------------------ files
    def _choose_file(self, filename, kind="csv", save=True):
        files = [("CSV files", "*.csv")] if kind == "csv" else [("PNG image", "*.png")]
        args = dict(parent=self, filetypes=files, title="Save file" if save else "Open file")
        if save:
            return filedialog.asksaveasfilename(defaultextension=f".{kind}", initialfile=filename, **args)
        return filedialog.askopenfilename(**args)

    def save_graph(self):
        # Revalidate the CURRENT text immediately; a pending live-update timer may
        # not have fired yet after the user typed an invalid value.
        self.run_analysis()
        if self.inputs is None or self.analysis is None or self.proposed_result is None:
            messagebox.showwarning("Check your inputs",
                                   "Correct invalid inputs before exporting a graph.", parent=self)
            return
        path = self._choose_file("RampForce_graph.png", kind="png")
        if path:
            try:
                self.figure.savefig(path, dpi=180)
                self.status.set(f"Saved graph: {path}")
            except (OSError, ValueError) as exc:
                messagebox.showerror("Save failed", str(exc), parent=self)


    def save_csv(self, kind):
        # Prevent exporting stale calculations even if live-update is still pending.
        if kind != "comparison":
            self.run_analysis()
        if kind == "comparison":
            if not self.reference_rows:
                messagebox.showwarning("No reference results", "Import reference CSV cases first.", parent=self)
                return
        elif self.inputs is None or self.proposed_result is None:
            messagebox.showwarning("Check your inputs", "Correct invalid inputs before exporting.", parent=self)
            return
        if kind not in ("summary", "ramp_comparison", "comparison"):
            messagebox.showerror("Unknown export", f"Unsupported export kind: {kind}", parent=self)
            return
        scenario = self.vars["scenario"].get().strip() or "scenario"
        path = self._choose_file(f"RampForce_{scenario}_{kind}.csv")
        if not path:
            return
        try:
            if kind == "ramp_comparison":
                n = export_ramp_comparison(path, self.inputs, self.limits, self.proposed_run, scenario)
                self.status.set(f"Exported {n} direct ramp comparison rows: {path}")
            elif kind == "summary":
                export_summary(path, self.inputs, self.limits, scenario, self.proposed_run)
                self.status.set(f"Saved scenario summary: {path}")
            else:
                export_comparison(path, self.reference_rows)
                self.status.set(f"Saved numerical reference comparison: {path}")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)


    def import_refs(self):
        path = self._choose_file("", save=False)
        if path:
            self._load_refs(path)

    def _load_supplied(self):
        """Load the ten reference cases embedded in datasets.py; no external CSV needed."""
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

def main() -> None:
    """Map the window before the first analysis and report the actual startup stage."""
    try:
        print("Creating RampForce window...", flush=True)
        app = RampForceApp(defer_analysis=True)
        app.report_callback_exception = lambda kind, error, tb: _report_callback_error(app, kind, error, tb)
        app.deiconify()
        app.lift()

        def initial_analysis():
            print("RampForce window visible; calculating initial results...", flush=True)
            app.run_analysis()
            print("RampForce initial analysis complete. Close the window to exit.", flush=True)

        def first_map(event):
            if event.widget is not app or getattr(app, "_startup_mapped", False):
                return
            app._startup_mapped = True
            print(f"RampForce window mapped: {app.winfo_geometry()}", flush=True)
            # Bring the window forward briefly, then restore normal stacking.
            try:
                app.attributes("-topmost", True)
                app.after(600, lambda: app.attributes("-topmost", False))
            except tk.TclError:
                pass
            app.after(150, initial_analysis)

        app.bind("<Map>", first_map, add="+")
        # Handle an already mapped root as well as the usual Map event.
        if app.winfo_ismapped():
            from types import SimpleNamespace
            app.after(0, lambda: first_map(SimpleNamespace(widget=app)))
        print("Interface built; entering Tkinter event loop...", flush=True)
        app.mainloop()
        print("RampForce closed.", flush=True)
    except Exception as exc:
        _report_startup_error(exc)
        raise SystemExit(1) from None


def _report_callback_error(app, kind, error, tb):
    """Show callback errors in the existing root, without creating another Tk instance."""
    details = "".join(traceback.format_exception(kind, error, tb))
    print(details, file=sys.stderr, flush=True)
    try:
        (APP_DIR / "RampForce_startup_error.log").write_text(details, encoding="utf-8")
    except OSError:
        pass
    messagebox.showerror("RampForce error", f"{kind.__name__}: {error}\nSee the terminal for details.", parent=app)


if __name__ == "__main__":
    main()
