import csv
import xml.etree.ElementTree as ET


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def export_xml(rows):
    root = ET.Element("rows")
    for row in rows:
        item = ET.SubElement(root, "row")
        for key, value in row.items():
            ET.SubElement(item, key).text = value
    return ET.tostring(root, encoding="unicode")
