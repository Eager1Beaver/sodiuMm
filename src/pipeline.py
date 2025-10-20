"""
pipeline.py — orchestrates the full sodium-window analysis for a single input file.

Responsibilities
----------------
1) Load experimental data (CSV/XLSX) via input_data.load_input
2) Fit Boltzmann curves for activation and inactivation (fitting.py)
3) Build tidy outputs (experimental + dense fitted grids)
4) Compute intersections, window area, and window-peak biomarkers
5) Save plots (PNG/SVG) and write CSV/XLSX/metadata bundle (output_data.py)

Public API
----------
- PipelineConfig
- run_pipeline(input_path, base_outdir, *, run_name=None, loader_cfg=None, fit_cfg=None, V_bounds=None, samples=None)

Returns a dict with results and an OutputPaths dataclass from output_data.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, Tuple, List

import numpy as np
import pandas as pd

# Local imports (support both package and flat script usage)
try:
    from . import input_data, fitting, output_data, plots
except Exception:
    import input_data, fitting, output_data, plots  # type: ignore


# ---------------------------
# Configuration model
# ---------------------------

@dataclass
class PipelineConfig:
    samples_fit_grid: int = 1200         # points for evaluating fitted curves for plotting/export
    include_svg_plot: bool = True        # also write SVG alongside PNG
    excel_report: bool = True
    write_csvs: bool = True
    write_area_text: bool = True
    write_metadata: bool = True


# ---------------------------
# Orchestration
# ---------------------------

def run_pipeline(
    input_path: str | Path,
    base_outdir: str | Path,
    *,
    run_name: Optional[str] = None,
    loader_cfg: Optional[input_data.DataLoaderConfig] = None,
    fit_cfg: Optional[fitting.FittingConfig] = None,
    V_bounds: Optional[Tuple[float, float]] = None,
    samples: Optional[int] = None,
) -> Dict:
    """Run the sodium-window analysis end-to-end and write outputs.

    Parameters
    ----------
    input_path : str | Path
        Path to CSV/XLSX with experimental points.
    base_outdir : str | Path
        Base directory where a timestamped run folder will be created.
    run_name : str, optional
        Custom run folder name; defaults to "run-<timestamp>".
    loader_cfg : DataLoaderConfig, optional
        Loader behavior (sheet name, clipping, etc.).
    fit_cfg : FittingConfig, optional
        Fitting behavior (bounds, initial guess strategy, etc.).
    V_bounds : (float, float), optional
        Voltage bounds (mV) for metrics and fit-grid evaluation. If None, defaults are used.
    samples : int, optional
        Number of points for fit-grid evaluation; overrides PipelineConfig.samples_fit_grid.

    Returns
    -------
    dict with keys: {"loaded", "fits", "tidy_curves", "biomarkers", "window_metrics", "paths"}
    """
    input_path = Path(input_path)
    base_outdir = Path(base_outdir)
    pcfg = PipelineConfig()
    fit_cfg = fit_cfg or fitting.FittingConfig()
    loader_cfg = loader_cfg or input_data.DataLoaderConfig()

    # 1) Load
    loaded = input_data.load_input(input_path, loader_cfg)

    # 2) Fit curves
    act_fit = fitting.fit_activation(loaded.activation["V"], loaded.activation["y"], fit_cfg)
    inact_fit = fitting.fit_inactivation(loaded.inactivation["V"], loaded.inactivation["y"], fit_cfg)

    # 3) Build fit grids for export/plotting
    if V_bounds is None:
        # Use min/max of experimental voltages with a small pad
        vmin = float(min(loaded.activation["V"].min(), loaded.inactivation["V"].min()))
        vmax = float(max(loaded.activation["V"].max(), loaded.inactivation["V"].max()))
        pad = max(1.0, 0.03 * (vmax - vmin))
        Vmin, Vmax = vmin - pad, vmax + pad
    else:
        Vmin, Vmax = (float(min(V_bounds)), float(max(V_bounds)))

    n = int(samples or pcfg.samples_fit_grid)
    V_grid = fitting.build_voltage_grid(Vmin, Vmax, n)

    Va, ya = fitting.evaluate_on_grid(act_fit.params, Vmin, Vmax, n)
    Vi, yi = fitting.evaluate_on_grid(inact_fit.params, Vmin, Vmax, n)

    # 4) Tidy curves dataframe (experimental + fits)
    tidy_exp = loaded.as_tidy()
    fit_act_df = pd.DataFrame({"V": Va, "y": ya, "curve": "fit_act"})
    fit_inact_df = pd.DataFrame({"V": Vi, "y": yi, "curve": "fit_inact"})
    tidy_curves = pd.concat([tidy_exp, fit_act_df, fit_inact_df], ignore_index=True)

    # 5) Biomarkers table for curves (parameters + fit quality)
    biom_cols = ["curve", "A_lo", "A_hi", "V_half", "k", "r2", "rmse", "method"]
    biomarkers = pd.DataFrame([
        {
            "curve": "fit_act",
            "A_lo": act_fit.params.A_lo,
            "A_hi": act_fit.params.A_hi,
            "V_half": act_fit.params.V_half,
            "k": act_fit.params.k,
            "r2": act_fit.r2,
            "rmse": act_fit.rmse,
            "method": act_fit.method,
        },
        {
            "curve": "fit_inact",
            "A_lo": inact_fit.params.A_lo,
            "A_hi": inact_fit.params.A_hi,
            "V_half": inact_fit.params.V_half,
            "k": inact_fit.params.k,
            "r2": inact_fit.r2,
            "rmse": inact_fit.rmse,
            "method": inact_fit.method,
        },
    ], columns=biom_cols)

    # 6) Window metrics (intersections, area, peak)
    wm = fitting.compute_biomarkers(act_fit, inact_fit, V_bounds=(Vmin, Vmax), samples=max(n, 2000))

    # 7) Write outputs
    # Prepare output config
    out_cfg = output_data.OutputConfig(
        base_outdir=base_outdir,
        run_name=run_name or input_path.stem,
        make_plots_subdir=True,
        write_csvs=pcfg.write_csvs,
        write_excel=pcfg.excel_report,
        write_metadata=pcfg.write_metadata,
        write_area_text=pcfg.write_area_text,
    )

    # Ensure run_dir/plots exists so we can save figures first and then include paths in metadata
    run_dir = out_cfg.base_outdir / (out_cfg.run_name or "run")
    plots_dir = run_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    # Save plots
    fig_paths = plots.save_window_plots(
        tidy_curves=tidy_curves,
        act_fit=act_fit,
        inact_fit=inact_fit,
        window_metrics=wm,
        outdir=plots_dir,
        filename_base="window",
        dpi=220,
        include_svg=True,
    )

    # Write CSVs/XLSX/metadata (with the plot paths we just created)
    paths = output_data.write_outputs(
        tidy_curves=tidy_curves,
        biomarkers=biomarkers,
        window_metrics=wm,
        config=out_cfg,
        plot_paths=fig_paths,
        extra_metadata={
            "source_path": str(loaded.source_path) if loaded.source_path else None,
            "sheet_name": loaded.sheet_name,
            "loader_messages": loaded.messages,
            "V_grid": [Vmin, Vmax, n],
            "fit_config": asdict(fit_cfg),
        },
    )

    return {
        "loaded": loaded,
        "fits": {"activation": act_fit, "inactivation": inact_fit},
        "tidy_curves": tidy_curves,
        "biomarkers": biomarkers,
        "window_metrics": wm,
        "paths": paths,
    }


# ---------------------------
# Optional test/demo code
# ---------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run sodium-window pipeline on a file.")
    parser.add_argument("input", help="Path to input CSV/XLSX")
    parser.add_argument("outdir", help="Base output directory")
    parser.add_argument("--run-name", dest="run_name", default=None, help="Name of run folder (default: input stem)")
    parser.add_argument("--sheet", dest="sheet", default=None, help="Excel sheet name")
    parser.add_argument("--bounds", dest="bounds", default=None, help="Voltage bounds as Vmin,Vmax (e.g., -120,80)")

    args = parser.parse_args()

    lbounds = None
    if args.bounds:
        parts = [p.strip() for p in args.bounds.split(",")]
        if len(parts) != 2:
            parser.error("--bounds must be two comma-separated numbers, e.g., -120,80")
        lbounds = (float(parts[0]), float(parts[1]))

    lcfg = input_data.DataLoaderConfig(sheet_name=args.sheet)

    res = run_pipeline(args.input, args.outdir, run_name=args.run_name, loader_cfg=lcfg, V_bounds=lbounds)
    print("Completed. Output directory:", res["paths"].run_dir)
