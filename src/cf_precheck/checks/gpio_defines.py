import logging
import os
import re
from pathlib import Path
from pyverilog.vparser.parser import ParseError, parse

VAL_ILLEGAL = "13'hXXXX"
VAL_ILLEGAL_CF = VAL_ILLEGAL.casefold()

MODREX = re.compile(r"^__gpioModeObserve[0-9]+$")
WIRREX = re.compile(r"^USER_CONFIG_GPIO_([0-9]+)_INIT$")

_ASSETS_DIR = Path(__file__).parent / "verilog_assets"
PRE_V = [_ASSETS_DIR / "gpio_modes_base.v"]
POST_V = [_ASSETS_DIR / "gpio_modes_observe.v"]


def _run_gpio_defines_check(
    input_directory: Path,
    output_directory: Path,
    project_type: str,
    user_defines_v: Path,
    include_extras: list,
    precheck_config: dict,
) -> bool:
    errs = 0

    if "gf180mcu" in precheck_config["pdk_path"].stem:
        legalrex = re.compile(r"^10'[hH][0-9a-fA-F]+$")
    else:
        legalrex = re.compile(r"^13'[hH][0-9a-fA-F]+$")

    gpio_defines_report = output_directory / "outputs/reports/gpio_defines.report"
    user_defines_vf = input_directory / user_defines_v
    include_extras_vf = [input_directory / Path(f) for f in include_extras]

    if not user_defines_vf.is_file() or not os.access(str(user_defines_vf), os.R_OK):
        logging.warning(f"User defines file {user_defines_vf} not readable")
        errs += 1

    bad_files = [p for p in include_extras if not p.is_file() or not os.access(str(p), os.R_OK)]
    if bad_files:
        logging.warning(f"Include files not readable: {bad_files}")
        errs += len(bad_files)

    bad_assets = [p for p in [*PRE_V, *POST_V] if not p.is_file() or not os.access(str(p), os.R_OK)]
    if bad_assets:
        logging.warning(f"GPIO check asset files not readable: {bad_assets}")
        errs += len(bad_assets)

    if errs:
        logging.error(f"GPIO defines check failed due to {errs} error(s)")
        return False

    file_list = [*PRE_V, *include_extras_vf, user_defines_vf, *POST_V]
    logging.info(f"GPIO defines: parsing {user_defines_v}")

    try:
        ast, _ = parse(file_list)
    except ParseError as e:
        logging.warning(f"GPIO defines: parse failed: {e}")
        return False
    except RuntimeError as e:
        logging.warning(f"GPIO defines: parse failed: {e}")
        return False
    except Exception as e:
        logging.warning(f"GPIO defines: parse failed: {e}")
        return False

    mods = [d for d in ast.description.definitions if type(d).__name__ == "ModuleDef" and MODREX.match(d.name)]

    want = set(range(5, 38))
    if project_type == "analog":
        for i in range(14, 25):
            want.discard(i)

    ills = []
    valids = {}

    for d in mods:
        for i in d.items:
            if type(i).__name__ == "Decl" and len(i.list) == 2:
                i0, i1 = i.list[0], i.list[1]
                if type(i0).__name__ == "Wire" and type(i1).__name__ == "Assign":
                    match = WIRREX.match(i0.name)
                    if match:
                        windex = int(match.group(1))
                        if windex in want:
                            want.remove(windex)
                            val = "<error-unrecognized>"
                            try:
                                val = i1.right.var.value
                            except Exception:
                                try:
                                    val = str(i1.right.var)
                                except Exception:
                                    pass
                            if val.casefold() == VAL_ILLEGAL_CF or not legalrex.match(val):
                                ills.append(f"{i0.name}={val}")
                            else:
                                valids[windex] = [i0.name, val]

    msgs = []
    if want:
        miss_wires = [f"USER_CONFIG_GPIO_{i}_INIT" for i in want]
        msgs.append(f"Missing wires ({len(want)}): {' '.join(miss_wires)}")
    if ills:
        msgs.append(f"Invalid directives ({len(ills)}): {' '.join(ills)}")
    if msgs:
        logging.error(f"GPIO defines: {'; '.join(msgs)}")
        return False

    try:
        with open(gpio_defines_report, "w") as rpt:
            for i in range(5, 38):
                if i in valids:
                    rpt.write(f"{valids[i][0]:<26} {valids[i][1]}\n")
    except Exception as e:
        logging.error(f"GPIO defines: error writing report: {e}")
        return False

    logging.info(f"GPIO defines report: {gpio_defines_report}")
    return True


class GpioDefines:
    __ref__ = "gpio_defines"
    __surname__ = "GPIO Defines"
    __supported_pdks__ = ["gf180mcuC", "gf180mcuD", "sky130A", "sky130B"]
    __supported_type__ = ["analog", "digital"]
    __optional__ = False

    def __init__(self, precheck_config: dict, project_config: dict):
        self.precheck_config = precheck_config
        self.project_config = project_config
        self.result = True

    def run(self) -> bool:
        self.result = _run_gpio_defines_check(
            input_directory=self.precheck_config["input_directory"],
            output_directory=self.precheck_config["output_directory"],
            project_type=self.project_config["type"],
            user_defines_v=Path("verilog/rtl/user_defines.v"),
            include_extras=[],
            precheck_config=self.precheck_config,
        )
        return self.result
