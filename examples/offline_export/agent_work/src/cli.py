from exporter import export_xml, read_rows
from checksum import checksum_rows
from summary import summarize


def main(path="data/input.csv"):
    rows = read_rows(path)
    print(export_xml(rows))
    print(checksum_rows(rows))
    print(summarize(rows))


if __name__ == "__main__":
    main()
