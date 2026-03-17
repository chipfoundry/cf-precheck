import logging
from pathlib import Path

import pya


def check_top_cells(gds_file: Path) -> bool:
    layout = pya.Layout()
    layout.read(str(gds_file))
    top_cells = list(layout.top_cells())
    if len(top_cells) == 0:
        logging.error("No top cell found in the GDS layout")
        return False
    elif len(top_cells) > 1:
        names = [cell.name for cell in top_cells]
        logging.error(f"Multiple top cells found in the GDS layout: {names}")
        return False
    logging.info(f"Single top cell '{top_cells[0].name}' found")
    return True


class TopcellCheck:
    __ref__ = "topcell_check"
    __surname__ = "Top Cell"
    __supported_pdks__ = ["gf180mcuC", "gf180mcuD", "sky130A", "sky130B"]
    __supported_type__ = ["analog", "digital", "openframe", "mini"]
    __optional__ = False

    def __init__(self, precheck_config: dict, project_config: dict):
        self.precheck_config = precheck_config
        self.project_config = project_config
        self.gds_input_file_path = precheck_config["input_directory"] / f"gds/{project_config['user_module']}.gds"
        self.result = True

    def run(self) -> bool:
        if not self.gds_input_file_path.exists():
            logging.warning(f"{self.gds_input_file_path.name} not found")
            return False
        self.result = check_top_cells(self.gds_input_file_path)
        return self.result
