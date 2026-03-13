from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _labelize(value: str) -> str:
    cleaned = re.sub(r"[_\-.]+", " ", value).strip(" []")
    return re.sub(r"\s+", " ", cleaned).title() or "Field"


def _normalize_metric_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "metric"


def _extract_tableau_xml(content: bytes) -> ET.Element:
    try:
        return ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError("Unsupported Tableau workbook format") from exc


def _parse_tableau_workbook(filename: str, content: bytes) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    xml_bytes = content
    if suffix == ".twbx":
        with zipfile.ZipFile(BytesIO(content)) as archive:
            workbook_entry = next((name for name in archive.namelist() if name.lower().endswith(".twb")), None)
            if not workbook_entry:
                raise ValueError("Tableau packaged workbook does not contain a .twb definition")
            xml_bytes = archive.read(workbook_entry)

    root = _extract_tableau_xml(xml_bytes)
    workbook_name = root.attrib.get("name") or Path(filename).stem
    dashboards = _dedupe([node.attrib.get("name", "") for node in root.findall(".//dashboard")])
    worksheets = _dedupe([node.attrib.get("name", "") for node in root.findall(".//worksheet")])

    kpi_names: list[str] = []
    dimension_names: list[str] = []
    kpi_definitions: list[dict[str, Any]] = []

    for column in root.findall(".//column"):
        raw_name = str(column.attrib.get("caption") or column.attrib.get("name") or "").strip()
        if not raw_name:
            continue
        label = _labelize(raw_name)
        role = str(column.attrib.get("role") or "").lower()
        datatype = str(column.attrib.get("datatype") or "").lower()
        calc = column.find("calculation")
        formula = calc.attrib.get("formula") if calc is not None else None
        if role == "measure" or datatype in {"real", "integer", "float"}:
            kpi_names.append(label)
            kpi_definitions.append(
                {
                    "source_name": label,
                    "label": label,
                    "formula": formula,
                    "aggregation": "sum",
                    "value_format": None,
                    "description": f"Imported from Tableau workbook column {raw_name}.",
                }
            )
        elif role == "dimension" or datatype in {"string", "date", "datetime", "boolean"}:
            dimension_names.append(label)

    connection_types = _dedupe([node.attrib.get("class", "unknown") for node in root.findall(".//connection") if node.attrib.get("class") not in {None, "federated"}])
    connection_str = f" via {', '.join(connection_types)}" if connection_types else ""
    notes = f"Imported from Tableau workbook '{workbook_name}'{connection_str}."

    return {
        "source_tool": "tableau",
        "workbook_name": workbook_name,
        "dashboard_names": dashboards,
        "report_names": worksheets,
        "kpi_names": _dedupe(kpi_names),
        "dimension_names": _dedupe(dimension_names),
        "benchmark_rows": [],
        "kpi_definitions": kpi_definitions,
        "notes": notes,
    }


