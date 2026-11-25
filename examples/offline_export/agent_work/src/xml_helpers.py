import xml.etree.ElementTree as ET


def parse_xml(payload):
    return ET.fromstring(payload)
