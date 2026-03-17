import logging
from pathlib import Path

import pya


def run_metal_check(gds_file_path: Path) -> bool:
    layout = pya.Layout()
    layout.read(str(gds_file_path))
    for layer in layout.layer_indices():
        layer_info = layout.get_info(layer)
        if layer_info is not None:
            ld = f"{layer_info.layer}/{layer_info.datatype}"
            if ld in ("71/44", "72/20"):
                return False
    return True


class MetalCheck:
    __ref__ = "metalcheck"
    __surname__ = "Metal Check"
    __supported_pdks__ = ["sky130A", "sky130B"]
    __supported_type__ = ["mini"]
    __optional__ = False

    def __init__(self, precheck_config: dict, project_config: dict):
        self.precheck_config = precheck_config
        self.project_config = project_config
        self.gds_input_file_path = precheck_config["input_directory"] / f"gds/{project_config['user_module']}.gds"
        self.result = True

    def run(self) -> bool:
        self.result = run_metal_check(self.gds_input_file_path)
        return self.result
