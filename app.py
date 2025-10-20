# app.py
import io, tempfile, zipfile, json
from pathlib import Path
import re

import streamlit as st

# Make local modules importable
import sys
sys.path.append("src")

# Import your project code
import pipeline
import input_data
import fitting

st.set_page_config(page_title="sodiuMm - Sodium Window", layout="centered")
st.title("sodiuMm - Sodium Window Analysis")

st.markdown(
    "Upload a CSV/XLSX with sodium activation/deactivation curves. "
    "We'll run the pipeline and give you a ZIP of results plus a quick preview."
    )

uploaded = st.file_uploader("Upload CSV/XLSX", type=["csv", "xlsx", "xls"])
run_name = st.text_input("Run name (optional)", value="")
sheet = st.text_input("Excel sheet (optional)", value="data")
bounds_str = st.text_input("Voltage bounds (e.g., -120,80)", value="-120,80")

def parse_bounds(s: str | None):
    if not s:
        return None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) != 2:
        st.warning("Bounds must look like: -120,80")
        return None
    a, b = float(parts[0]), float(parts[1])
    return (min(a, b), max(a, b))

run_clicked = st.button("Run analysis", type="primary", use_container_width=True)

if run_clicked:
    if uploaded is None:
        st.error("Please upload a file first.")
        st.stop()

    with st.spinner("Running analysis..."):
        # Save uploaded file to a temp dir
        tmpdir = Path(tempfile.mkdtemp(prefix="sodiumm_"))
        infile = tmpdir / uploaded.name
        infile.write_bytes(uploaded.read())

        # Output dir for this run
        outdir = tmpdir / "output"
        outdir.mkdir(parents=True, exist_ok=True)

        # Build configs
        loader_cfg = input_data.DataLoaderConfig(sheet_name=sheet or None)
        fit_cfg = fitting.FittingConfig()

        # Parse bounds
        V_bounds = parse_bounds(bounds_str)

        try:
            # Run your pipeline
            result = pipeline.run_pipeline(
                input_path=str(infile),
                base_outdir=str(outdir),
                run_name=run_name or infile.stem,
                loader_cfg=loader_cfg,
                fit_cfg=fit_cfg,
                V_bounds=V_bounds,
                )
        except Exception as e:
            st.exception(e)
            st.stop()

        # Extract run directory from result
        def _extract_run_dir(res):
            # Case 1: dict result
            if isinstance(res, dict):
                paths = res.get("paths")
                if paths is None:
                    return None
                # If "paths" is a dict
                if isinstance(paths, dict):
                    return Path(paths.get("run_dir")) if paths.get("run_dir") else None
                # If "paths" is a dataclass/obj with .run_dir
                if hasattr(paths, "run_dir"):
                    return Path(paths.run_dir)
                return None
            # Case 2: direct dataclass with .paths or .run_dir
            if hasattr(res, "run_dir"):
                return Path(res.run_dir)
            if hasattr(res, "paths") and hasattr(res.paths, "run_dir"):
                return Path(res.paths.run_dir)
            return None

        run_dir = _extract_run_dir(result)
        if not run_dir or not run_dir.exists():
            st.error("Run completed but no output folder was found.")
            st.stop()


        st.success(f"Done. Outputs saved in: {run_dir.name}")

        # Summary metrics & preview
        def fmt_area(x):
            return f"{x:.3f}"

        def fmt_bounds(bounds):
            if not bounds or len(bounds) != 2:
                return "—"
            a, b = bounds
            return f"({int(round(a))}, {int(round(b))})"

        def fmt_peak(x):
            return f"{x:.2f}"

        def get_from_meta(meta: dict):
            """Get metrics fron metadata.json."""
            wm = (meta or {}).get("window_metrics") or {}
            area = wm.get("area")
            bounds = wm.get("area_bounds")
            peak = wm.get("vmax_window")
            v_at_peak = wm.get("v_at_vmax_window")
            plots = meta.get("plots") or []
            return area, bounds, peak, v_at_peak, plots

        def get_from_area_txt(p: Path):
            """Parser for area.txt lines."""
            if not p.exists():
                return None, None, None, None
            text = p.read_text(encoding="utf-8", errors="ignore")
            # Area
            m_area = re.search(r"^Area:\s*([+-]?\d+(?:\.\d+)?)", text, flags=re.MULTILINE)
            area = float(m_area.group(1)) if m_area else None
            # Bounds
            m_bounds = re.search(
                r"^Bounds:\s*\(\s*([+-]?\d+(?:\.\d+)?),\s*([+-]?\d+(?:\.\d+)?)\s*\)",
                text, flags=re.MULTILINE
            )
            bounds = (float(m_bounds.group(1)), float(m_bounds.group(2))) if m_bounds else None
            # Peak value and V*
            m_peak = re.search(
                r"^Peak window.*:\s*([+-]?\d+(?:\.\d+)?)\s*at V=([+-]?\d+(?:\.\d+)?)",
                text, flags=re.MULTILINE
            )
            peak = float(m_peak.group(1)) if m_peak else None
            v_at_peak = float(m_peak.group(2)) if m_peak else None
            return area, bounds, peak, v_at_peak

        # Load metadata + area.txt
        meta = {}
        meta_json = run_dir / "metadata.json"
        area_txt = run_dir / "area.txt"

        if meta_json.exists():
            try:
                meta = json.loads(meta_json.read_text(encoding="utf-8"))
            except Exception:
                meta = {}

        area_val, bounds_val, peak_val, v_at_peak, meta_plots = get_from_meta(meta)

        if area_val is None or bounds_val is None or peak_val is None:
            a2, b2, p2, vp2 = get_from_area_txt(area_txt)
            area_val = area_val if area_val is not None else a2
            bounds_val = bounds_val if bounds_val is not None else b2
            peak_val = peak_val if peak_val is not None else p2
            v_at_peak = v_at_peak if v_at_peak is not None else vp2

        # Show the three key metrics with requested formatting
        cols = st.columns(3)
        cols[0].metric("Window area", fmt_area(area_val) if area_val is not None else "—")
        cols[1].metric("Voltage bounds", fmt_bounds(bounds_val))
        cols[2].metric("Peak window", fmt_peak(peak_val) if peak_val is not None else "—")

        # Optional small caption for V* at peak (rounded to integer for readability)
        if v_at_peak is not None:
            st.caption(f"Peak occurs near V = {int(round(v_at_peak))} mV")

        # Prefer plots listed in metadata.json
        plot_candidates = []
        for p in (meta_plots or []):
            try:
                q = Path(p)
                if q.exists():
                    plot_candidates.append(q)
            except Exception:
                pass
        plot_candidates += [
            run_dir / "plots" / "window.png",
            run_dir / "plots" / "window.svg",
            run_dir / "plots" / "summary.png",
        ]

        shown = False
        for p in plot_candidates:
            if p.exists() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                st.image(str(p), caption=p.name, use_container_width=True)
                shown = True
                break
        if not shown:
            # Offer SVG (non-raster) as a direct download
            for p in plot_candidates:
                if p.exists():
                    st.download_button(
                        f"Download preview plot: {p.name}",
                        data=p.read_bytes(),
                        file_name=p.name,
                    )
                    shown = True
                    break

        # Package all outputs as a ZIP
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as z:
            for path in run_dir.rglob("*"):
                z.write(path, arcname=path.relative_to(run_dir))
        zip_buf.seek(0)

        st.download_button(
            "Download all outputs (ZIP)",
            data=zip_buf,
            file_name=f"{run_dir.name}.zip",
            mime="application/zip",
            use_container_width=True,
            )

        #
        st.caption("Tip: keep this page open until your download finishes.")

with st.sidebar:
    st.write("**App**: sodiuMm (Streamlit UI)")
