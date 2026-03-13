from __future__ import annotations

from typing import Any


NUMERIC_SKIP_KEYS = {"x", "label", "widget", "series"}


def chart_rows_from_widget_config(widget_title: str, widget_config: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(widget_config, dict):
        return []

    chart = widget_config.get("chart")
    if not isinstance(chart, dict):
        return []

    if chart.get("type") == "table" and isinstance(chart.get("rows"), list):
        rows = chart.get("rows") or []
        return [row for row in rows[:10] if isinstance(row, dict)]

    if isinstance(chart.get("series"), list):
        flattened: list[dict[str, Any]] = []
        for series in chart.get("series", [])[:3]:
            if not isinstance(series, dict):
                continue
            series_name = str(series.get("name", widget_title))
            for point in series.get("data", [])[:10]:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    flattened.append(
                        {
                            "widget": widget_title,
                            "series": series_name,
                            "x": point[0],
                            "y": point[1],
                            "label": point[2] if len(point) > 2 else None,
                        }
                    )
        return flattened

    return []


def extract_numeric_value(row: dict[str, Any]) -> tuple[float | None, str | None]:
    if "y" in row and isinstance(row.get("y"), (int, float)):
        return float(row["y"]), str(row.get("label") or row.get("x") or row.get("series") or row.get("widget"))

    for key, value in row.items():
        if key in NUMERIC_SKIP_KEYS:
            continue
        if isinstance(value, (int, float)):
            label = str(row.get("label") or row.get("x") or key)
            return float(value), label
    return None, None


def build_exception_report_body(rows: list[dict[str, Any]], highlights: list[dict[str, Any]], title: str) -> str:
    scored_rows: list[tuple[float, str]] = []
    for row in rows:
        value, label = extract_numeric_value(row)
        if value is None:
            continue
        scored_rows.append((value, label or "Unlabeled segment"))

    if scored_rows:
        scored_rows.sort(key=lambda item: item[0])
        watchlist = ", ".join(f"{label} ({value:,.0f})" for value, label in scored_rows[:3])
        return f"{title} is focused on the lowest-performing segments in the current governed output: {watchlist}. Review the watchlist before cutover or distribution."

    if highlights:
        joined = " ".join(item["summary"] for item in highlights[:2])
        return f"{title} highlights the widgets that need executive follow-up. {joined}"

    return f"{title} is available, but there are not yet enough numeric signals to rank exception candidates automatically."
