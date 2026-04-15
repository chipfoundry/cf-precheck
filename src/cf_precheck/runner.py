from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from rich.panel import Panel
from rich.text import Text

from cf_precheck import __version__
from cf_precheck.check_manager import ALL_CHECKS, build_sequence, get_check_manager
from cf_precheck.config import file_hash, get_project_config, uncompress_gds
from cf_precheck.logging import console, error_capture
from cf_precheck.results import CheckResult, ResultsCollector


def _log_info(precheck_config: dict, project_config: dict) -> None:
    gds_info_path = precheck_config["log_path"].parent / "gds.info"
    pdks_info_path = precheck_config["log_path"].parent / "pdks.info"
    tools_info_path = precheck_config["log_path"].parent / "tools.info"

    logging.info(f"Project type: {project_config['type']}")

    try:
        user_module_hash = file_hash(precheck_config["input_directory"] / f"gds/{project_config['user_module']}.gds")
        with open(gds_info_path, "w") as f:
            f.write(f"{project_config['user_module']}.gds: {user_module_hash}")
        logging.info(f"GDS hash ({project_config['user_module']}): {user_module_hash}")
    except Exception as e:
        logging.warning(f"Could not compute GDS hash: {e}")

    try:
        klayout_version = subprocess.check_output(["klayout", "-v"], encoding="utf-8").replace("KLayout", "").strip()
        magic_version = subprocess.check_output(["magic", "--version"], encoding="utf-8").strip()
        with open(tools_info_path, "w") as f:
            f.write(f"KLayout: {klayout_version}\nMagic: {magic_version}")
        logging.info(f"Tools: KLayout v{klayout_version} | Magic v{magic_version}")
    except Exception as e:
        logging.warning(f"Could not detect tool versions: {e}")

    try:
        nodeinfo_path = precheck_config["pdk_path"] / ".config/nodeinfo.json"
        if nodeinfo_path.exists():
            with open(nodeinfo_path) as f:
                pdk_nodeinfo = json.load(f)
                open_pdks_commit = pdk_nodeinfo["commit"]["open_pdks"]
                pdk_commit = pdk_nodeinfo["reference"].get(
                    "skywater_pdk", pdk_nodeinfo["reference"].get("gf180mcu_pdk", "unknown")
                )
            with open(pdks_info_path, "w") as f:
                f.write(f"Open PDKs {open_pdks_commit}\n")
                f.write(f"{precheck_config['pdk_path'].name.upper()} PDK {pdk_commit}")
            logging.info(f"PDK: {precheck_config['pdk_path'].name.upper()} {pdk_commit}")
    except Exception as e:
        logging.warning(f"Could not retrieve PDK info: {e}")


def _format_check_line(prefix: str, dots: str, status: str, elapsed: float | None = None) -> Text:
    if elapsed is not None:
        return Text.from_markup(f"{prefix}{dots} {status}  ({elapsed:.1f}s)")
    return Text.from_markup(f"{prefix}{dots} {status}")


def run_precheck(
    input_directory: Path,
    output_directory: Path,
    caravel_root: Path,
    pdk_path: Path,
    log_path: Path,
    include_magic_drc: bool = False,
    only_checks: list[str] | None = None,
    skip_checks: list[str] | None = None,
) -> bool:
    """Main entry point for running precheck."""
    precheck_config = {
        "input_directory": input_directory,
        "output_directory": output_directory,
        "caravel_root": caravel_root,
        "pdk_path": pdk_path,
        "log_path": log_path,
        "default_content": Path(__file__).parent / "_default_content",
    }

    uncompress_gds(input_directory, caravel_root)
    project_config = get_project_config(input_directory, caravel_root)

    gds_file = input_directory / f"gds/{project_config['user_module']}.gds"
    compressed = input_directory / f"gds/{project_config['user_module']}.gds.gz"
    if gds_file.exists() and compressed.exists():
        console.print("[fail]Both compressed and uncompressed GDS exist. Keep only one.[/fail]")
        return False

    _log_info(precheck_config, project_config)

    pdk = pdk_path.stem
    proj_type = project_config["type"]

    sequence = build_sequence(
        ALL_CHECKS, pdk, proj_type,
        include_optional=include_magic_drc,
        only=only_checks,
        skip=skip_checks,
    )

    input_file_hash = None
    gds_path = input_directory / f"gds/{project_config['user_module']}.gds"
    if gds_path.exists():
        try:
            input_file_hash = file_hash(gds_path)
        except Exception:
            pass

    collector = ResultsCollector(pdk=pdk, input_file_hash=input_file_hash)
    total = len(sequence)
    idx_width = len(str(total))

    console.print()
    console.print(Panel(
        f"[bold]CF Precheck v{__version__}[/bold]\n"
        f"Project: {input_directory.name} ({proj_type}, {pdk})\n"
        f"Checks:  {total}",
        title="Precheck",
        border_style="cyan",
    ))
    console.print()

    logging.info(f"Running {total} checks: [{', '.join(sequence)}]")

    for idx, ref in enumerate(sequence, start=1):
        check = get_check_manager(ref, precheck_config, project_config)
        surname = check.__surname__
        prefix = f"  [{idx:>{idx_width}}/{total}] {surname} "
        dots = "." * max(1, 50 - len(surname))

        error_capture.start()

        is_tty = hasattr(console.file, "isatty") and console.file.isatty()

        if is_tty:
            console.print(_format_check_line(prefix, dots, "[info]RUNNING[/info]"))

        old_stdout, old_stderr = sys.stdout, sys.stderr
        devnull = open(os.devnull, "w")
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            start = time.time()
            try:
                passed = check.run()
            except Exception as e:
                logging.error(f"{surname} raised an exception: {e}")
                passed = False
            elapsed = time.time() - start
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            devnull.close()

        captured_errors = error_capture.stop()

        if passed:
            status_str = "[pass]PASS[/pass]"
            result = CheckResult(name=ref, surname=surname, status="pass", duration_s=elapsed)
        else:
            status_str = "[fail]FAIL[/fail]"
            detail = captured_errors[0] if captured_errors else None
            result = CheckResult(name=ref, surname=surname, status="fail", duration_s=elapsed, details=detail)

        collector.add(result)

        if is_tty:
            # Move cursor up one line and clear it, then print final status
            console.file.write("\033[A\033[2K")
            console.file.flush()
        console.print(_format_check_line(prefix, dots, status_str, elapsed))

        if not passed and captured_errors:
            brief = captured_errors[0]
            if len(brief) > 120:
                brief = brief[:117] + "..."
            console.print(f"         [dim]{brief}[/dim]")

    for ref, cls in ALL_CHECKS.items():
        if cls.__optional__ and ref not in sequence:
            if cls.__supported_pdks__ and pdk in cls.__supported_pdks__:
                collector.add(CheckResult(
                    name=ref, surname=cls.__surname__, status="skip", duration_s=0,
                    reason="optional (use --magic-drc to include)",
                ))

    collector.print_summary()
    collector.write_to_project_json(input_directory)

    return collector.all_passed
