import json
import logging
import os
from pathlib import Path


def run_pdn(config_file: Path) -> bool:
    if not os.path.exists(config_file):
        logging.error(f"OpenLane configuration file {config_file} doesn't exist")
        return False

    with open(config_file) as f:
        data = json.load(f)

    if "FP_PDN_HPITCH" not in data or "FP_PDN_HPITCH_MULT" not in data:
        logging.error("FP_PDN_HPITCH or FP_PDN_HPITCH_MULT not defined in OpenLane configuration")
        return False

    if isinstance(data["FP_PDN_HPITCH_MULT"], str):
        logging.error("FP_PDN_HPITCH_MULT can't be a string")
        return False

    if data["FP_PDN_HPITCH"] != "expr::60 + $FP_PDN_HPITCH_MULT * 30":
        logging.error("FP_PDN_HPITCH has incorrect value, expected: expr::60 + $FP_PDN_HPITCH_MULT * 30")
        return False

    if data["FP_PDN_HPITCH_MULT"] < 0:
        logging.error("FP_PDN_HPITCH_MULT can't be negative")
        return False

    if not isinstance(data["FP_PDN_HPITCH_MULT"], int):
        logging.error("FP_PDN_HPITCH_MULT must be an integer")
        return False

    return True


class PDNMulti:
    __ref__ = "pdnmulti"
    __surname__ = "PDN Multi"
    __supported_pdks__ = ["gf180mcuC", "gf180mcuD"]
    __supported_type__ = ["digital"]
    __optional__ = False

    def __init__(self, precheck_config: dict, project_config: dict):
        self.precheck_config = precheck_config
        self.project_config = project_config
        self.config_file = precheck_config["input_directory"] / f"openlane/{project_config['user_module']}/config.json"
        self.result = True

    def run(self) -> bool:
        self.result = run_pdn(self.config_file)
        return self.result
