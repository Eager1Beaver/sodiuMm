"""
output_data.py - writers for CSVs, Excel report, area text, and metadata.

This module centralizes all file outputs for a single run. It produces a clean bundle:

    output/
        <run_name>/
        curves.csv              # V, y, exp_act, fit_act, exp_inact, fit_inact
        biomarkers.csv          # parameters per curve + fit quality
        area.txt                # scalar(s) with definition + bounds
        report.xlsx             # convenience Excel with multiple sheets
        metadata.json           # run metadata (inputs, settings, versions)
        plots/                  # optional: plot files saved by plots.py
            window.png / .svg

Public methods:
    - OutputConfig
    - OutputPaths
    - write_outputs(...)
    - write_curves_csv(...), write_biomarkers_csv(...), write_area_txt(...), write_report_xlsx(...), write_metadata_json(...)

Inputs (typical from pipeline):
    - arranged_curves: pd.DataFrame with columns ["V", "y", "exp_act", "fit_act", "exp_inact", "fit_inact"] and rows for exp/fit variants
    - biomarkers: pd.DataFrame with columns like [curve, A_lo, A_hi, V_half, k, r2, rmse, method]
    - window_metrics: object with fields (area, area_bounds, intersections, vmax_window, v_at_vmax_window)
    - plot_paths: list of paths (created by plots.py) to include in metadata
    - metadata: dict with extra info (app_version, config, source_path, sheet_name, messages)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import json
from datetime import datetime

import numpy as np
import pandas as pd


# ---------------------------
# Configuration
# ---------------------------


@dataclass
class OutputConfig:
    base_outdir: Path
    run_name: Optional[str] = None  # if None, timestamped run name
    make_plots_subdir: bool = True
    write_csvs: bool = True
    write_excel: bool = True
    write_metadata: bool = True
    write_area_text: bool = True
    excel_filename: str = "report.xlsx"
    curves_filename: str = "curves.csv"
    biomarkers_filename: str = "biomarkers.csv"
    area_filename: str = "area.txt"
    metadata_filename: str = "metadata.json"


@dataclass
class OutputPaths:
    run_dir: Path
    curves_csv: Optional[Path]
    biomarkers_csv: Optional[Path]
    area_txt: Optional[Path]
    report_xlsx: Optional[Path]
    metadata_json: Optional[Path]
    plots_dir: Optional[Path]


# ---------------------------
# Methods
# ---------------------------

def _now_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _set_name(name: str) -> str:
    keep = [c if c.isalnum() or c in ("-", "_", ".") else "-" for c in name.strip()]
    s = "".join(keep).strip("-_")
    return s or "run"

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _arrange_cols(arranged_curves: pd.DataFrame) -> pd.DataFrame:
    """
    Arranges 6 columns:
    V, y, exp_act, exp_inact, fit_act, fit_inact

    The specific curve column holds the value; other curve columns are NaN
    'y' duplicates that value.
    """
    required = {"V", "y", "curve"}
    missing = required - set(arranged_curves.columns)
    if missing:
        raise ValueError(f"curves.csv is missing columns: {sorted(missing)}")

    cols = ["V", "y", "exp_act", "exp_inact", "fit_act", "fit_inact"]
    frames = []
    for label in ("exp_act", "exp_inact", "fit_act", "fit_inact"):
        df = arranged_curves[arranged_curves["curve"] == label][["V", "y"]].copy()
        df["exp_act"] = np.nan
        df["exp_inact"] = np.nan
        df["fit_act"] = np.nan
        df["fit_inact"] = np.nan
        if len(df):
            df[label] = df["y"]
        frames.append(df[cols])

    if len(frames):
        out = pd.concat(frames, ignore_index=True)
    else:
        # Empty frame with correct columns
        out = pd.DataFrame(columns=cols)
    return out


# ---------------------------
# Writers
# ---------------------------

def write_outputs(
    *,
    arranged_curves: pd.DataFrame,
    biomarkers: pd.DataFrame,
    window_metrics: object,
    config: OutputConfig,
    plot_paths: Optional[Iterable[Path]] = None,
    extra_metadata: Optional[Dict] = None,
    ) -> OutputPaths:
    """Write all selected outputs and return their paths."""
    if not isinstance(config.base_outdir, Path):
        config.base_outdir = Path(config.base_outdir)

    run_name = _set_name(config.run_name) if config.run_name else f"run-{_now_timestamp()}"
    run_dir = config.base_outdir / run_name
    _ensure_dir(run_dir)

    plots_dir = run_dir / "plots" if config.make_plots_subdir else run_dir
    if config.make_plots_subdir:
        _ensure_dir(plots_dir)

    # CSVs
    curves_csv = (run_dir / config.curves_filename) if config.write_csvs else None
    biomarkers_csv = (run_dir / config.biomarkers_filename) if config.write_csvs else None
    if curves_csv is not None:
        _write_curves_csv(arranged_curves, curves_csv)
    if biomarkers_csv is not None:
        _write_biomarkers_csv(biomarkers, biomarkers_csv)

    # area.txt
    area_txt = (run_dir / config.area_filename) if config.write_area_text else None
    if area_txt is not None:
        _write_area_txt(area_txt, window_metrics)

    # Excel report
    report_xlsx = (run_dir / config.excel_filename) if config.write_excel else None
    if report_xlsx is not None:
        _write_report_xlsx(report_xlsx, arranged_curves, biomarkers, window_metrics)

    # metadata.json
    metadata_json = (run_dir / config.metadata_filename) if config.write_metadata else None
    if metadata_json is not None:
        _write_metadata_json(
            metadata_json,
            arranged_curves=arranged_curves,
            biomarkers=biomarkers,
            window_metrics=window_metrics,
            plot_paths=list(plot_paths) if plot_paths else [],
            extra=extra_metadata or {},
            )

    return OutputPaths(
        run_dir=run_dir,
        curves_csv=curves_csv,
        biomarkers_csv=biomarkers_csv,
        area_txt=area_txt,
        report_xlsx=report_xlsx,
        metadata_json=metadata_json,
        plots_dir=plots_dir,
        )


def _write_curves_csv(arranged_curves: pd.DataFrame, path: Path) -> None:
    wide = _arrange_cols(arranged_curves)
    wide.to_csv(path, index=False)


def _write_biomarkers_csv(biomarkers: pd.DataFrame, path: Path) -> None:
    biomarkers.to_csv(path, index=False)


def _write_area_txt(path: Path, window_metrics: object) -> None:
    # Dataclass-like and dict-like access
    area = getattr(window_metrics, "area", None) if not isinstance(window_metrics, dict) else window_metrics.get("area")
    bounds = getattr(window_metrics, "area_bounds", None) if not isinstance(window_metrics, dict) else window_metrics.get("area_bounds")
    inters = getattr(window_metrics, "intersections", None) if not isinstance(window_metrics, dict) else window_metrics.get("intersections")
    vmax = getattr(window_metrics, "vmax_window", None) if not isinstance(window_metrics, dict) else window_metrics.get("vmax_window")
    v_at = getattr(window_metrics, "v_at_vmax_window", None) if not isinstance(window_metrics, dict) else window_metrics.get("v_at_vmax_window")

    lines = [
        "# Window area of sodium activation-inactivation",
        "Definition: Integral[min(m_inf(V), h_inf(V))] dV on [V_L_cap, V_R_cap], filled down to y=0.",
        "",
        f"Area: {area}",
        f"Cap bounds [V_L_cap, V_R_cap] (mV): {bounds}",
        f"Intersections (V*, y*): {inters}",
        f"Peak window (at crossing): {vmax} at V={v_at}",
        "",
        "Notes: cap bounds come from the y-level just below the crossing; plotting uses the same bounds.",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_report_xlsx(path: Path, arranged_curves: pd.DataFrame, biomarkers: pd.DataFrame, window_metrics: object) -> None:
    # A one-row dataframe for area metrics
    def _wm_value(attr, default=None):
        if isinstance(window_metrics, dict):
            return window_metrics.get(attr, default)
        return getattr(window_metrics, attr, default)

    area_df = pd.DataFrame([
        {
            "area": _wm_value("area"),
            "V_left": _wm_value("area_bounds", (None, None))[0],
            "V_right": _wm_value("area_bounds", (None, None))[1],
            "intersections": _wm_value("intersections"),
            "vmax_window": _wm_value("vmax_window"),
            "v_at_vmax_window": _wm_value("v_at_vmax_window"),
        }
        ])

    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        _arrange_cols(arranged_curves).to_excel(xw, index=False, sheet_name="curves")
        biomarkers.to_excel(xw, index=False, sheet_name="biomarkers")
        area_df.to_excel(xw, index=False, sheet_name="area")


def _write_metadata_json(
    path: Path,
    *,
    arranged_curves: pd.DataFrame,
    biomarkers: pd.DataFrame,
    window_metrics: object,
    plot_paths: List[Path],
    extra: Dict,
    ) -> None:
    meta = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "rows": {
            "curves": int(len(arranged_curves)),
            "biomarkers": int(len(biomarkers)),
            },
        "window_metrics": {
            "area": getattr(window_metrics, "area", None) if not isinstance(window_metrics, dict) else window_metrics.get("area"),
            "area_bounds": getattr(window_metrics, "area_bounds", None) if not isinstance(window_metrics, dict) else window_metrics.get("area_bounds"),
            "intersections": getattr(window_metrics, "intersections", None) if not isinstance(window_metrics, dict) else window_metrics.get("intersections"),
            "vmax_window": getattr(window_metrics, "vmax_window", None) if not isinstance(window_metrics, dict) else window_metrics.get("vmax_window"),
            "v_at_vmax_window": getattr(window_metrics, "v_at_vmax_window", None) if not isinstance(window_metrics, dict) else window_metrics.get("v_at_vmax_window"),
            },
        "plots": [str(p) for p in plot_paths],
        "extra": extra or {},
        }
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


# ---------------------------
# Optional test/demo code
# ---------------------------
if __name__ == "__main__":
    import tempfile
    import numpy as np

    tmp = Path(tempfile.mkdtemp())

    curves = pd.DataFrame({
        "V": np.linspace(-100, 60, 10),
        "y": np.linspace(0, 1, 10),
        "curve": ["fit_act"] * 10,
        })
    biomarkers = pd.DataFrame([
        {"curve": "fit_act", "A_lo": 0.0, "A_hi": 1.0, "V_half": -40.0, "k": 6.0, "r2": 0.99, "rmse": 0.01, "method": "curve_fit"}
        ])
    wm = {
        "area": 12.34,
        "area_bounds": (-120.0, 80.0),
        "intersections": [(-55.0, 0.4), (-25.0, 0.6)],
        "vmax_window": 0.55,
        "v_at_vmax_window": -40.0,
        }

    cfg = OutputConfig(base_outdir=tmp, run_name="demo")
    paths = write_outputs(
        arranged_curves=curves,
        biomarkers=biomarkers,
        window_metrics=wm,
        config=cfg,
        plot_paths=[tmp / "plots" / "window.png"],
        extra_metadata={"source_path": "data/sample.csv", "sheet_name": None, "app_version": "0.1.0"},
        )

    print("Wrote to:", paths)
