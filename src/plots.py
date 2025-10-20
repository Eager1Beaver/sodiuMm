"""
plots.py — publication-ready plotting for sodium activation/inactivation and window area.

This module provides a single high-level function:

  save_window_plots(tidy_curves, act_fit, inact_fit, window_metrics, outdir, filename_base="window")

which produces PNG (and SVG) figures summarizing experimental points, fitted curves,
intersection points, and the shaded sodium "window" (m_inf - h_inf > 0).

Inputs
------
- tidy_curves: pd.DataFrame with columns ["V", "y", "curve"], where curve ∈ {exp_act, exp_inact, fit_act, fit_inact}
- act_fit, inact_fit: CurveFitResult from fitting.py (used for captions/annotations if desired)
- window_metrics: WindowMetrics (area, bounds, intersections, vmax_window, v_at_vmax_window)
- outdir: Path-like directory to save images
- filename_base: base name for files (e.g., "window" -> window.png, window.svg)

Outputs
-------
- List[Path] of saved figure paths
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # headless-safe
import matplotlib.pyplot as plt


# ---------------------------
# Public API
# ---------------------------

def save_window_plots(
    tidy_curves: pd.DataFrame,
    act_fit,
    inact_fit,
    window_metrics,
    outdir: Path | str,
    filename_base: str = "window",
    *,
    dpi: int = 200,
    include_svg: bool = True,
) -> List[Path]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    fig1 = _make_main_plot(tidy_curves, window_metrics)

    png_path = outdir / f"{filename_base}.png"
    fig1.savefig(png_path, dpi=dpi, bbox_inches="tight")

    paths = [png_path]

    if include_svg:
        svg_path = outdir / f"{filename_base}.svg"
        fig1.savefig(svg_path, bbox_inches="tight")
        paths.append(svg_path)

    plt.close(fig1)
    return paths


# ---------------------------
# Internals
# ---------------------------

def _make_main_plot(tidy_curves: pd.DataFrame, window_metrics) -> plt.Figure:
    required = {"V", "y", "curve"}
    missing = required - set(tidy_curves.columns)
    if missing:
        raise ValueError(f"tidy_curves missing columns: {sorted(missing)}")

    # Split layers
    def layer(name: str) -> pd.DataFrame:
        return tidy_curves[tidy_curves["curve"] == name]

    exp_act = layer("exp_act")
    exp_inact = layer("exp_inact")
    fit_act = layer("fit_act") if "fit_act" in tidy_curves["curve"].unique() else pd.DataFrame(columns=["V","y"]) 
    fit_inact = layer("fit_inact") if "fit_inact" in tidy_curves["curve"].unique() else pd.DataFrame(columns=["V","y"]) 

    # Figure
    fig, ax = plt.subplots(figsize=(7, 5))

    # Experimental points
    if len(exp_act):
        ax.scatter(exp_act["V"], exp_act["y"], s=24, label="Activation (exp)", alpha=0.9, marker="o")
    if len(exp_inact):
        ax.scatter(exp_inact["V"], exp_inact["y"], s=24, label="Inactivation (exp)", alpha=0.9, marker="s")

    # Fitted curves
    if len(fit_act):
        fit_act_sorted = fit_act.sort_values("V")
        ax.plot(fit_act_sorted["V"], fit_act_sorted["y"], linewidth=2.2, label="Activation (fit)")
    if len(fit_inact):
        fit_inact_sorted = fit_inact.sort_values("V")
        ax.plot(fit_inact_sorted["V"], fit_inact_sorted["y"], linewidth=2.2, label="Inactivation (fit)")

    # Shade window region where m_inf − h_inf > 0 using fitted curves if available
        # Shade the CAP: under the crossing, within the curves, down to y=0
    if len(fit_act) and len(fit_inact):
        fit_act_sorted = fit_act.sort_values("V")
        fit_inact_sorted = fit_inact.sort_values("V")
        Vmin = float(min(fit_act_sorted["V"].min(), fit_inact_sorted["V"].min()))
        Vmax = float(max(fit_act_sorted["V"].max(), fit_inact_sorted["V"].max()))
        V = np.linspace(Vmin, Vmax, 1200)

        ma = np.interp(V, fit_act_sorted["V"], fit_act_sorted["y"])
        hi = np.interp(V, fit_inact_sorted["V"], fit_inact_sorted["y"])

        # Use bounds from metrics (cap limits)
        VL_cap, VR_cap = getattr(window_metrics, "area_bounds", (None, None)) if not isinstance(window_metrics, dict) else window_metrics.get("area_bounds", (None, None))
        if VL_cap is not None and VR_cap is not None and np.isfinite(VL_cap) and np.isfinite(VR_cap) and VR_cap > VL_cap:
            mask = (V >= VL_cap) & (V <= VR_cap)
            Vc = V[mask]
            lower = np.minimum(ma[mask], hi[mask])
            ax.fill_between(Vc, 0.0, lower, alpha=0.25, linewidth=0, label="Window (cap)")

    # Intersections
    inters = getattr(window_metrics, "intersections", []) if not isinstance(window_metrics, dict) else window_metrics.get("intersections", [])
    if inters:
        for (vx, vy) in inters:
            ax.scatter([vx], [vy], s=40, zorder=5)
            ax.annotate(f"V*={vx:.1f}", (vx, vy), textcoords="offset points", xytext=(6, 6))

    # Labels and style
    ax.set_title("Sodium activation / inactivation and window area")
    ax.set_xlabel("Voltage V (mV)")
    ax.set_ylabel("Fraction (unitless)")
    ax.set_xlim(_auto_xlim(tidy_curves["V"].to_numpy()))
    ax.set_ylim(-0.05, 1.05)
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=False)

    # Footer text with area info
    area = getattr(window_metrics, "area", None) if not isinstance(window_metrics, dict) else window_metrics.get("area")
    bounds = getattr(window_metrics, "area_bounds", None) if not isinstance(window_metrics, dict) else window_metrics.get("area_bounds")
    vmax = getattr(window_metrics, "vmax_window", None) if not isinstance(window_metrics, dict) else window_metrics.get("vmax_window")
    v_at = getattr(window_metrics, "v_at_vmax_window", None) if not isinstance(window_metrics, dict) else window_metrics.get("v_at_vmax_window")

    footer = []
    if area is not None: footer.append(f"Area = {area:.4g}")
    if bounds is not None: footer.append(f"Bounds = [{bounds[0]:.1f}, {bounds[1]:.1f}] mV")
    if vmax is not None and v_at is not None: footer.append(f"Peak window = {vmax:.3f} at V = {v_at:.1f} mV")
    if footer:
        ax.text(0.01, -0.17, "  ·  ".join(footer), transform=ax.transAxes, ha="left", va="top")

    fig.tight_layout()
    return fig


def _auto_xlim(V: np.ndarray, pad_ratio: float = 0.04) -> Tuple[float, float]:
    vmin, vmax = np.nanmin(V), np.nanmax(V)
    span = vmax - vmin if np.isfinite(vmax - vmin) else 1.0
    pad = max(span * pad_ratio, 1e-6)
    return float(vmin - pad), float(vmax + pad)


# ---------------------------
# Optional test/demo code
# ---------------------------
if __name__ == "__main__":
    import tempfile

    # Fake tidy dataframe
    V = np.linspace(-100, 60, 12)
    df = pd.DataFrame({"V": np.r_[V, V], "y": np.r_[np.linspace(0,1,12), np.linspace(1,0,12)], "curve": ["fit_act"]*12 + ["fit_inact"]*12})
    wm = {"area": 10.0, "area_bounds": (-120, 80), "intersections": [(-45, 0.5)], "vmax_window": 0.6, "v_at_vmax_window": -35}

    tmp = Path(tempfile.mkdtemp())
    paths = save_window_plots(df, None, None, wm, tmp)
    print("Saved:", paths)
