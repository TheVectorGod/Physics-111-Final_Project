# Physics-111-Final_Project
Physics-Based Inclined Plane Analysis and Force Estimation System for Manual Load Transportation 

---
## Requirements (VScode Setup)
Install matplotlib

| Member | Feature | physics.py methods | main.py methods |
|---|---|---:|---:|
| Tristan | Inputs, validation, and user controls | 8 | 11 |
| Ace | Physics computations and understandable results | 5 | 9 |
| Cedric | Feasibility, calculus, graphs, and display styling | 4 | 12 |
| Christian | Sampling, app coordination, datasets, and exports | 3 | 13 |

1. Tristan establishes valid inputs and input controls.
2. Ace implements calculations and numerical result displays.
3. Cedric implements feasibility, calculus and plots.
4. Christian connects everything and completes reference/CSV workflows.

# Member 1 (Tristan) — Inputs, validation, and user controls

**Goal:** Ensure the user can enter, change, and validate every physics parameter and planning limit.

## Assigned functions in `physics.py`

- `Inputs.total_mass_kg` — Return cargo mass plus sled/cart mass in kilograms.
- `Inputs.c_rr` — Calculate the dimensionless rolling coefficient from b (mm) and radius (cm).
- `Inputs.kinetic_coefficient` — Choose mu_k in SLIDING, or Crr in WHEELED mode.
- `Inputs.start_coefficient` — Choose mu_s in SLIDING; the existing wheeled mode uses Crr.
- `_in_range` — Reject non-finite or out-of-range numbers with meaningful ValueError messages.
- `field_errors` — Return a dict of invalid input keys and messages without raising; preserve all bounds and field names.
- `validate` — Raise ValueError using the FIRST message in field_errors, when errors exist.
- `parse_run` — Read metres (including decimal commas) or slope ratio 1:12; return metres; reject invalid inputs.

## Assigned methods in `main.py`

- `Tooltip.__init__` — Record widget/help text and connect hover/focus show/hide callbacks.
- `Tooltip.show` — Show the temporary help popup next to the field unless already shown.
- `Tooltip.hide` — Destroy the help popup if it exists.
- `RampForceApp._field` — Create an input label, entry, inline validation label, and tooltip.
- `RampForceApp._show_field_errors` — Place or hide each validation message under its corresponding box.
- `RampForceApp._build_inputs` — Build scrollable input panel, settings, mode-specific fields, and buttons.
- `RampForceApp._on_mode_selected` — Switch input panels then request a new analysis.
- `RampForceApp._switch_mode` — Show slide or wheel input fields depending on mode.
- `RampForceApp._read_values` — Parse field values (accept decimal commas), instantiate Inputs/Limits, return (inputs, limits, errors).
- `RampForceApp._schedule_analysis` — Debounce edits and call run_analysis after 300 ms.
- `RampForceApp._reset` — Restore DEFAULTS, correct mode panel, and recalculate.

## Integration handoff

Give Christian a reliable `_read_values()` result and Ace valid Inputs/PlanningLimits instances.

## Rules

1. Edit **only** the method bodies labeled with your member number in the shared files.
2. Preserve function names, parameters, decorators, return types, dataclasses, imports, constants, and GUI widget names.
3. Replace `raise NotImplementedError(...)` with the logic you personally implement; do not replace it with a bare `pass` and expect the application to work.
4. If you need another person’s function or a specific widget name, coordinate the contract; do not rename it on your own.
5. Do not alter `datasets.py` or `explain.py` during this exercise.
6. After merging, run `python check_structure.py`, unit tests, and the real GUI. Syntax checks alone do not verify behavior.

**Existing 101-point functions are preserved for original-file compatibility;** redesigning them to match the newer three-ramp manuscript approach should be a separate group decision.

# Member 2 (Ace) — Physics computations and understandable results

**Goal:** Calculate forces, ramp geometry, work and constraint flags for one run, then display and explain outputs.

