from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def uncompress_gds(project_path: Path, caravel_root: Path) -> None:
    cmd = f"make -f {caravel_root}/Makefile uncompress;"
    try:
        logging.info(f"Extracting compressed files in: {project_path}")
        subprocess.run(
            cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
            shell=True, cwd=str(project_path),
        )
    except subprocess.CalledProcessError as error:
        logging.critical(f"Make 'uncompress' error: {error}")
        sys.exit(252)


def is_binary_file(filename: str | Path) -> bool:
    ext = Path(filename).suffix
    return "gds" in ext or "gz" in ext


def file_hash(filename: str | Path) -> str:
    def is_compressed(fn: str | Path) -> bool:
        with open(fn, "rb") as f:
            return f.read(2) == b"\x1f\x8b"

    bsize = 65536
    sha1 = hashlib.sha1()
    f = gzip.open(filename, "rb") if is_compressed(filename) else open(filename, "rb")
    while True:
        data = f.read(bsize)
        if not data:
            break
        sha1.update(data)
    f.close()
    return sha1.hexdigest()


def get_project_config(project_path: Path, caravel_root: Path) -> dict:
    """Detect project type from GDS files and build project config."""
    project_config: dict = {}

    analog_gds = project_path / "gds/user_analog_project_wrapper.gds"
    digital_gds = project_path / "gds/user_project_wrapper.gds"
    openframe_gds = project_path / "gds/openframe_project_wrapper.gds"
    mini_gds = project_path / "gds/user_project_wrapper_mini4.gds"

    gds_files = {
        "analog": analog_gds,
        "digital": digital_gds,
        "openframe": openframe_gds,
        "mini": mini_gds,
    }
    present = {k: v for k, v in gds_files.items() if v.exists()}

    if len(present) != 1:
        logging.critical(
            "A single valid GDS was not found. "
            "Digital projects need 'gds/user_project_wrapper(.gds/.gds.gz)'. "
            "Analog projects need 'gds/user_analog_project_wrapper(.gds/.gds.gz)'."
        )
        sys.exit(254)

    proj_type = next(iter(present))
    configs = {
        "analog": {
            "type": "analog",
            "netlist_type": "spice",
            "top_module": "caravan",
            "user_module": "user_analog_project_wrapper",
            "golden_wrapper": "user_analog_project_wrapper_empty",
            "top_netlist": caravel_root / "spi/lvs/caravan.spice",
            "user_netlist": project_path / "netgen/user_analog_project_wrapper.spice",
        },
        "digital": {
            "type": "digital",
            "netlist_type": "verilog",
            "top_module": "caravel",
            "user_module": "user_project_wrapper",
            "golden_wrapper": "user_project_wrapper_empty",
            "top_netlist": caravel_root / "verilog/gl/caravel.v",
            "user_netlist": project_path / "verilog/gl/user_project_wrapper.v",
        },
        "openframe": {
            "type": "openframe",
            "netlist_type": "verilog",
            "top_module": "caravel_openframe",
            "user_module": "openframe_project_wrapper",
            "golden_wrapper": "openframe_project_wrapper_empty",
            "top_netlist": caravel_root / "verilog/gl/caravel_openframe.v",
            "user_netlist": project_path / "verilog/gl/openframe_project_wrapper.v",
        },
        "mini": {
            "type": "mini",
            "netlist_type": "verilog",
            "top_module": "caravel",
            "user_module": "user_project_wrapper_mini4",
            "golden_wrapper": "user_project_wrapper_mini4_empty",
            "top_netlist": caravel_root / "verilog/gl/caravel.v",
            "user_netlist": project_path / "verilog/gl/user_project_wrapper_mini4.v",
        },
    }
    return configs[proj_type]


# --- LVS/OEB backend utilities ---

def is_valid(string: str) -> bool:
    return not string.startswith("/")


def substitute_env_variables(string: str, env: dict) -> str | None:
    if "$" not in string:
        return string
    words = re.findall(r"\$\w+", string)
    for w in words:
        env_var = w[1:]
        if env_var in env:
            string = string.replace(w, env.get(env_var), 1)
        else:
            logging.error(f"LVS FAILED: couldn't find environment variable {w}")
            return None
    return string


