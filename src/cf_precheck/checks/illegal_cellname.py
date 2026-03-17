import logging
from pathlib import Path

import pya


def run_illegal_cellname_check(gds_input_file_path: Path) -> bool:
    layout = pya.Layout()
    layout.read(str(gds_input_file_path))
    search_chars = ["#", "/"]

    def search_subcells(cell, depth: int = 0) -> bool:
        match_found = False
        for instance in cell.each_inst():
            subcell = instance.cell
            for ch in search_chars:
                if ch in subcell.name:
                    logging.error(f"{'  ' * depth}Found '{ch}' in subcell: {subcell.name}")
                    match_found = True
            if not search_subcells(subcell, depth + 1):
                match_found = True
        return not match_found

    top_cell = layout.top_cell()
    return search_subcells(top_cell)


class IllegalCellnameCheck:
    __ref__ = "illegal_cellname_check"
    __surname__ = "Illegal Cellname"
    __supported_pdks__ = ["sky130A", "sky130B"]
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
        self.result = run_illegal_cellname_check(self.gds_input_file_path)
        return self.result