## Assigned functions in `physics.py`

- `RampResult.feasible` — True only if space_ok, angle_ok and force_ok are all true.
- `RampResult.status` — Return the existing machine-readable FEASIBLE / FAIL: SPACE, ANGLE, FORCE status.
- `RampResult.plain_status` — Return the existing friendly wording for failed conditions.
- `calculate_at_run` — Construct RampResult for one given run; preserve geometry, steady/peak forces, work, and holding semantics.
- `release_note` — Give the existing cautionary release wording; do NOT infer wheeled braking/holding from Crr.

## Assigned methods in `main.py`

- `RampForceApp._card` — Create one results card and return its display StringVars.
- `RampForceApp._build_overview` — Build verdict, selection cards, ramp canvas, and custom-run checker.
- `RampForceApp._fill` — Set display StringVars from the provided texts.
- `RampForceApp._show_banner` — Style the status banner and set icon, title and explanation text.
- `RampForceApp._draw_ramp` — Draw scaled ramp geometry, x and xmax labels on Tk Canvas.
- `RampForceApp._build_steps` — Build the How it was calculated tab using explain_steps.
- `RampForceApp._build_models` — Show the preserved MODEL_TEXT explanation in a scrollable text box.
- `RampForceApp._set_text` — Replace text in a read-only Text widget; highlight STEP headings.
- `RampForceApp._text_box` — Create a read-only, scrollable tkinter.Text widget.

## Integration handoff

Provide Cedric `calculate_at_run` and complete RampResult fields; provide Member 4 the overview widgets.

## Rules

1. Edit **only** the method bodies labeled with your member number in the shared files.
2. Preserve function names, parameters, decorators, return types, dataclasses, imports, constants, and GUI widget names.
3. Replace `raise NotImplementedError(...)` with the logic you personally implement; do not replace it with a bare `pass` and expect the application to work.
4. If you need another person’s function or a specific widget name, coordinate the contract; do not rename it on your own.
5. Do not alter `datasets.py` or `explain.py` during this exercise.
6. After merging, run `python check_structure.py`, unit tests, and the real GUI. Syntax checks alone do not verify behavior.

**Existing 101-point functions are preserved for original-file compatibility;** redesigning them to match the newer three-ramp manuscript approach should be a separate group decision.

# Member 3 (Cedric) — Feasibility, calculus, graphs, and display styling

**Goal:** Find the feasible-run interval, support the analytic endpoint choices, and visualize comparisons.

## Assigned functions in `physics.py`

- `theta_for_force` — Solve the stated theoretical force inequality for its upper allowable angle in radians.
- `analyze` — Calculate allowed angle, minimum required run, feasibility, at_max and at_min; return Analysis.
- `force_derivative` — Compute dFsteady/dx analytically for a specified run.
- `work_derivative` — Compute dW/dx analytically for the current transport coefficient.

## Assigned methods in `main.py`

- `RampForceApp._build_comparison` — Build Matplotlib plots, comparison controls, and ramp table.
- `RampForceApp._update_graphs` — Draw steady/peak forces and work; handle infeasible cases with what-if data.
- `RampForceApp._update_table` — Populate 101-run or standard-slope results with readable status values.
- `RampForceApp.check_custom` — Evaluate a custom run as metres or 1:N; show plain-language constraints and results.
- `RampForceApp._on_check_return` — Run custom check and prevent global Enter handling from repeating analysis.
- `RampForceApp._clear_results` — Clear old verdict, data tables, graph and explanation when input is invalid.
- `RampForceApp._table` — Create a ttk.Treeview with headings and horizontal/vertical scrollbars.
- `RampForceApp._fonts` — Create shared Tkinter font objects.
- `RampForceApp._apply_sizes` — Apply current text size to Tk fonts and Treeview rows.
- `RampForceApp.change_text_size` — Change/reset base font size; reapply sizes and refresh the display.
- `RampForceApp._style` — Configure ttk theme, colors and named label/button styles.
- `RampForceApp._bind_keys` — Connect Enter, Ctrl+Plus, Ctrl+Minus and Ctrl+0 shortcuts.

