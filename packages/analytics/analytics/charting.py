from typing import Any


def recommend_chart(plan: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    dimensions = plan.get("dimensions", [])
    metrics = plan.get("metrics", [])

    if not rows:
        return {"type": "table", "title": "No results", "series": []}

    if len(metrics) == 1 and len(dimensions) == 1:
        dim = dimensions[0]
        metric = metrics[0]
        is_time = any(token in dim.lower() for token in ["date", "month", "week", "day", "quarter", "year"])
        chart_type = "line" if is_time else "bar"
        return {
            "type": chart_type,
            "x": dim,
            "y": metric,
            "series": [{"name": metric, "data": [[row.get(dim), row.get(metric)] for row in rows]}],
        }

    if len(metrics) == 1 and not dimensions:
        return {
            "type": "kpi",
            "metric": metrics[0],
            "value": rows[0].get(metrics[0]),
        }

    return {
        "type": "table",
        "columns": list(rows[0].keys()),
    }
