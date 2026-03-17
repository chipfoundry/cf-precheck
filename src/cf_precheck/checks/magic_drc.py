import gzip
import logging
import os
import re
import subprocess
from pathlib import Path

from cf_precheck.checks.magic_converters import magic_drc_to_rdb, magic_drc_to_tcl, magic_drc_to_tr_drc, tr2klayout

_SCRIPTS_DIR = Path(__file__).parent.parent / "drc_scripts"


def _check_if_binary_has(word: str, filename: Path) -> int:
    f = gzip.open(filename, "r", errors="ignore") if "gz" in str(filename) else open(filename, errors="ignore")
    content = f.read()
    f.close()
    return int(bool(re.search(word, content)))


def _is_valid_magic_drc_report(drc_content: str) -> bool:
    split_line = "----------------------------------------"
    return len(drc_content.split(split_line)) >= 2


def _violations_count(drc_content: str) -> int:
    split_line = "----------------------------------------"
    drc_sections = drc_content.split(split_line)
    if len(drc_sections) == 2:
        return 0
    count = 0
    for i in range(1, len(drc_sections) - 1, 2):
        val = len(drc_sections[i + 1].split("\n")) - 2
        count += val
        logging.error(f"Violation: '{drc_sections[i].strip()}' found {val} times")
    return count


def magic_gds_drc_check(
    gds_ut_path: Path,
    design_name: str,
    pdk_path: Path,
    output_directory: Path,
) -> bool:
    logs_directory = output_directory / "logs"
    outputs_directory = output_directory / "outputs"
    reports_directory = outputs_directory / "reports"
    design_magic_drc_file_path = reports_directory / "magic_drc_check.drc.report"

    installed_sram_modules_names = []
    sram_dir = pdk_path / "libs.ref/sky130_sram_macros/maglef"
    if sram_dir.exists():
        for f in sram_dir.glob("*.mag"):
            installed_sram_modules_names.append(f.stem)

    sram_modules_in_gds = [s for s in installed_sram_modules_names if _check_if_binary_has(s, gds_ut_path)]

    pdk_name = pdk_path.stem
    magicrc = pdk_path / "libs.tech" / "magic" / f"{pdk_name}.magicrc"
    magic_drc_tcl = _SCRIPTS_DIR / "magic_drc_check.tcl"
    design_mag = outputs_directory / f"{design_name}.magic.drc.mag"
    esd_fet = "sky130_fd_io__signal_5_sym_hv_local_5term"
    has_sram = str(_check_if_binary_has("sram", gds_ut_path))
    has_esd = str(_check_if_binary_has(esd_fet, gds_ut_path))

    os.environ["MAGTYPE"] = "mag"
    os.environ["PDK_ROOT"] = str(pdk_path.parent)

    run_cmd = [
        "magic", "-noconsole", "-dnull", "-rcfile", str(magicrc),
        str(magic_drc_tcl), str(gds_ut_path), design_name, str(pdk_path),
        str(design_magic_drc_file_path), str(design_mag),
        " ".join(sram_modules_in_gds), esd_fet, has_sram, has_esd,
    ]

    magic_drc_log_path = logs_directory / "magic_drc_check.log"
    with open(magic_drc_log_path, "w") as log_f:
        process = subprocess.run(run_cmd, stderr=log_f, stdout=log_f)

    if not design_magic_drc_file_path.exists():
        logging.error(f"No DRC report produced: {design_magic_drc_file_path}")
        return False

    drc_violations_count = process.returncode
    if drc_violations_count != 0:
        drc_violations_count = (drc_violations_count + 3) / 4

    total_path = logs_directory / "magic_drc_check.total"
    with open(total_path, "w") as f:
        f.write(str(drc_violations_count))

    try:
        rdb_path = reports_directory / "magic_drc_check.rdb"
        magic_drc_to_rdb.convert(design_magic_drc_file_path, rdb_path)
        tcl_path = reports_directory / "magic_drc_check.tcl"
        magic_drc_to_tcl.convert(design_magic_drc_file_path, tcl_path)
        tr_path = reports_directory / "magic_drc_check.tr"
        magic_drc_to_tr_drc.convert(design_magic_drc_file_path, tr_path)
        xml_path = reports_directory / "magic_drc_check.xml"
        tr2klayout.convert(tr_path, xml_path, design_name)
    except Exception as e:
        logging.warning(f"Error generating DRC violation reports: {e}")

    with open(magic_drc_log_path) as f:
        log_content = f.read()

    if "was used but not defined." in log_content:
        logging.error(f"GDS is corrupt: cells used but not defined. See {magic_drc_log_path}")
        return False

    if 'Unrecognized layer (type) name "<<<<<\"' in log_content:
        logging.error(f"GDS is corrupt. See {magic_drc_log_path}")
        return False

    with open(design_magic_drc_file_path) as f:
        drc_content = f.read()

    if not _is_valid_magic_drc_report(drc_content):
        logging.error(f"Incomplete DRC report (possible OOM). See {magic_drc_log_path}")
        return False

    count = _violations_count(drc_content)
    if count == 0:
        logging.info("0 DRC violations")
        return True
    else:
        logging.error(f"{count} DRC violations")
        return False


class MagicDRC:
    __ref__ = "magic_drc"
    __surname__ = "Magic DRC"
    __supported_pdks__ = ["sky130A", "sky130B"]
    __supported_type__ = ["analog", "digital", "openframe", "mini"]
    __optional__ = True

    def __init__(self, precheck_config: dict, project_config: dict):
        self.precheck_config = precheck_config
        self.project_config = project_config
        self.gds_input_file_path = precheck_config["input_directory"] / f"gds/{project_config['user_module']}.gds"
        self.result = True

    def run(self) -> bool:
        if not self.gds_input_file_path.exists():
            logging.warning(f"{self.gds_input_file_path.name} not found")
            return False

        self.result = magic_gds_drc_check(
            self.gds_input_file_path,
            self.project_config["user_module"],
            self.precheck_config["pdk_path"],
            self.precheck_config["output_directory"],
        )
        return self.result