## Integration handoff

Christian calls `analyze` and uses the table/plot widgets; Member 2 builds the overview cards updated from the same Analysis object.

## Rules

1. Edit **only** the method bodies labeled with your member number in the shared files.
2. Preserve function names, parameters, decorators, return types, dataclasses, imports, constants, and GUI widget names.
3. Replace `raise NotImplementedError(...)` with the logic you personally implement; do not replace it with a bare `pass` and expect the application to work.
4. If you need another person’s function or a specific widget name, coordinate the contract; do not rename it on your own.
5. Do not alter `datasets.py` or `explain.py` during this exercise.
6. After merging, run `python check_structure.py`, unit tests, and the real GUI. Syntax checks alone do not verify behavior.

**Existing 101-point functions are preserved for original-file compatibility;** redesigning them to match the newer three-ramp manuscript approach should be a separate group decision.

# Member 4 (Christian) — Sampling, app coordination, datasets, and exports

**Goal:** Make the whole app start, coordinate backend to GUI, retain the existing comparison sampling, and save/review datasets.

## Assigned functions in `physics.py`

- `sweep` — Reproduce the existing 101-point angle-cap-to-xmax comparison list; preserve old CSV behavior for now.
- `reference_slopes` — Evaluate the existing standard 1:N slope list from RATIOS.
- `what_if_sweep` — Return diagnostic curve points even when the angle-cap run exceeds available space.

## Assigned methods in `main.py`

- `RampForceApp.__init__` — Initialize the window, StringVars, state, fonts, style, tabs, bindings, and initial analysis.
- `RampForceApp._rewrap` — Update long label wraplengths when the window resizes.
- `RampForceApp._build` — Construct main header, side inputs and original five notebook tabs.
- `RampForceApp._build_references` — Build reference CSV import/fallback controls, table, and error summary.
- `RampForceApp.run_analysis` — Coordinate validation, physics.analyze/sweep, text/cards/graph/table and stale-result prevention.
- `RampForceApp._choose_file` — Open a tkinter file chooser for CSV/PNG save or import.
- `RampForceApp.save_graph` — Save the Matplotlib figure as PNG and display status or file I/O errors.
- `RampForceApp.save_csv` — Save candidate, summary or reference-comparison CSV using datasets.py functions.
- `RampForceApp.import_refs` — Choose a reference CSV to import.
- `RampForceApp._load_supplied` — Load sample CSV from samples/ or use SUPPLIED_REFERENCE_CSV fallback.
- `RampForceApp._load_refs` — Load/compare external CSV and show friendly errors.
- `RampForceApp._show_references` — Fill reference results table and compute mean absolute errors.
- `_enable_sharp_text_on_windows` — Apply optional Windows DPI awareness; skip gracefully on non-Windows systems.

## Integration handoff

Christian integrates the completed functions from all three teammates; export uses unchanged datasets.py and reference uses unchanged explain.py.

## Rules

1. Edit **only** the method bodies labeled with your member number in the shared files.
2. Preserve function names, parameters, decorators, return types, dataclasses, imports, constants, and GUI widget names.
3. Replace `raise NotImplementedError(...)` with the logic you personally implement; do not replace it with a bare `pass` and expect the application to work.
4. If you need another person’s function or a specific widget name, coordinate the contract; do not rename it on your own.
5. Do not alter `datasets.py` or `explain.py` during this exercise.
6. After merging, run `python check_structure.py`, unit tests, and the real GUI. Syntax checks alone do not verify behavior.

**Existing 101-point functions are preserved for original-file compatibility;** redesigning them to match the newer three-ramp manuscript approach should be a separate group decision.
