import logging
import os
import subprocess
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent / "drc_scripts"


def klayout_gds_drc_check(
    check_name: str,
    drc_script_path: Path,
    gds_input_file_path: Path,
    output_directory: Path,
    klayout_cmd_extra_args: list[str] | None = None,
) -> bool:
    if klayout_cmd_extra_args is None:
        klayout_cmd_extra_args = []

    report_file_path = output_directory / "outputs/reports" / f"{check_name}_check.xml"
    logs_directory = output_directory / "logs"
    total_file_path = logs_directory / f"{check_name}_check.total"

    run_cmd = [
        "klayout", "-b", "-r", str(drc_script_path),
        "-rd", f"input={gds_input_file_path}",
        "-rd", f"topcell={gds_input_file_path.stem}",
        "-rd", f"report={report_file_path}",
        "-rd", f"thr={os.cpu_count()}",
    ]
    run_cmd.extend(klayout_cmd_extra_args)

    log_file_path = logs_directory / f"{check_name}_check.log"
    with open(log_file_path, "w") as log_f:
        logging.info(f"Running: {' '.join(str(x) for x in run_cmd)}")
        p = subprocess.run(run_cmd, stderr=log_f, stdout=log_f)
        if p.returncode != 0:
            logging.error(f"{check_name} failed (stat={p.returncode}), see {log_file_path}")
            return False

    try:
        with open(report_file_path) as f:
            size = os.fstat(f.fileno()).st_size
            if size == 0:
                logging.error(f"{check_name} produced empty report: {report_file_path.name}")
                return False
            drc_content = f.read()
            drc_count = drc_content.count("<item>")
            with open(total_file_path, "w") as tf:
                tf.write(str(drc_count))
            if drc_count == 0:
                logging.info("No DRC violations found")
                return True
            else:
                logging.error(f"{drc_count} DRC violations. See {report_file_path}")
                return False
    except FileNotFoundError as e:
        logging.error(f"{check_name} failed to generate report: {e}")
    except (IOError, OSError) as e:
        logging.error(f"{check_name} failed to write total: {e}")
    return False


class _KlayoutDRCBase:
    __ref__: str | None = None
    __surname__: str | None = None
    __supported_pdks__: list[str] | None = None
    __supported_type__ = ["analog", "digital", "openframe", "mini"]
    __optional__ = False

    def __init__(self, precheck_config: dict, project_config: dict):
        self.precheck_config = precheck_config
        self.project_config = project_config
        self.gds_input_file_path = precheck_config["input_directory"] / f"gds/{project_config['user_module']}.gds"
        self.drc_script_path: Path = Path()
        self.klayout_cmd_extra_args: list[str] = []
        self.result = True

    def _pdk_extra_args(self) -> list[str]:
        pdk = self.precheck_config["pdk_path"].stem
        if "gf180mcuC" in pdk:
            return ["-rd", "metal_top=9K", "-rd", "mim_option=B", "-rd", "metal_level=5LM", "-rd", "conn_drc=true"]
        if "gf180mcuD" in pdk:
            return [
                "-rd", "metal_top=11K", "-rd", "mim_option=B", "-rd", "metal_level=5LM",
                "-rd", "conn_drc=true", "-rd", "run_mode=deep", "-rd", "density=false",
                "-rd", "split_deep=false", "-rd", "slow_via=false",
            ]
        return []

    def run(self) -> bool:
        if not self.gds_input_file_path.exists():
            logging.warning(f"{self.gds_input_file_path.name} not found")
            return False
        self.result = klayout_gds_drc_check(
            self.__ref__, self.drc_script_path, self.gds_input_file_path,
            self.precheck_config["output_directory"], self.klayout_cmd_extra_args,
        )
        return self.result


class KlayoutFEOL(_KlayoutDRCBase):
    __ref__ = "klayout_feol"
    __surname__ = "Klayout FEOL"
    __supported_pdks__ = ["gf180mcuC", "gf180mcuD", "sky130A", "sky130B"]

    def __init__(self, precheck_config: dict, project_config: dict):
        super().__init__(precheck_config, project_config)
        self.drc_script_path = _SCRIPTS_DIR / f"{precheck_config['pdk_path'].stem}_mr.drc"
        self.klayout_cmd_extra_args = ["-rd", "feol=true"] + self._pdk_extra_args()


class KlayoutBEOL(_KlayoutDRCBase):
    __ref__ = "klayout_beol"
    __surname__ = "Klayout BEOL"
    __supported_pdks__ = ["gf180mcuC", "gf180mcuD", "sky130A", "sky130B"]

    def __init__(self, precheck_config: dict, project_config: dict):
        super().__init__(precheck_config, project_config)
        self.drc_script_path = _SCRIPTS_DIR / f"{precheck_config['pdk_path'].stem}_mr.drc"
        self.klayout_cmd_extra_args = ["-rd", "beol=true"] + self._pdk_extra_args()


class KlayoutOffgrid(_KlayoutDRCBase):
    __ref__ = "klayout_offgrid"
    __surname__ = "Klayout Offgrid"
    __supported_pdks__ = ["gf180mcuC", "gf180mcuD", "sky130A", "sky130B"]

    def __init__(self, precheck_config: dict, project_config: dict):
        super().__init__(precheck_config, project_config)
        self.drc_script_path = _SCRIPTS_DIR / f"{precheck_config['pdk_path'].stem}_mr.drc"
        self.klayout_cmd_extra_args = ["-rd", "offgrid=true"] + self._pdk_extra_args()


class KlayoutMetalMinimumClearAreaDensity(_KlayoutDRCBase):
    __ref__ = "klayout_met_min_ca_density"
    __surname__ = "Klayout Metal Density"
    __supported_pdks__ = ["gf180mcuC", "gf180mcuD", "sky130A", "sky130B"]

    def __init__(self, precheck_config: dict, project_config: dict):
        super().__init__(precheck_config, project_config)
        if "gf180mcu" in precheck_config["pdk_path"].stem:
            self.drc_script_path = _SCRIPTS_DIR / "gf180mcu_density.lydrc"
        else:
            self.drc_script_path = _SCRIPTS_DIR / "met_min_ca_density.lydrc"


class KlayoutPinLabelPurposesOverlappingDrawing(_KlayoutDRCBase):
    __ref__ = "klayout_pin_label_purposes_overlapping_drawing"
    __surname__ = "Klayout Pin Label"
    __supported_pdks__ = ["sky130A", "sky130B"]

    def __init__(self, precheck_config: dict, project_config: dict):
        super().__init__(precheck_config, project_config)
        self.drc_script_path = _SCRIPTS_DIR / "pin_label_purposes_overlapping_drawing.rb.drc"
        self.klayout_cmd_extra_args = ["-rd", f"top_cell_name={project_config['user_module']}"]


class KlayoutZeroArea(_KlayoutDRCBase):
    __ref__ = "klayout_zeroarea"
    __surname__ = "Klayout ZeroArea"
    __supported_pdks__ = ["sky130A", "sky130B"]

    def __init__(self, precheck_config: dict, project_config: dict):
        super().__init__(precheck_config, project_config)
        self.drc_script_path = _SCRIPTS_DIR / "zeroarea.rb.drc"
        cleaned_output = precheck_config["output_directory"] / "outputs" / f"{self.gds_input_file_path.stem}_no_zero_areas.gds"
        self.klayout_cmd_extra_args = ["-rd", f"cleaned_output={cleaned_output}"]
