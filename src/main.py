"""
main.py — unified entry point for sodiumm

Usage
-----
GUI (default):
    python -m sodiumm   # if packaged
    python src/main.py  # from source tree

CLI (batch):
    python src/main.py run data/sample.csv output/ --run-name demo --bounds -120,80 --sheet data

Subcommands
-----------
- gui  : launch the Tkinter interface (default if no subcommand is given)
- run  : run the pipeline headlessly on one input file
"""
from __future__ import annotations

import sys
from pathlib import Path
import argparse

# Local imports (support both package and flat script usage)
try:
    from . import pipeline, input_data, fitting, gui
except Exception:
    import pipeline, input_data, fitting  # type: ignore
    import gui  # type: ignore

APP_VERSION = "0.1.0"


def _parse_bounds(s: str | None):
    if not s:
        return None
    try:
        parts = [p.strip() for p in s.split(",")]
        if len(parts) != 2:
            raise ValueError
        a, b = float(parts[0]), float(parts[1])
        return (min(a, b), max(a, b))
    except Exception:
        raise argparse.ArgumentTypeError("--bounds must be two comma-separated numbers, e.g., -120,80")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(prog="sodiumm", add_help=False)
    parser.add_argument("--version", action="version", version=f"sodiumm {APP_VERSION}")

    subparsers = parser.add_subparsers(dest="command")

    # GUI subcommand (default)
    p_gui = subparsers.add_parser("gui", help="Launch the GUI")

    # RUN subcommand
    p_run = subparsers.add_parser("run", help="Run the pipeline in CLI mode")
    p_run.add_argument("input", help="Path to input CSV/XLSX")
    p_run.add_argument("outdir", help="Base output directory")
    p_run.add_argument("--run-name", dest="run_name", default=None, help="Run folder name (default: input stem)")
    p_run.add_argument("--sheet", dest="sheet", default=None, help="Excel sheet name (default: tries 'data' or first sheet)")
    p_run.add_argument("--bounds", dest="bounds", default=None, help="Voltage bounds as Vmin,Vmax (e.g., -120,80)")

    # If no subcommand supplied, assume GUI
    if not argv or argv[0] not in {"gui", "run"}:
        return _launch_gui()

    args = parser.parse_args(argv)

    if args.command == "gui":
        return _launch_gui()
    elif args.command == "run":
        return _run_cli(args)
    else:
        parser.print_help()
        return 2


def _launch_gui() -> int:
    try:
        gui.main()
        return 0
    except Exception as e:
        print(f"Failed to start GUI: {e}", file=sys.stderr)
        return 1


def _run_cli(args) -> int:
    try:
        bounds = _parse_bounds(args.bounds)
        lcfg = input_data.DataLoaderConfig(sheet_name=args.sheet)
        res = pipeline.run_pipeline(
            input_path=args.input,
            base_outdir=args.outdir,
            run_name=args.run_name,
            loader_cfg=lcfg,
            V_bounds=bounds,
        )
        print("Completed. Output directory:", res["paths"].run_dir)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
