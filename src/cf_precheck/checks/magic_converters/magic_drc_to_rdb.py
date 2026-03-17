import logging
from pathlib import Path


def convert(input_file: Path, output_file: Path, data: bool = True, drc: bool = False) -> None:
    try:
        line_type = data
        with open(input_file) as fp, open(output_file, "w") as fpw:
            line = fp.readline()
            fpw.write(f"${line} 100\n")
            while line:
                line = fp.readline()
                if ("[INFO]" in line) or (len(line.strip()) == 0):
                    continue
                elif "------" in line:
                    line_type = not line_type
                elif line_type == drc:
                    drc_rule = line.strip().split("(")
                    drc_rule = [drc_rule, "UnknownRule"] if len(drc_rule) < 2 else drc_rule
                    fpw.write(f"r_0_{drc_rule[1][:-1]}\n")
                    fpw.write(f"Rule File Pathname: {input_file}\n")
                    fpw.write(f"{drc_rule[1][:-1]}: {drc_rule[0]}\n")
                    drc_number = 1
                elif line_type == data:
                    cord = [int(float(i)) * 100 for i in line.strip().split(" ")]
                    fpw.write(f"p {drc_number} 4\n")
                    fpw.write(f"{cord[0]} {cord[1]}\n")
                    fpw.write(f"{cord[2]} {cord[1]}\n")
                    fpw.write(f"{cord[2]} {cord[3]}\n")
                    fpw.write(f"{cord[0]} {cord[3]}\n")
                    drc_number += 1
    except IOError:
        logging.error(f"Magic DRC file not found: {input_file}")
    except Exception:
        logging.error("Failed to generate RDB file")