def _read_json_content(content: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(content.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Workbook import JSON is invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("Workbook import payload must be a JSON object")
    return payload


def _parse_json_bundle(filename: str, content: bytes, source_tool: str | None) -> dict[str, Any]:
    payload = _read_json_content(content)
    workbook_name = str(payload.get("workbook_name") or payload.get("name") or Path(filename).stem)
    inferred_tool = str(payload.get("source_tool") or source_tool or "generic")

    dashboards = payload.get("dashboard_names") or payload.get("dashboards") or payload.get("pages") or []
    reports = payload.get("report_names") or payload.get("reports") or payload.get("worksheets") or []
    raw_kpis = payload.get("kpi_definitions") or payload.get("kpis") or payload.get("measures") or []
    raw_dimensions = payload.get("dimension_names") or payload.get("dimensions") or []
    benchmark_rows = payload.get("benchmark_rows") or payload.get("benchmarks") or []

    kpi_names: list[str] = []
    kpi_definitions: list[dict[str, Any]] = []
    if isinstance(raw_kpis, list):
        for item in raw_kpis:
            if isinstance(item, str):
                label = _labelize(item)
                kpi_names.append(label)
                kpi_definitions.append(
                    {
                        "source_name": label,
                        "label": label,
                        "formula": None,
                        "aggregation": "sum",
                        "value_format": None,
                        "description": f"Imported from {inferred_tool} workbook manifest.",
                    }
                )
                continue
            if isinstance(item, dict):
                source_name = str(item.get("source_name") or item.get("name") or item.get("label") or "").strip()
                if not source_name:
                    continue
                label = str(item.get("label") or _labelize(source_name))
                kpi_names.append(label)
                kpi_definitions.append(
                    {
                        "source_name": label,
                        "label": label,
                        "formula": item.get("formula"),
                        "aggregation": str(item.get("aggregation") or "sum"),
                        "value_format": item.get("value_format"),
                        "description": item.get("description") or f"Imported from {inferred_tool} workbook manifest.",
                    }
                )

    dimension_names: list[str] = []
    if isinstance(raw_dimensions, list):
        for item in raw_dimensions:
            if isinstance(item, str):
                dimension_names.append(_labelize(item))
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("label") or "").strip()
                if name:
                    dimension_names.append(_labelize(name))

    notes = str(payload.get("notes") or f"Imported workbook metadata from {inferred_tool} bundle '{workbook_name}'.")
    return {
        "source_tool": inferred_tool,
        "workbook_name": workbook_name,
        "dashboard_names": _dedupe([_labelize(item) for item in dashboards if isinstance(item, str)]),
        "report_names": _dedupe([_labelize(item) for item in reports if isinstance(item, str)]),
        "kpi_names": _dedupe(kpi_names),
        "dimension_names": _dedupe(dimension_names),
        "benchmark_rows": benchmark_rows if isinstance(benchmark_rows, list) else [],
        "kpi_definitions": kpi_definitions,
        "notes": notes,
    }


def _parse_powerbi_template(filename: str, content: bytes) -> dict[str, Any]:
    workbook_name = Path(filename).stem
    dashboards: list[str] = []
    kpi_definitions: list[dict[str, Any]] = []
    dimension_names: list[str] = []

    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            if "Report/Layout" in archive.namelist():
                layout_bytes = archive.read("Report/Layout")
                # Sometimes it's UTF-16 LE
                layout_str = layout_bytes.decode("utf-16-le") if layout_bytes.startswith(b"\xff\xfe") else layout_bytes.decode("utf-8")
                layout = json.loads(layout_str)
                for section in layout.get("sections", []):
                    name = section.get("displayName")
                    if name:
                        dashboards.append(name)
            
            if "DataModelSchema" in archive.namelist():
                schema = json.loads(archive.read("DataModelSchema"))
                for table in schema.get("model", {}).get("tables", []):
                    for measure in table.get("measures", []):
                        name = measure.get("name")
                        if name:
                            kpi_definitions.append({
                                "source_name": name,
                                "label": _labelize(name),
                                "formula": measure.get("expression"),
                                "aggregation": "sum",
                                "value_format": measure.get("formatString"),
                                "description": measure.get("description") or f"DAX measure from {table.get('name')}",
                            })
                    for column in table.get("columns", []):
                        if column.get("type", "") != "rowNumber" and not column.get("isHidden"):
                            name = column.get("name")
                            if name:
                                dimension_names.append(_labelize(name))

    except Exception as exc: # noqa: BLE001
        raise ValueError(f"Failed to parse Power BI template: {exc}") from exc

    return {
        "source_tool": "power_bi",
        "workbook_name": workbook_name,
        "dashboard_names": _dedupe(dashboards),
        "report_names": [],
        "kpi_names": _dedupe([k["label"] for k in kpi_definitions]),
        "dimension_names": _dedupe(dimension_names),
        "benchmark_rows": [],
        "kpi_definitions": kpi_definitions,
        "notes": f"Extracted natively from Power BI template file '{filename}'.",
    }


def parse_workbook_bundle(filename: str, content: bytes, source_tool: str | None = None) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    if source_tool == "tableau" or suffix in {".twb", ".twbx"}:
        return _parse_tableau_workbook(filename, content)
    if source_tool == "power_bi" or suffix in {".pbit", ".pbip"}:
        # Try native ZIP extraction first for PBIT, fallback to JSON if it's not a zip
        try:
            return _parse_powerbi_template(filename, content)
        except (zipfile.BadZipFile, ValueError):
            return _parse_json_bundle(filename, content, "power_bi")
    if source_tool in {"domo", "generic", None} or suffix == ".json":
        return _parse_json_bundle(filename, content, source_tool)
    raise ValueError("Unsupported workbook import format")
