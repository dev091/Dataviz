from typing import Any


COMPOSITION_HINTS = {"share", "mix", "composition", "split", "distribution", "contribution"}
FLOW_HINTS = {"funnel", "pipeline", "stage", "conversion", "drop-off", "dropoff"}
WATERFALL_HINTS = {"waterfall", "bridge", "variance"}
HEATMAP_HINTS = {"heatmap", "matrix"}
HIERARCHY_HINTS = {"tree", "treemap", "hierarchy"}
RELATIONSHIP_HINTS = {"correlation", "relationship", "versus", "vs", "compare"}


def _question(plan: dict[str, Any]) -> str:
    return str(plan.get("question", "")).lower()


def _contains_hint(question: str, hints: set[str]) -> bool:
    return any(hint in question for hint in hints)


def _is_time_dimension(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ["date", "month", "week", "day", "quarter", "year"])


def _ordered_unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        label = str(value)
        if label in seen:
            continue
        seen.add(label)
        ordered.append(label)
    return ordered


def recommend_chart(plan: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    dimensions = plan.get("dimensions", [])
    metrics = plan.get("metrics", [])
    question = _question(plan)

    if not rows:
        return {"type": "table", "title": "No results", "series": []}

    if len(metrics) == 1 and not dimensions:
        metric = metrics[0]
        return {
            "type": "kpi",
            "metric": metric,
            "value": rows[0].get(metric),
        }

    if len(metrics) == 1 and len(dimensions) == 1:
        dim = dimensions[0]
        metric = metrics[0]
        paired = [[row.get(dim), row.get(metric)] for row in rows]
        label_lengths = [len(str(row.get(dim, ""))) for row in rows]

        if _contains_hint(question, FLOW_HINTS):
            return {"type": "funnel", "series": [{"name": metric, "data": paired}]}

        if _contains_hint(question, WATERFALL_HINTS):
            return {"type": "waterfall", "series": [{"name": metric, "data": paired}]}

        if _contains_hint(question, HIERARCHY_HINTS):
            return {
                "type": "treemap",
                "nodes": [{"name": str(row.get(dim)), "value": row.get(metric)} for row in rows],
            }

        if _contains_hint(question, COMPOSITION_HINTS) and len(rows) <= 12:
            return {"type": "donut", "series": [{"name": metric, "data": paired}]}

        if _is_time_dimension(dim):
            return {"type": "line", "x": dim, "y": metric, "series": [{"name": metric, "data": paired}]}

        chart_type = "horizontal_bar" if max(label_lengths or [0]) > 12 or len(rows) > 7 else "bar"
        return {"type": chart_type, "x": dim, "y": metric, "series": [{"name": metric, "data": paired}]}

    if len(metrics) == 2 and len(dimensions) == 1:
        dim = dimensions[0]
        first_metric, second_metric = metrics[:2]

        if _is_time_dimension(dim):
            return {
                "type": "combo_line_bar",
                "series": [
                    {"name": first_metric, "data": [[row.get(dim), row.get(first_metric)] for row in rows]},
                    {"name": second_metric, "data": [[row.get(dim), row.get(second_metric)] for row in rows]},
                ],
            }

        if _contains_hint(question, RELATIONSHIP_HINTS):
            return {
                "type": "scatter",
                "x_metric": first_metric,
                "y_metric": second_metric,
                "series": [
                    {
                        "name": dim,
                        "data": [[row.get(first_metric), row.get(second_metric), str(row.get(dim))] for row in rows],
                    }
                ],
            }

        return {
            "type": "bar",
            "series": [
                {"name": first_metric, "data": [[row.get(dim), row.get(first_metric)] for row in rows]},
                {"name": second_metric, "data": [[row.get(dim), row.get(second_metric)] for row in rows]},
            ],
        }

    if len(metrics) == 1 and len(dimensions) >= 2:
        x_dim, y_dim = dimensions[:2]
        metric = metrics[0]
        x_categories = _ordered_unique([row.get(x_dim) for row in rows])
        y_categories = _ordered_unique([row.get(y_dim) for row in rows])

        if _contains_hint(question, HEATMAP_HINTS) or (len(x_categories) <= 12 and len(y_categories) <= 12):
            return {
                "type": "heatmap",
                "x_categories": x_categories,
                "y_categories": y_categories,
                "series": [
                    {
                        "name": metric,
                        "data": [[row.get(x_dim), row.get(y_dim), row.get(metric)] for row in rows],
                    }
                ],
            }

    return {
        "type": "table",
        "columns": list(rows[0].keys()),
        "rows": rows,
    }
