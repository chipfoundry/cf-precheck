from pathlib import Path

from cf_precheck.config import run_be_check


def run_oeb(
    design_directory: Path,
    output_directory: Path,
    design_name: str,
    config_file: Path,
    pdk_root: Path,
    pdk: str,
) -> bool:
    return run_be_check(design_directory, output_directory, design_name, config_file, pdk_root, pdk, "OEB")


class Oeb:
    __ref__ = "oeb"
    __surname__ = "OEB"
    __supported_pdks__ = ["gf180mcuC", "gf180mcuD", "sky130A", "sky130B"]
    __supported_type__ = ["analog", "digital", "mini"]
    __optional__ = False

    def __init__(self, precheck_config: dict, project_config: dict):
        self.precheck_config = precheck_config
        self.project_config = project_config
        self.result = True

        proj_type = project_config["type"]
        type_to_design = {
            "analog": "user_analog_project_wrapper",
            "openframe": "openframe_project_wrapper",
            "mini": "user_project_wrapper_mini4",
        }
        self.design_name = type_to_design.get(proj_type, "user_project_wrapper")
        self.config_file = precheck_config["input_directory"] / f"lvs/{self.design_name}/lvs_config.json"
        self.pdk_root = precheck_config["pdk_path"].parent
        self.pdk = precheck_config["pdk_path"].name

    def run(self) -> bool:
        self.result = run_oeb(
            self.precheck_config["input_directory"],
            self.precheck_config["output_directory"],
            self.design_name,
            self.config_file,
            self.pdk_root,
            self.pdk,
        )
        return self.result
