import logging
import subprocess
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent / "drc_scripts"


def run_spike_check(gds_input_file_path: Path, output_directory: Path, script_path: Path) -> bool:
    report_file_path = output_directory / "outputs/reports/spike_check.xml"
    logs_directory = output_directory / "logs"
    log_file_path = logs_directory / "spike_check.log"
    run_cmd = ["bash", str(script_path), "-V", "-m", str(report_file_path), str(gds_input_file_path)]

    with open(log_file_path, "w") as log_f:
        logging.info(f"Running: {' '.join(str(x) for x in run_cmd)}")
        p = subprocess.run(run_cmd, stderr=log_f, stdout=log_f)
        if p.returncode != 0:
            logging.error(f"Spike check failed (stat={p.returncode}), see {log_file_path}")
            return False
        logging.info("No spikes found")
        return True


class SpikeCheck:
    __ref__ = "spike_check"
    __surname__ = "Spike Check"
    __supported_pdks__ = ["gf180mcuC", "gf180mcuD", "sky130A", "sky130B"]
    __supported_type__ = ["analog", "digital", "openframe", "mini"]
    __optional__ = False

    def __init__(self, precheck_config: dict, project_config: dict):
        self.precheck_config = precheck_config
        self.project_config = project_config
        self.script_path = _SCRIPTS_DIR / "gdsArea0"
        self.gds_input_file_path = precheck_config["input_directory"] / f"gds/{project_config['user_module']}.gds"
        self.result = True

    def run(self) -> bool:
        if not self.gds_input_file_path.exists():
            logging.warning(f"{self.gds_input_file_path.name} not found")
            return False
        self.result = run_spike_check(self.gds_input_file_path, self.precheck_config["output_directory"], self.script_path)
        return self.result
