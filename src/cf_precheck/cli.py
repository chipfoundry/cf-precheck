from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

from cf_precheck import __version__
from cf_precheck.check_manager import ALL_CHECKS


def main() -> None:
    all_check_names = list(ALL_CHECKS.keys())

    parser = argparse.ArgumentParser(
        description="CF Precheck - ChipFoundry MPW tapeout precheck tool",
        allow_abbrev=False,
    )
    parser.add_argument("--version", action="version", version=f"cf-precheck {__version__}")
    parser.add_argument(
        "-i", "--input-directory", required=True,
        help="Absolute path to the project directory",
    )
    parser.add_argument(
        "-p", "--pdk-path", required=True,
        help="Path to the PDK installation (variant-specific, e.g. $PDK_ROOT/sky130A)",
    )
    parser.add_argument(
        "-c", "--caravel-root", required=False,
        default=os.environ.get("GOLDEN_CARAVEL"),
        help="Path to the golden Caravel root (default: $GOLDEN_CARAVEL env var)",
    )
    parser.add_argument(
        "-o", "--output-directory", required=False,
        help="Output directory (default: <input_directory>/precheck_results/<timestamp>)",
    )
    parser.add_argument(
        "--magic-drc", action="store_true", default=False,
        help="Include Magic DRC check (optional, off by default)",
    )
    parser.add_argument(
        "checks", metavar="check", type=str, nargs="*",
        help=f"Only run these checks. Available: {' '.join(all_check_names)}",
    )
    parser.add_argument(
        "--skip-checks", metavar="check", type=str, nargs="*",
        help="Skip these checks",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False,
        help="Enable verbose/debug output",
    )

    args = parser.parse_args()

    if not args.caravel_root:
        print(
            "Error: Caravel root not specified. "
            "Use --caravel-root or set the GOLDEN_CARAVEL environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)

    input_directory = Path(args.input_directory)
    pdk_path = Path(args.pdk_path)
    caravel_root = Path(args.caravel_root)

    tag = f"{datetime.datetime.utcnow():%d_%b_%Y___%H_%M_%S}".upper()
    output_directory = Path(args.output_directory) if args.output_directory else input_directory / f"precheck_results/{tag}"

    (output_directory / "logs").mkdir(parents=True, exist_ok=True)
    (output_directory / "outputs").mkdir(parents=True, exist_ok=True)
    (output_directory / "outputs/reports").mkdir(parents=True, exist_ok=True)

    log_path = output_directory / "logs/precheck.log"

    from cf_precheck.logging import setup_logging
    setup_logging(log_path=log_path, verbose=args.verbose)

    only_checks = [c.lower() for c in args.checks] if args.checks else None
    skip_checks = [c.lower() for c in args.skip_checks] if args.skip_checks else None

    from cf_precheck.runner import run_precheck
    success = run_precheck(
        input_directory=input_directory,
        output_directory=output_directory,
        caravel_root=caravel_root,
        pdk_path=pdk_path,
        log_path=log_path,
        include_magic_drc=args.magic_drc,
        only_checks=only_checks,
        skip_checks=skip_checks,
    )

    sys.exit(0 if success else 2)
