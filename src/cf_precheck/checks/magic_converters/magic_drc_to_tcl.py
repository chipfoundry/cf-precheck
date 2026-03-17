from pathlib import Path


def convert(input_file: Path, output_file: Path) -> None:
    split_line = "----------------------------------------"
    with open(input_file) as fp, open(output_file, "w") as fpw:
        drc_content = fp.read()
        if drc_content is not None:
            drc_sections = drc_content.split(split_line)
            if len(drc_sections) > 2:
                for i in range(1, len(drc_sections) - 1, 2):
                    vio_name = drc_sections[i].strip()
                    for vio in drc_sections[i + 1].split("\n"):
                        vio = "um ".join(vio.strip().split())
                        if len(vio):
                            fpw.write(f'box {vio}; feedback add "{vio_name}" medium\n')
