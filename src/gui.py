"""
gui.py — Tkinter GUI for the sodiumm sodium-window analysis tool.

User flow
---------
1) Open input file (.csv/.xlsx)
2) Choose output directory
3) (Optional) Set run name, sheet name, voltage bounds
4) Click "Run analysis"
5) See completion status; open the output folder

Notes
-----
• Runs pipeline on a background thread to keep UI responsive.
• Shows an indeterminate progress bar and a live status label.
• Disables controls during a run to prevent conflicts.
• Robust error handling with messageboxes; logs short messages in the UI.
"""
from __future__ import annotations

import threading
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Tuple

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Local imports (support both package and flat script usage)
try:
    from . import pipeline, input_data, fitting
except Exception:
    import pipeline, input_data, fitting  # type: ignore

APP_TITLE = "sodiumm — Sodium Window Analysis"
APP_VERSION = "0.1.0"


class SodiumWindowApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=12)
        self.master.title(APP_TITLE)

        # State
        self.input_path: Optional[Path] = None
        self.out_dir: Optional[Path] = None

        # UI variables
        self.var_input = tk.StringVar()
        self.var_outdir = tk.StringVar()
        self.var_runname = tk.StringVar()
        self.var_sheet = tk.StringVar(value="data")
        self.var_bounds = tk.StringVar(value="-120,80")
        self.var_svg = tk.BooleanVar(value=True)

        # Layout
        self._build_widgets()

    # ---------------------------
    # UI construction
    # ---------------------------
    def _build_widgets(self) -> None:
        # File selectors
        row = 0
        ttk.Label(self, text="Input file (.csv/.xlsx)").grid(row=row, column=0, sticky="w")
        frm_in = ttk.Frame(self)
        frm_in.grid(row=row, column=1, sticky="ew", padx=(8,0))
        self.columnconfigure(1, weight=1)
        ttk.Entry(frm_in, textvariable=self.var_input).grid(row=0, column=0, sticky="ew")
        frm_in.columnconfigure(0, weight=1)
        ttk.Button(frm_in, text="Browse…", command=self._choose_input).grid(row=0, column=1, padx=(6,0))

        row += 1
        ttk.Label(self, text="Output directory").grid(row=row, column=0, sticky="w")
        frm_out = ttk.Frame(self)
        frm_out.grid(row=row, column=1, sticky="ew", padx=(8,0))
        ttk.Entry(frm_out, textvariable=self.var_outdir).grid(row=0, column=0, sticky="ew")
        frm_out.columnconfigure(0, weight=1)
        ttk.Button(frm_out, text="Choose…", command=self._choose_outdir).grid(row=0, column=1, padx=(6,0))

        # Options
        row += 1
        opt = ttk.LabelFrame(self, text="Options")
        opt.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10,0))
        opt.columnconfigure(1, weight=1)

        ttk.Label(opt, text="Run name").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(opt, textvariable=self.var_runname).grid(row=0, column=1, sticky="ew", padx=(0,8), pady=4)

        ttk.Label(opt, text="Excel sheet name").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(opt, textvariable=self.var_sheet).grid(row=1, column=1, sticky="ew", padx=(0,8), pady=4)

        ttk.Label(opt, text="Voltage bounds (mV)").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(opt, textvariable=self.var_bounds).grid(row=2, column=1, sticky="ew", padx=(0,8), pady=4)

        ttk.Checkbutton(opt, text="Also save SVG plot", variable=self.var_svg).grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(0,8))

        # Actions
        row += 1
        btns = ttk.Frame(self)
        btns.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10,0))
        btns.columnconfigure(1, weight=1)
        self.btn_run = ttk.Button(btns, text="Run analysis", command=self._on_run)
        self.btn_run.grid(row=0, column=0, sticky="w")
        ttk.Button(btns, text="Exit", command=self.master.destroy).grid(row=0, column=2, sticky="e")

        # Progress + status
        row += 1
        prog = ttk.Frame(self)
        prog.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10,0))
        self.pbar = ttk.Progressbar(prog, mode="indeterminate")
        self.pbar.grid(row=0, column=0, sticky="ew")
        prog.columnconfigure(0, weight=1)
        self.lbl_status = ttk.Label(self, text="Ready.")
        self.lbl_status.grid(row=row+1, column=0, columnspan=2, sticky="w", pady=(6,0))

        # Footer
        row += 2
        ttk.Label(self, text=f"{APP_TITLE}  •  v{APP_VERSION}", foreground="#555").grid(row=row, column=0, columnspan=2, sticky="w", pady=(12,0))

        self.grid(sticky="nsew")
        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)

    # ---------------------------
    # Event handlers
    # ---------------------------
    def _choose_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select input file",
            filetypes=[("Data files", "*.csv *.xlsx *.xls"), ("CSV", "*.csv"), ("Excel", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if path:
            self.var_input.set(path)
            self.input_path = Path(path)
            self._set_status("Input selected.")

    def _choose_outdir(self) -> None:
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self.var_outdir.set(path)
            self.out_dir = Path(path)
            self._set_status("Output directory selected.")

    def _parse_bounds(self, s: str) -> Optional[Tuple[float, float]]:
        s = (s or "").strip()
        if not s:
            return None
        try:
            parts = [p.strip() for p in s.split(",")]
            if len(parts) != 2:
                raise ValueError
            vmin, vmax = float(parts[0]), float(parts[1])
            return (min(vmin, vmax), max(vmin, vmax))
        except Exception:
            raise ValueError("Voltage bounds must be two comma-separated numbers, e.g., -120,80")

    def _on_run(self) -> None:
        try:
            if not self.var_input.get():
                raise ValueError("Please select an input file.")
            if not self.var_outdir.get():
                raise ValueError("Please select an output directory.")
            bounds = self._parse_bounds(self.var_bounds.get()) if self.var_bounds.get() else None
        except Exception as e:
            messagebox.showerror("Validation error", str(e))
            return

        # Build configs
        loader_cfg = input_data.DataLoaderConfig(sheet_name=(self.var_sheet.get() or None))
        fit_cfg = fitting.FittingConfig()

        # Disable UI and start background thread
        self._toggle_running(True)
        self._set_status("Running analysis…")

        t = threading.Thread(
            target=self._run_pipeline_thread,
            args=(self.var_input.get(), self.var_outdir.get(), self.var_runname.get() or None, loader_cfg, fit_cfg, bounds),
            daemon=True,
        )
        t.start()

    def _run_pipeline_thread(self, input_path: str, outdir: str, run_name: Optional[str], loader_cfg, fit_cfg, bounds):
        try:
            res = pipeline.run_pipeline(
                input_path=input_path,
                base_outdir=outdir,
                run_name=run_name,
                loader_cfg=loader_cfg,
                fit_cfg=fit_cfg,
                V_bounds=bounds,
            )
            run_dir = res["paths"].run_dir
            msg = (
                f"Completed. Saved outputs in:\n{run_dir}\n\n"
                f"curves.csv, biomarkers.csv, area.txt, report.xlsx, metadata.json, plots/"
            )
            self._after_success(msg)
        except Exception as e:
            self._after_failure(str(e))

    # ---------------------------
    # UI helpers (thread-safe via after)
    # ---------------------------
    def _toggle_running(self, running: bool) -> None:
        def set_state(widget, state):
            try:
                widget.configure(state=state)
            except Exception:
                pass
        state = tk.DISABLED if running else tk.NORMAL
        set_state(self.btn_run, state)
        for child in self.winfo_children():
            if isinstance(child, ttk.Frame) or isinstance(child, ttk.LabelFrame):
                for w in child.winfo_children():
                    if w is not self.btn_run and not isinstance(w, ttk.Progressbar):
                        try:
                            w.configure(state=state)
                        except Exception:
                            pass
        if running:
            self.pbar.start(12)
        else:
            self.pbar.stop()

    def _set_status(self, text: str) -> None:
        self.lbl_status.configure(text=text)

    def _after_success(self, message: str) -> None:
        self.master.after(0, lambda: self._on_success_ui(message))

    def _after_failure(self, message: str) -> None:
        self.master.after(0, lambda: self._on_failure_ui(message))

    def _on_success_ui(self, message: str) -> None:
        self._toggle_running(False)
        self._set_status("Completed ✓")
        messagebox.showinfo("Done", message)

    def _on_failure_ui(self, message: str) -> None:
        self._toggle_running(False)
        self._set_status("Failed ✗")
        messagebox.showerror("Error", message)


# ---------------------------
# Main entry point
# ---------------------------

def main() -> None:
    root = tk.Tk()
    try:
        # Optional: set a nice default ttk theme if available
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    app = SodiumWindowApp(root)
    root.minsize(640, 360)
    root.mainloop()


if __name__ == "__main__":
    main()
