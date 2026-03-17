import logging
import re
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from pathlib import Path


def _prettify(element: ET.Element) -> str:
    rough_string = ET.tostring(element, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="    ", newl="\n")


def _single_quote_between_category_tags(content: str) -> str:
    return re.sub("<category>(.*?)</category>", r"<category>'\1'</category>", content)


def convert(input_file: Path, output_file: Path, design_name: str) -> None:
    re_violation = re.compile(
        r"violation type: (?P<type>\S+)\s+"
        r"srcs: (?P<src1>\S+)( (?P<src2>\S+))?\s+"
        r"bbox = \( (?P<llx>\S+), (?P<lly>\S+) \)"
        r" - "
        r"\( (?P<urx>\S+), (?P<ury>\S+) \) "
        r"on Layer (?P<layer>\S+)",
        re.M,
    )

    with open(input_file) as fp, open(output_file, "w") as fpw:
        content = fp.read()
        count = 0
        vio_dict: dict = {}

        for match in re_violation.finditer(content):
            count += 1
            type_ = match.group("type")
            src1 = match.group("src1")
            src2 = match.group("src2")
            llx, lly = match.group("llx"), match.group("lly")
            urx, ury = match.group("urx"), match.group("ury")
            layer = match.group("layer")

            item = ET.Element("item")
            ET.SubElement(item, "category").text = type_
            ET.SubElement(item, "cell").text = design_name
            ET.SubElement(item, "visited").text = "false"
            ET.SubElement(item, "multiplicity").text = "1"
            values = ET.SubElement(item, "values")
            ET.SubElement(values, "value").text = f"box: ({llx},{lly};{urx},{ury})"
            ET.SubElement(values, "value").text = f"text: 'On layer {layer}'"
            srcs_text = f"text: 'Between {src1} {src2}'" if src2 else f"text: 'Between {src1}'"
            ET.SubElement(values, "value").text = srcs_text

            vio_dict.setdefault(type_, []).append(item)

        logging.info(f"Found {count} violations")

        report_database = ET.Element("report-database")
        categories = ET.SubElement(report_database, "categories")
        for type_ in vio_dict:
            category = ET.SubElement(categories, "category")
            ET.SubElement(category, "name").text = type_

        cells = ET.SubElement(report_database, "cells")
        cell = ET.SubElement(cells, "cell")
        ET.SubElement(cell, "name").text = design_name

        items = ET.Element("items")
        for vios in vio_dict.values():
            for item in vios:
                items.append(item)

        report_database.append(items)
        fpw.write(_single_quote_between_category_tags(_prettify(report_database)))
