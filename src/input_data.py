"""
input_data.py - loader and validator for sodium activation and inactivation datasets.

Expected input (CSV or Excel): 4 logical columns representing two curves:
    - Activation:   V_act (mV), m_inf (0..1)
    - Inactivation: V_inact (mV), h_inf (0..1)

Accepted:
    - Positional columns (no headers): [V_act, m_inf, V_inact, h_inf]
    - Headered columns (case-insensitive, flexible names). See NAME_ALIASES below.

Output: LoadedData with two DataFrames (activation, inactivation) with standardized
columns ["V", "y", "curve"] where curve in {"exp_act", "exp_inact"} and metadata.

This module performs:
    - File type sniffing and sheet selection for Excel
    - Header inference and alias normalization
    - Numeric coercion, NaN/inf removal, and optional clipping to [0,1]
    - Sorting by voltage and duplicate-voltage consolidation
    - Checks with actionable warnings

"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

# ---------------------------
# Configuration
# ---------------------------

NAME_ALIASES: Dict[str, str] = {
    # Activation voltage
    "v_act": "V_act",
    "v_activation": "V_act",
    "voltage_act": "V_act",
    "voltage_activation": "V_act",
    "v(mv)_act": "V_act",
    # Inactivation voltage
    "v_inact": "V_inact",
    "v_inactivation": "V_inact",
    "voltage_inact": "V_inact",
    "voltage_inactivation": "V_inact",
    "v(mv)_inact": "V_inact",
    # Activation fraction
    "m": "m_inf",
    "m_inf": "m_inf",
    "activation": "m_inf",
    "act": "m_inf",
    "fraction_activation": "m_inf",
    # Inactivation fraction
    "h": "h_inf",
    "h_inf": "h_inf",
    "inactivation": "h_inf",
    "inact": "h_inf",
    "fraction_inactivation": "h_inf",
}

REQUIRED_STD_COLS = ["V_act", "m_inf", "V_inact", "h_inf"]

@dataclass
class DataLoaderConfig:
    """Config options for loading input data.

    Attributes
    ----------
    sheet_name: Optional[str]
        Excel sheet to read. If None, tries "data" then first sheet.
    clip_unit_interval: bool
        If True, clip y-values to [0, 1] with a warning.
    drop_duplicate_voltages: bool
        If True, average rows with identical voltages after sorting.
    expect_headers: Optional[bool]
        If True, assume headered columns; if False, assume positional; if None, infer.
    min_points_per_curve: int
        Minimal number of valid (V, y) pairs per curve.
    """

    sheet_name: Optional[str] = None
    clip_unit_interval: bool = True
    drop_duplicate_voltages: bool = True
    expect_headers: Optional[bool] = None
    min_points_per_curve: int = 4

@dataclass
class LoadedData:
    activation: pd.DataFrame
    inactivation: pd.DataFrame
    messages: List[str] = field(default_factory=list)
    source_path: Optional[Path] = None
    sheet_name: Optional[str] = None

    def make_standardized(self) -> pd.DataFrame:
        """Return a single standardized DataFrame with standardized columns.

        Columns: ["V", "y", "curve"], where curve in {"exp_act", "exp_inact"}.
        """
        a = self.activation.copy()
        a["curve"] = "exp_act"
        i = self.inactivation.copy()
        i["curve"] = "exp_inact"
        return pd.concat([a, i], ignore_index=True)[["V", "y", "curve"]]

# ---------------
# API
# ---------------

def load_input(path: str | Path, config: Optional[DataLoaderConfig] = None) -> LoadedData:
    """Load and validate sodium activation/inactivation data from CSV/Excel.

    Parameters
    ----------
    path : str | Path
        Input file path. Supports .csv, .xlsx, .xls.
    config : DataLoaderConfig, optional
        Loader configuration; sensible defaults if omitted.

    Returns
    -------
    LoadedData
        Object containing cleaned activation and inactivation dataframes and messages.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If required columns are missing or data are insufficient/invalid.
    """
    cfg = config or DataLoaderConfig()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    ext = p.suffix.lower()
    msgs: List[str] = []

    if ext == ".csv":
        df = _read_csv(p)
        used_sheet = None
    elif ext in {".xlsx", ".xls"}:
        df, used_sheet = _read_excel(p, cfg.sheet_name, msgs)
    else:
        raise ValueError(f"Unsupported file extension '{ext}'. Use .csv or .xlsx/.xls")

    # Standardize columns
    df_std, _ = _standardize_columns(df, expect_headers=cfg.expect_headers, msgs=msgs)

    # Split into curves
    act = _prepare_curve_df(df_std["V_act"], df_std["m_inf"], curve_label="activation", cfg=cfg, msgs=msgs)
    ina = _prepare_curve_df(df_std["V_inact"], df_std["h_inf"], curve_label="inactivation", cfg=cfg, msgs=msgs)

    # Validate minimal points
    if len(act) < cfg.min_points_per_curve:
        raise ValueError(
            f"Activation curve has only {len(act)} valid points (<{cfg.min_points_per_curve})."
        )
    if len(ina) < cfg.min_points_per_curve:
        raise ValueError(
            f"Inactivation curve has only {len(ina)} valid points (<{cfg.min_points_per_curve})."
        )

    # Final type setters
    act = act[["V", "y"]].astype({"V": float, "y": float})
    ina = ina[["V", "y"]].astype({"V": float, "y": float})

    return LoadedData(activation=act, inactivation=ina, messages=msgs, source_path=p, sheet_name=used_sheet)

# ------------------
# Internal functions
# ------------------

def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception as e:
        raise ValueError(f"Failed to read CSV: {path}\n{e}")


def _read_excel(path: Path, sheet_name: Optional[str], msgs: List[str]) -> Tuple[pd.DataFrame, Optional[str]]:
    try:
        if sheet_name is not None:
            return pd.read_excel(path, sheet_name=sheet_name), sheet_name
        try:
            df = pd.read_excel(path, sheet_name="data")
            msgs.append("Sheet 'data' found and used.")
            return df, "data"
        except Exception:
            # Using first sheet if 'data' not found
            xls = pd.ExcelFile(path)
            first = xls.sheet_names[0]
            msgs.append(f"Using first sheet '{first}'.")
            return pd.read_excel(path, sheet_name=first), first
    except Exception as e:
        raise ValueError(f"Failed to read Excel: {path}\n{e}")


def _normalize_header(s: str) -> str:
    return (
        s.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
    )


def _standardize_columns(
    df: pd.DataFrame,
    expect_headers: Optional[bool],
    msgs: List[str],
) -> Tuple[pd.DataFrame, str]:
    """Return a DataFrame with standardized column names V_act, m_inf, V_inact, h_inf.

    If headers cannot be mapped, attempt positional mapping. Raises ValueError if unsuccessful.

    Returns
    -------
    (df_std, mode)
      mode in {"headers", "positional"}
    """
    # Work on a copy
    work = df.copy()

    # Try header-based mapping if either told to expect headers or inference says headers look plausible
    header_candidates = [
        _normalize_header(str(c)) for c in work.columns
    ]

    alias_map: Dict[str, str] = {}
    for src_norm, original in zip(header_candidates, work.columns):
        if src_norm in NAME_ALIASES:
            alias_map[original] = NAME_ALIASES[src_norm]
        # direct exact std names
        elif src_norm in {"v_act", "v_inact", "m_inf", "h_inf"}:
            # map normalized std to std
            std = src_norm.replace("v_", "V_") if src_norm.startswith("v_") else src_norm
            alias_map[original] = std

    mapped_cols = set(alias_map.values())

    header_is_plausible = len(mapped_cols) >= 2  # at least some names resolved
    do_headers = expect_headers if expect_headers is not None else header_is_plausible

    if do_headers:
        work = work.rename(columns=alias_map)
        missing = [c for c in REQUIRED_STD_COLS if c not in work.columns]
        if missing:
            msgs.append(
                "Header mode selected but some standard columns are missing: " + ", ".join(missing)
            )
        else:
            return work[REQUIRED_STD_COLS].copy(), "headers"

    # Use positional mapping if header mode not selected or failed
    if work.shape[1] < 4:
        raise ValueError(
            f"Expected at least 4 columns, got {work.shape[1]}. Provide either headers or 4 positional columns."
        )
    # Use first four columns by position
    sub = work.iloc[:, :4].copy()
    sub.columns = REQUIRED_STD_COLS
    msgs.append("Using positional columns: [0..3] -> [V_act, m_inf, V_inact, h_inf].")
    return sub, "positional"


def _prepare_curve_df(
    V: Iterable, y: Iterable, *, curve_label: str, cfg: DataLoaderConfig, msgs: List[str]
) -> pd.DataFrame:
    """Clean one curve into a standardized two-column DataFrame with [V, y]."""
    sV = pd.to_numeric(pd.Series(V), errors="coerce")
    sy = pd.to_numeric(pd.Series(y), errors="coerce")

    df = pd.DataFrame({"V": sV, "y": sy}).replace([np.inf, -np.inf], np.nan).dropna()

    # Clip/validate y
    if cfg.clip_unit_interval:
        out_of_range = (~df["y"].between(0.0, 1.0)).sum()
        if out_of_range:
            msgs.append(
                f"{curve_label}: {out_of_range} y-values outside [0,1] were clipped."
            )
            df["y"] = df["y"].clip(0.0, 1.0)
    else:
        if (~df["y"].between(0.0, 1.0)).any():
            msgs.append(
                f"{curve_label}: values outside [0,1] detected (not clipped). Downstream fitting may fail."
            )

    # Sort by voltage
    df = df.sort_values("V", kind="mergesort").reset_index(drop=True)

    # Drop/average duplicate voltages
    if cfg.drop_duplicate_voltages:
        before = len(df)
        df = df.groupby("V", as_index=False)["y"].mean()
        after = len(df)
        if after < before:
            msgs.append(
                f"{curve_label}: consolidated {before - after} duplicate-voltage rows by averaging."
            )

    return df


# ---------------
# Optional test/demo code
# ---------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load and validate sodium window data.")
    parser.add_argument("path", type=str, help="Path to CSV or Excel file")
    parser.add_argument("--sheet", dest="sheet", type=str, default=None, help="Excel sheet name")
    parser.add_argument(
        "--no-clip",
        dest="clip",
        action="store_false",
        help="Do not clip y to [0,1]",
        )
    parser.add_argument(
        "--keep-dupes",
        dest="dedupe",
        action="store_false",
        help="Keep duplicate voltages (do not average)",
        )
    args = parser.parse_args()

    cfg = DataLoaderConfig(sheet_name=args.sheet, clip_unit_interval=args.clip, drop_duplicate_voltages=args.dedupe)
    loaded = load_input(args.path, cfg)

    print("Loaded:")
    print("     activation points:", len(loaded.activation))
    print("     inactivation points:", len(loaded.inactivation))
    print("Messages:")
    print("  - " + "\n  - ".join(loaded.messages))

    print("\nTidy preview (head):")
    print(loaded.make_standardized().head().to_json(orient="records", indent=2))
