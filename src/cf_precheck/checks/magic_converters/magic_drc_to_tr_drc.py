import re
from pathlib import Path


def _cleanup(vio_type: str) -> str:
    replacements = {
        " ": "_", ">": "gt", "<": "lt", "=": "eq", "!": "not",
        "^": "pow", ".": "dot", "-": "_", "+": "plus", "(": "", ")": "",
    }
    for old, new in replacements.items():
        vio_type = vio_type.replace(old, new)
    return vio_type


def convert(input_file: Path, output_file: Path) -> None:
    split_line = "----------------------------------------"
    pattern = re.compile(r".*\s*\((\S+)\.?\s*[^\(\)]+\)")
    with open(input_file) as fp, open(output_file, "w") as fpw:
        drc_content = fp.read()
        if drc_content is not None:
            drc_sections = drc_content.split(split_line)
            if len(drc_sections) > 2:
                for i in range(1, len(drc_sections) - 1, 2):
                    vio_name = drc_sections[i].strip()
                    match = pattern.match(vio_name)
                    layer = match.group(1).split(".")[0] if match else "unknown"
                    prefix = f"  violation type: {_cleanup(vio_name)}\n    srcs: N/A N/A\n"
                    for vio in drc_sections[i + 1].split("\n"):
                        vio_cor = vio.strip().split()
                        if len(vio_cor) > 3:
                            fpw.write(f"{prefix}    bbox = ( {vio_cor[0]}, {vio_cor[1]} ) - ( {vio_cor[2]}, {vio_cor[3]} ) on Layer {layer}\n")
