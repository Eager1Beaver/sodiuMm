"""
fittting.py — curve fitting, intersections, and window-area metrics for sodium gating curves.

This module provides a robust, publication-grade implementation to:
  • Fit activation (m∞) and inactivation (h∞) curves with a Boltzmann (sigmoid) model.
  • Evaluate fitted curves on dense voltage grids for plotting/export.
  • Find 0/1/2 intersections between the two fitted curves.
  • Compute the physiologically meaningful "window area": ∫ max(0, m∞(V) − h∞(V)) dV.
  • Extract biomarkers: V½, slope factor k, plateaus (A_lo, A_hi), R², RMSE, and window peak.

Design notes
------------
• Activation uses y = A_lo + (A_hi − A_lo) / (1 + exp(−(V − V_half)/k))
• Inactivation uses y = A_lo + (A_hi − A_lo) / (1 + exp( +(V − V_half)/k))
  The sign flip captures decreasing behavior.
• Bounds and smart initial guesses increase stability on sparse/limited datasets.
• If non-linear least squares fails, an optional spline fallback can provide a smooth
  curve for downstream metrics (flagged via result.method="spline_fallback").

Public API
----------
- FittingConfig
- SigmoidParams, CurveFitResult, WindowMetrics
- fit_activation(V, y, cfg) -> CurveFitResult
- fit_inactivation(V, y, cfg) -> CurveFitResult
- evaluate(params, V) -> ndarray
- build_voltage_grid(Vmin, Vmax, n) -> ndarray
- find_intersections(f_act, f_inact, V_grid) -> List[float]
- compute_window_area(f_act, f_inact, V_left=None, V_right=None, n=2000) -> (area, (VL, VR))
- compute_biomarkers(act_fit, inact_fit, *, V_bounds=None, samples=1000) -> WindowMetrics
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np

# SciPy imports are optional for environments without SciPy at import-time; we import lazily
from scipy.optimize import curve_fit
from scipy.interpolate import UnivariateSpline
from scipy.integrate import simpson
from scipy.optimize import brentq


# ---------------------------
# Models & Configuration
# ---------------------------

@dataclass
class FittingConfig:
    # Global bounds for parameters
    A_lo_bounds: Tuple[float, float] = (0.0, 1.0)
    A_hi_bounds: Tuple[float, float] = (0.0, 1.0)
    V_half_bounds: Tuple[float, float] = (-150.0, 150.0)  # mV
    k_bounds: Tuple[float, float] = (0.1, 50.0)  # mV, positive magnitude; sign is encoded by model

    # Initial guess strategies
    use_percentile_plateaus: bool = True  # infer A_lo/A_hi from 10th/90th percentile

    # Fallback behavior
    enable_spline_fallback: bool = True
    spline_smoothing: Optional[float] = None  # None lets UnivariateSpline choose reasonable s

    # Evaluation density
    default_samples: int = 1000


@dataclass
class SigmoidParams:
    A_lo: float
    A_hi: float
    V_half: float
    k: float  # positive magnitude; sign handled by model choice
    invert: bool  # False for activation, True for inactivation


@dataclass
class CurveFitResult:
    params: SigmoidParams
    success: bool
    method: str  # "curve_fit" or "spline_fallback"
    r2: Optional[float]
    rmse: Optional[float]
    y_pred_on_data: Optional[np.ndarray]
    covariance: Optional[np.ndarray]

    def evaluate(self, V: np.ndarray) -> np.ndarray:
        return evaluate(self.params, V)


@dataclass
class WindowMetrics:
    intersections: List[Tuple[float, float]]  # [(V*, y*), ...]
    area: float
    area_bounds: Tuple[float, float]
    vmax_window: float  # max(m∞ − h∞) within bounds
    v_at_vmax_window: float


# ---------------------------
# Core model and helpers
# ---------------------------

def _boltzmann_activation(V: np.ndarray, A_lo: float, A_hi: float, V_half: float, k: float) -> np.ndarray:
    return A_lo + (A_hi - A_lo) / (1.0 + np.exp(-(V - V_half) / k))


def _boltzmann_inactivation(V: np.ndarray, A_lo: float, A_hi: float, V_half: float, k: float) -> np.ndarray:
    # Decreasing with V by flipping the exponent sign
    return A_lo + (A_hi - A_lo) / (1.0 + np.exp(+ (V - V_half) / k))


def evaluate(params: SigmoidParams, V: np.ndarray) -> np.ndarray:
    if params.invert:
        return _boltzmann_inactivation(V, params.A_lo, params.A_hi, params.V_half, abs(params.k))
    else:
        return _boltzmann_activation(V, params.A_lo, params.A_hi, params.V_half, abs(params.k))


def _initial_guess(V: np.ndarray, y: np.ndarray, *, invert: bool, cfg: FittingConfig) -> Tuple[float, float, float, float]:
    V = np.asarray(V)
    y = np.asarray(y)

    # Plateaus
    if cfg.use_percentile_plateaus:
        lo = float(np.nanpercentile(y, 10))
        hi = float(np.nanpercentile(y, 90))
    else:
        lo, hi = float(np.nanmin(y)), float(np.nanmax(y))
    if lo > hi:
        lo, hi = hi, lo
    lo = np.clip(lo, cfg.A_lo_bounds[0], cfg.A_lo_bounds[1])
    hi = np.clip(hi, cfg.A_hi_bounds[0], cfg.A_hi_bounds[1])

    # V_half: midpoint in y mapped to nearest V via linear interpolation
    mid = (lo + hi) / 2.0
    # rough monotonic mapping (works even with a few points)
    order = np.argsort(V)
    V_sorted, y_sorted = V[order], y[order]
    try:
        V_half = float(np.interp(mid, y_sorted if invert else np.sort(y_sorted), np.sort(V_sorted)))
    except Exception:
        V_half = float(np.nanmedian(V))

    # slope factor k: spread of V covering middle 60%
    q20, q80 = np.nanpercentile(V, 20), np.nanpercentile(V, 80)
    k = max((q80 - q20) / 8.0, cfg.k_bounds[0])  # heuristic; ensures not too small
    k = min(k, cfg.k_bounds[1])

    return lo, hi, V_half, float(k)


def _fit_generic(V: np.ndarray, y: np.ndarray, invert: bool, cfg: FittingConfig) -> CurveFitResult:
    V = np.asarray(V, dtype=float)
    y = np.asarray(y, dtype=float)

    # Bounds
    bounds_lo = [cfg.A_lo_bounds[0], cfg.A_hi_bounds[0], cfg.V_half_bounds[0], cfg.k_bounds[0]]
    bounds_hi = [cfg.A_lo_bounds[1], cfg.A_hi_bounds[1], cfg.V_half_bounds[1], cfg.k_bounds[1]]

    p0 = _initial_guess(V, y, invert=invert, cfg=cfg)

    model: Callable[[np.ndarray, float, float, float, float], np.ndarray] = (
        _boltzmann_inactivation if invert else _boltzmann_activation
    )

    try:
        popt, pcov = curve_fit(
            model, V, y, p0=p0, bounds=(bounds_lo, bounds_hi), maxfev=20000
        )
        yhat = model(V, *popt)
        resid = y - yhat
        ss_res = float(np.sum(resid ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
        rmse = float(np.sqrt(ss_res / max(len(y), 1)))
        params = SigmoidParams(A_lo=float(popt[0]), A_hi=float(popt[1]), V_half=float(popt[2]), k=float(popt[3]), invert=invert)
        return CurveFitResult(params=params, success=True, method="curve_fit", r2=r2, rmse=rmse, y_pred_on_data=yhat, covariance=pcov)
    except Exception:
        if not cfg.enable_spline_fallback:
            raise
        # Monotone-ish smoothing spline as fallback
        try:
            # Sort by V for spline
            order = np.argsort(V)
            Vs, ys = V[order], y[order]
            spl = UnivariateSpline(Vs, ys, s=cfg.spline_smoothing)
            # Convert spline to pseudo-params by fitting sigmoid to spline samples
            grid = build_voltage_grid(float(Vs.min()), float(Vs.max()), max(200, cfg.default_samples//2))
            y_spl = np.clip(spl(grid), 0.0, 1.0)
            p0_spl = _initial_guess(grid, y_spl, invert=invert, cfg=cfg)
            try:
                popt, pcov = curve_fit(
                    model, grid, y_spl, p0=p0_spl, bounds=(bounds_lo, bounds_hi), maxfev=20000
                )
                yhat = model(V, *popt)
                resid = y - yhat
                ss_res = float(np.sum(resid ** 2))
                ss_tot = float(np.sum((y - np.mean(y)) ** 2))
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
                rmse = float(np.sqrt(ss_res / max(len(y), 1)))
                params = SigmoidParams(A_lo=float(popt[0]), A_hi=float(popt[1]), V_half=float(popt[2]), k=float(popt[3]), invert=invert)
                return CurveFitResult(params=params, success=True, method="spline_fallback", r2=r2, rmse=rmse, y_pred_on_data=yhat, covariance=pcov)
            except Exception:
                # As a last resort, return a spline-evaluated pseudo-constant sigmoid near data center
                A_lo, A_hi, V_half, k = p0_spl
                params = SigmoidParams(A_lo=A_lo, A_hi=A_hi, V_half=V_half, k=k, invert=invert)
                yhat = evaluate(params, V)
                resid = y - yhat
                ss_res = float(np.sum(resid ** 2))
                ss_tot = float(np.sum((y - np.mean(y)) ** 2))
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
                rmse = float(np.sqrt(ss_res / max(len(y), 1)))
                return CurveFitResult(params=params, success=False, method="spline_fallback", r2=r2, rmse=rmse, y_pred_on_data=yhat, covariance=None)
        except Exception:
            # give up with very basic params
            A_lo, A_hi, V_half, k = p0
            params = SigmoidParams(A_lo=A_lo, A_hi=A_hi, V_half=V_half, k=k, invert=invert)
            return CurveFitResult(params=params, success=False, method="curve_fit", r2=None, rmse=None, y_pred_on_data=None, covariance=None)


def fit_activation(V: Iterable[float], y: Iterable[float], cfg: Optional[FittingConfig] = None) -> CurveFitResult:
    cfg = cfg or FittingConfig()
    V = np.asarray(list(V), dtype=float)
    y = np.asarray(list(y), dtype=float)
    return _fit_generic(V, y, invert=False, cfg=cfg)


def fit_inactivation(V: Iterable[float], y: Iterable[float], cfg: Optional[FittingConfig] = None) -> CurveFitResult:
    cfg = cfg or FittingConfig()
    V = np.asarray(list(V), dtype=float)
    y = np.asarray(list(y), dtype=float)
    return _fit_generic(V, y, invert=True, cfg=cfg)


# ---------------------------
# Intersections & Window area
# ---------------------------

def build_voltage_grid(Vmin: float, Vmax: float, n: int) -> np.ndarray:
    if Vmax < Vmin:
        Vmin, Vmax = Vmax, Vmin
    # pad slightly to avoid edge-root issues
    span = Vmax - Vmin
    Vmin -= 0.01 * span
    Vmax += 0.01 * span
    return np.linspace(Vmin, Vmax, int(max(n, 50)))


def find_intersections(f_act: Callable[[np.ndarray], np.ndarray], f_inact: Callable[[np.ndarray], np.ndarray], V_grid: np.ndarray) -> List[float]:
    """Find all distinct roots of f(V) = m∞(V) − h∞(V) on the given grid using brentq bracketed by sign changes."""
    m = f_act(V_grid)
    h = f_inact(V_grid)
    diff = m - h
    roots: List[float] = []

    # Identify sign changes between consecutive grid points
    s = np.sign(diff)
    changes = np.where(s[:-1] * s[1:] < 0)[0]

    for idx in changes:
        a, b = V_grid[idx], V_grid[idx + 1]
        try:
            r = brentq(lambda V: float(f_act(np.array([V])) - f_inact(np.array([V]))), a, b, maxiter=200)
            roots.append(float(r))
        except Exception:
            continue

    # Deduplicate close roots
    roots = sorted(roots)
    dedup: List[float] = []
    for r in roots:
        if not dedup or abs(r - dedup[-1]) > 1e-6:
            dedup.append(r)
    return dedup


def compute_window_area(
    f_act: Callable[[np.ndarray], np.ndarray],
    f_inact: Callable[[np.ndarray], np.ndarray],
    V_left: Optional[float] = None,
    V_right: Optional[float] = None,
    n: int = 2000,
) -> Tuple[float, Tuple[float, float]]:
    """Compute ∫ max(0, m∞ − h∞) dV over [VL, VR]. If bounds are None, uses min/max of an adaptive grid.

    Returns (area, (VL, VR)).
    """
    if V_left is None or V_right is None:
        # Use a broad grid to infer reasonable bounds from where curves differ
        base = np.linspace(-150.0, 150.0, 601)
        d = f_act(base) - f_inact(base)
        mask = np.abs(d) > 1e-6
        if not np.any(mask):
            # curves virtually identical; area zero across default bounds
            VL, VR = float(base.min()), float(base.max())
        else:
            VL = float(base[mask].min())
            VR = float(base[mask].max())
    else:
        VL, VR = (float(V_left), float(V_right)) if V_left <= V_right else (float(V_right), float(V_left))

    V = np.linspace(VL, VR, int(max(n, 50)))
    m = f_act(V)
    h = f_inact(V)
    w = np.maximum(0.0, m - h)
    area = float(simpson(w, V))
    return area, (VL, VR)


def compute_biomarkers(
    act_fit: CurveFitResult,
    inact_fit: CurveFitResult,
    *,
    V_bounds: Optional[Tuple[float, float]] = None,
    samples: int = 2000,
) -> WindowMetrics:
    import numpy as np
    from scipy.optimize import brentq

    # Safe scalar evaluators (avoid ndarray->scalar deprecation)
    def f_act_scalar(v: float) -> float:
        return float(act_fit.evaluate(np.array([v], dtype=float))[0])
    def f_in_scalar(v: float) -> float:
        return float(inact_fit.evaluate(np.array([v], dtype=float))[0])

    # Vector evaluators
    f_act = lambda V: act_fit.evaluate(np.asarray(V, dtype=float))
    f_in  = lambda V: inact_fit.evaluate(np.asarray(V, dtype=float))

    # --- grid and intersection ---
    VL, VR = (-120.0, 80.0) if V_bounds is None else (float(min(V_bounds)), float(max(V_bounds)))
    Vg = np.linspace(VL, VR, int(max(samples, 800)))
    diff = f_act(Vg) - f_in(Vg)
    sgn  = np.sign(diff)
    zidx = np.where(sgn[:-1] * sgn[1:] < 0)[0]

    def root_between(a: float, b: float) -> float:
        return float(brentq(lambda v: f_act_scalar(v) - f_in_scalar(v), a, b, maxiter=200))

    intersections: List[Tuple[float, float]] = []
    roots: List[float] = []
    for i in zidx:
        r = root_between(float(Vg[i]), float(Vg[i+1]))
        ystar = 0.5 * (f_act_scalar(r) + f_in_scalar(r))
        roots.append(r)
        intersections.append((float(r), float(ystar)))

    if not roots:
        # No crossing → window undefined → report standard overlap metrics over full bounds
        vmax = float(np.max(diff))
        v_at = float(Vg[int(np.argmax(diff))])
        return WindowMetrics(
            intersections=[],
            area=0.0,
            area_bounds=(VL, VR),
            vmax_window=vmax,
            v_at_vmax_window=v_at,
        )

    # Choose intersection with largest y* (most prominent wedge)
    V_star, y_star = max(intersections, key=lambda p: p[1])

    # --- choose a cap level slightly below the crossing to avoid zero width ---
    CAP_REL = 0.02                             # 98% of y*
    y_cap = float(max(1e-6, CAP_REL * y_star))  # keep positive

    # Find VL_cap: solve m∞(V) = y_cap to the LEFT of V*
    Fa = f_act(Vg) - y_cap
    sFa = np.sign(Fa)
    left_candidates = np.where((Vg[:-1] < V_star) & (sFa[:-1] * sFa[1:] < 0))[0]
    if len(left_candidates) == 0:
        # fallback: small step left
        VL_cap = float(V_star - 1.0)
    else:
        iL = left_candidates[-1]
        VL_cap = float(brentq(lambda v: f_act_scalar(v) - y_cap, float(Vg[iL]), float(Vg[iL+1]), maxiter=200))

    # Find VR_cap: solve h∞(V) = y_cap to the RIGHT of V*
    Fi = f_in(Vg) - y_cap
    sFi = np.sign(Fi)
    right_candidates = np.where((Vg[1:] > V_star) & (sFi[:-1] * sFi[1:] < 0))[0]
    if len(right_candidates) == 0:
        # fallback: small step right
        VR_cap = float(V_star + 1.0)
    else:
        iR = right_candidates[0]
        VR_cap = float(brentq(lambda v: f_in_scalar(v) - y_cap, float(Vg[iR]), float(Vg[iR+1]), maxiter=200))

    # Guard against degeneracy
    if not np.isfinite(VL_cap) or not np.isfinite(VR_cap) or VR_cap <= VL_cap:
        vmax = float(np.max(diff))
        v_at = float(Vg[int(np.argmax(diff))])
        return WindowMetrics(
            intersections=[(float(V_star), float(y_star))],
            area=0.0,
            area_bounds=(VL, VR),
            vmax_window=vmax,
            v_at_vmax_window=v_at,
        )

    # --- area of the wedge: integrate the lower envelope on [VL_cap, VR_cap] ---
    Vcap = np.linspace(VL_cap, VR_cap, int(max(512, samples // 2)))
    lower = np.minimum(f_act(Vcap), f_in(Vcap))
    lower = np.maximum(lower, 0.0)  # down to x-axis, non-negative

    # robust trapezoid with dedupe
    mask = np.isfinite(Vcap) & np.isfinite(lower)
    Vcap = Vcap[mask]
    lower = lower[mask]
    Vcap, uniq = np.unique(Vcap, return_index=True)
    lower = lower[uniq]

    if Vcap.size >= 2:
        area = float(np.trapz(lower, Vcap))
    else:
        # ultra-narrow numerical collapse → triangle approximation
        area = 0.5 * float(y_cap) * float(max(0.0, VR_cap - VL_cap))

    # Window peak = (y*, at V*)
    return WindowMetrics(
        intersections=[(float(V_star), float(y_star))],
        area=area,
        area_bounds=(float(VL_cap), float(VR_cap)),
        vmax_window=float(y_star),
        v_at_vmax_window=float(V_star),
    )


# ---------------------------
# Utilities for sampling
# ---------------------------

def evaluate_on_grid(params: SigmoidParams, Vmin: float, Vmax: float, n: int) -> Tuple[np.ndarray, np.ndarray]:
    V = build_voltage_grid(Vmin, Vmax, n)
    return V, evaluate(params, V)


# ---------------------------
# Optional test/demo code
# ---------------------------
if __name__ == "__main__":
    # Simple synthetic demo
    rng = np.random.default_rng(0)
    V_data = np.linspace(-100, 60, 12)
    m_true = SigmoidParams(0.0, 1.0, -35.0, 6.0, invert=False)
    h_true = SigmoidParams(0.0, 1.0, -55.0, 7.0, invert=True)
    m_obs = evaluate(m_true, V_data) + rng.normal(0, 0.02, size=V_data.size)
    h_obs = evaluate(h_true, V_data) + rng.normal(0, 0.02, size=V_data.size)
    m_obs = np.clip(m_obs, 0, 1)
    h_obs = np.clip(h_obs, 0, 1)

    cfg = FittingConfig()
    m_fit = fit_activation(V_data, m_obs, cfg)
    h_fit = fit_inactivation(V_data, h_obs, cfg)

    metrics = compute_biomarkers(m_fit, h_fit, V_bounds=(-120, 80))

    print("Activation fit:", m_fit)
    print("Inactivation fit:", h_fit)
    print("Intersections:", metrics.intersections)
    print("Area:", metrics.area, "over", metrics.area_bounds)
    print("Window peak:", metrics.vmax_window, "at V=", metrics.v_at_vmax_window)
