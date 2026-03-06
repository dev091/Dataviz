from typing import Any


def deterministic_summary(question: str, rows: list[dict[str, Any]], metrics: list[str], dimensions: list[str]) -> str:
    if not rows:
        return "No records matched the question for the selected semantic model."

    metric = metrics[0] if metrics else "metric"
    dim = dimensions[0] if dimensions else None

    if dim and len(rows) > 1:
        top = max(rows, key=lambda row: row.get(metric) if isinstance(row.get(metric), (int, float)) else float("-inf"))
        return f"The query returned {len(rows)} rows. '{top.get(dim)}' is currently the leading segment for {metric}."

    value = rows[0].get(metric)
    return f"The query returned {len(rows)} rows. Current {metric} value is {value}."