def parse_config_file(json_file: str, be_env: dict) -> bool:
    logging.info(f"Loading LVS environment from {json_file}")
    try:
        with open(json_file) as f:
            data = json.load(f)
        for key, value in data.items():
            if isinstance(value, list):
                exports = be_env[key].split() if key in be_env else []
                for val in value:
                    if is_valid(val):
                        val = substitute_env_variables(val, be_env)
                        if val is None:
                            return False
                        if val not in exports:
                            exports.append(val)
                            if key == "INCLUDE_CONFIGS":
                                be_env["INCLUDE_CONFIGS"] += " " + val
                                if not parse_config_file(val, be_env):
                                    return False
                    else:
                        logging.error(f"{val} is an absolute path, paths must start with $PDK_ROOT or $UPRJ_ROOT")
                        return False
                if key != "INCLUDE_CONFIGS":
                    be_env[key] = " ".join(exports)
            else:
                if is_valid(value):
                    value = substitute_env_variables(value, be_env)
                    if value is None:
                        return False
                    be_env[key] = value
                else:
                    logging.error(f"{value} is an absolute path, paths must start with $PDK_ROOT or $UPRJ_ROOT")
                    return False
        return True
    except Exception as err:
        logging.error(f"Error with config file {json_file}: {err}")
        return False


def run_be_check(
    design_directory: Path,
    output_directory: Path,
    design_name: str,
    config_file: Path,
    pdk_root: Path,
    pdk: str,
    check: str,
) -> bool:
    log_path = f"{output_directory}/logs"
    report_path = f"{output_directory}/outputs/reports"
    log_file_path = f"{log_path}/{check}_check.log"
    tmp_dir = f"{output_directory}/tmp"

    for d in [log_path, tmp_dir, f"{output_directory}/outputs", report_path]:
        os.makedirs(d, exist_ok=True)

    if check == "LVS":
        be_script = "run_be_checks"
        extra_args = "--nooeb"
    elif check == "OEB":
        be_script = "run_oeb_check"
        extra_args = ""
    else:
        logging.error(f"Unknown backend check: {check}")
        return False

    be_checks_dir = str(Path(__file__).parent / "be_checks")

    be_env: dict = {}
    be_env["UPRJ_ROOT"] = str(design_directory)
    be_env["LVS_ROOT"] = be_checks_dir
    be_env["WORK_ROOT"] = tmp_dir
    be_env["LOG_ROOT"] = log_path
    be_env["SIGNOFF_ROOT"] = report_path
    be_env["PDK"] = pdk
    be_env["PDK_ROOT"] = str(pdk_root)
    be_env["DESIGN_NAME"] = design_name

    if not os.path.exists(str(config_file)):
        logging.error(f"{check} FAILED: could not find LVS configuration file {config_file}")
        return False
    be_env["INCLUDE_CONFIGS"] = str(config_file)
    if not parse_config_file(str(config_file), be_env):
        return False

    be_cmd = ["bash", f"{be_checks_dir}/{be_script}", extra_args]

    for lvs_key in ["EXTRACT_FLATGLOB", "EXTRACT_ABSTRACT", "LVS_FLATTEN", "LVS_NOFLATTEN", "LVS_IGNORE", "LVS_SPICE_FILES", "LVS_VERILOG_FILES", "LAYOUT_FILE"]:
        if lvs_key in be_env:
            logging.info(f"{lvs_key}: {be_env[lvs_key]}")
        else:
            logging.warning(f"Missing LVS configuration variable {lvs_key}")

    be_env.update(os.environ)
    with open(log_file_path, "w") as be_log:
        logging.info(f"Running: {be_script}")
        logging.info(f"{check} output directory: {output_directory}")
        p = subprocess.run(be_cmd, stderr=be_log, stdout=be_log, env=be_env)
        stat = p.returncode
        if stat == 4:
            logging.warning(f"ERC check failed (stat={stat}), see {log_file_path}")
            return True
        elif stat != 0:
            logging.error(f"{check} FAILED (stat={stat}), see {log_file_path}")
            return False
        else:
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir)
            return True
