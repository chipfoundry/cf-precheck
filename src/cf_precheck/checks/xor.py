import logging
import os
import subprocess
from pathlib import Path

from cf_precheck.config import file_hash

_SCRIPTS_DIR = Path(__file__).parent.parent / "drc_scripts"


def gds_xor_check(
    input_directory: Path,
    output_directory: Path,
    magicrc_file_path: Path,
    gds_golden_wrapper_file_path: Path,
    project_config: dict,
    precheck_config: dict,
) -> bool:
    logs_directory = output_directory / "logs"
    outputs_directory = output_directory / "outputs"

    gds_ut_path = input_directory / "gds" / f"{project_config['user_module']}.gds"
    xor_log_file_path = logs_directory / "xor_check.log"

    if not gds_ut_path.exists():
        logging.error("GDS not found")
        return False

    with open(xor_log_file_path, "w") as xor_log:
        rb_gds_size_file_path = _SCRIPTS_DIR / "gds_size.rb"
        rb_gds_size_cmd = ["ruby", str(rb_gds_size_file_path), str(gds_ut_path), project_config["user_module"]]
        rb_gds_size_process = subprocess.run(rb_gds_size_cmd, stderr=xor_log, stdout=xor_log)
        if rb_gds_size_process.returncode != 0:
            logging.error(f"Top cell name {project_config['user_module']} not found")
            return False

        os.environ["MAGTYPE"] = "mag"

        gds_ut_box_erased_path = outputs_directory / f"{project_config['user_module']}_erased.gds"
        pdk_stem = precheck_config["pdk_path"].stem
        if "gf180mcu" in pdk_stem:
            tcl_erase = _SCRIPTS_DIR / "erase_box_gf180mcu.tcl"
        elif project_config["type"] == "openframe":
            tcl_erase = _SCRIPTS_DIR / "erase_box_openframe.tcl"
        elif project_config["type"] == "mini":
            tcl_erase = _SCRIPTS_DIR / "erase_box_mini4.tcl"
        else:
            tcl_erase = _SCRIPTS_DIR / "erase_box.tcl"

        magic_erase_ut_cmd = [
            "magic", "-dnull", "-noconsole", "-rcfile", str(magicrc_file_path),
            str(tcl_erase), str(gds_ut_path), str(gds_ut_box_erased_path),
            project_config["user_module"],
        ]
        subprocess.run(magic_erase_ut_cmd, stderr=xor_log, stdout=xor_log)

        gds_golden_erased = outputs_directory / f"{project_config['golden_wrapper']}_erased.gds"
        magic_erase_golden_cmd = [
            "magic", "-dnull", "-noconsole", "-rcfile", str(magicrc_file_path),
            str(tcl_erase), str(gds_golden_wrapper_file_path), str(gds_golden_erased),
            project_config["user_module"],
        ]
        subprocess.run(magic_erase_golden_cmd, stderr=xor_log, stdout=xor_log)

        klayout_xor_drc = _SCRIPTS_DIR / "xor.rb.drc"
        xor_result_gds = outputs_directory / f"{project_config['user_module']}.xor.gds"
        xor_total_file_path = logs_directory / "xor_check.total"
        xor_command = [
            "klayout", "-b", "-r", str(klayout_xor_drc),
            "-rd", "ext=gds",
            "-rd", "top_cell=xor_target",
            "-rd", f"thr={os.cpu_count()}",
            "-rd", f"a={gds_ut_box_erased_path}",
            "-rd", f"b={gds_golden_erased}",
            "-rd", f"o={xor_result_gds}",
            "-rd", f"ol={xor_result_gds}",
            "-rd", f"xor_total_file_path={xor_total_file_path}",
        ]
        subprocess.run(xor_command, stderr=xor_log, stdout=xor_log)

    try:
        with open(xor_total_file_path) as f:
            xor_count = f.read().strip()
        logging.info(f"Total XOR differences: {xor_count}")
        return xor_count == "0"
    except FileNotFoundError:
        logging.error(f"XOR total file not found: {xor_total_file_path}")
        return False


_DEFAULT_CONTENT_DIR = Path(__file__).parent.parent / "_default_content"


class XOR:
    __ref__ = "xor"
    __surname__ = "XOR"
    __supported_pdks__ = ["gf180mcuC", "gf180mcuD", "sky130A", "sky130B"]
    __supported_type__ = ["analog", "digital", "openframe", "mini"]
    __optional__ = False

    def __init__(self, precheck_config: dict, project_config: dict):
        self.precheck_config = precheck_config
        self.project_config = project_config
        self.result = True

    def run(self) -> bool:
        pdk_stem = self.precheck_config["pdk_path"].stem
        magicrc = self.precheck_config["pdk_path"] / f"libs.tech/magic/{self.precheck_config['pdk_path'].name}.magicrc"

        if "gf180mcu" in pdk_stem:
            golden_gds = _DEFAULT_CONTENT_DIR / "gds/user_project_wrapper_empty_gf180mcu.gds"
        elif self.project_config["type"] == "mini":
            golden_gds = _DEFAULT_CONTENT_DIR / "gds/user_project_wrapper_mini4_empty.gds"
        else:
            golden_gds = self.precheck_config["caravel_root"] / f"gds/{self.project_config['golden_wrapper']}.gds"

        self.result = gds_xor_check(
            self.precheck_config["input_directory"],
            self.precheck_config["output_directory"],
            magicrc,
            golden_gds,
            self.project_config,
            self.precheck_config,
        )
        return self.result
