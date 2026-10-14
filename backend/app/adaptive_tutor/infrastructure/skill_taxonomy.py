import re
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from app.adaptive_tutor.domain import SkillNode

_SPREADSHEET_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_HEADERS = {
    "Domain Tag": "domain_tag",
    "Skill ID": "skill_id",
    "Skill Name (English)": "name",
    "Sinhala Designation": "sinhala_designation",
    "Description / Scope": "description",
}


class XlsxSkillTaxonomyCatalog:
    """Read the authoritative Skill Nodes spreadsheet without copying its values into code."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> tuple[SkillNode, ...]:
        with ZipFile(self.path) as workbook:
            shared_strings = _read_shared_strings(workbook)
            worksheet = ElementTree.fromstring(
                workbook.read("xl/worksheets/sheet1.xml")
            )

        rows = [_read_row(row, shared_strings) for row in worksheet.findall(f".//{{{_SPREADSHEET_NAMESPACE}}}row")]
        header = next((row for row in rows if set(_HEADERS).issubset(row.values())), None)
        if header is None:
            raise ValueError("taxonomy spreadsheet is missing required columns")
        columns = {name: next(index for index, value in header.items() if value == name) for name in _HEADERS}

        nodes: list[SkillNode] = []
        for row in rows:
            skill_id = row.get(columns["Skill ID"], "").strip()
            if not skill_id or skill_id == "Skill ID":
                continue
            values = {field: row.get(columns[heading], "").strip() for heading, field in _HEADERS.items()}
            if not values["name"] or not values["description"]:
                raise ValueError(f"taxonomy skill {skill_id} is missing a name or description")
            nodes.append(SkillNode(**values))

        if not nodes:
            raise ValueError("taxonomy spreadsheet contains no skill nodes")
        if len({node.skill_id for node in nodes}) != len(nodes):
            raise ValueError("taxonomy spreadsheet contains duplicate skill IDs")
        return tuple(sorted(nodes, key=lambda node: node.skill_id))


def _read_shared_strings(workbook: ZipFile) -> tuple[str, ...]:
    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    return tuple(
        "".join(item.itertext())
        for item in root.findall(f"{{{_SPREADSHEET_NAMESPACE}}}si")
    )


def _read_row(row: ElementTree.Element, shared_strings: tuple[str, ...]) -> dict[int, str]:
    values: dict[int, str] = {}
    for cell in row.findall(f"{{{_SPREADSHEET_NAMESPACE}}}c"):
        reference = cell.get("r", "")
        column_match = re.match(r"[A-Z]+", reference)
        if column_match is None:
            continue
        column = _column_index(column_match.group())
        value = cell.find(f"{{{_SPREADSHEET_NAMESPACE}}}v")
        if value is None or value.text is None:
            values[column] = ""
        elif cell.get("t") == "s":
            values[column] = shared_strings[int(value.text)]
        else:
            values[column] = value.text
    return values


def _column_index(label: str) -> int:
    index = 0
    for character in label:
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1
