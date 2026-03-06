from semantic.models import QueryPlan, SortSpec


def heuristic_plan(question: str, metric_names: list[str], dimension_names: list[str]) -> QueryPlan:
    q = question.lower()

    metrics = [metric for metric in metric_names if metric.lower() in q]
    dimensions = [dimension for dimension in dimension_names if dimension.lower() in q]

    if not metrics and metric_names:
        metrics = [metric_names[0]]

    time_grain = None
    if "monthly" in q or "month" in q:
        time_grain = "month"
    elif "weekly" in q or "week" in q:
        time_grain = "week"
    elif "daily" in q or "day" in q:
        time_grain = "day"
    elif "quarter" in q:
        time_grain = "quarter"

    sort: list[SortSpec] = []
    if "top" in q and metrics:
        sort = [SortSpec(field=metrics[0], direction="desc")]

    limit = 10 if "top" in q else 50

    return QueryPlan(
        intent="trend" if time_grain else "comparison",
        metrics=metrics,
        dimensions=dimensions,
        time_grain=time_grain,
        sort=sort,
        limit=limit,
    )
