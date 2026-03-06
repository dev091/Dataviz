from typing import Any

import numpy as np


def _to_float(values: list[Any]) -> list[float]:
    numeric: list[float] = []
    for value in values:
        try:
            numeric.append(float(value))
        except (TypeError, ValueError):
            continue
    return numeric


def detect_insights(rows: list[dict[str, Any]], metrics: list[str], dimensions: list[str]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    if not rows or not metrics:
        return insights

    primary_metric = metrics[0]
    values = _to_float([row.get(primary_metric) for row in rows])
    if len(values) >= 5:
        avg = float(np.mean(values))
        std = float(np.std(values))
        if std > 0:
            z_scores = [(value - avg) / std for value in values]
            outlier_idx = [idx for idx, z in enumerate(z_scores) if abs(z) >= 2]
            if outlier_idx:
                insights.append(
                    {
                        "type": "anomaly",
                        "title": "Potential anomaly detected",
                        "body": f"{len(outlier_idx)} points deviate materially from the baseline in '{primary_metric}'.",
                        "data": {"indices": outlier_idx},
                    }
                )

        delta = values[-1] - values[0]
        direction = "up" if delta >= 0 else "down"
        pct = (delta / values[0] * 100) if values[0] else 0
        insights.append(
            {
                "type": "trend",
                "title": f"{primary_metric} trend is {direction}",
                "body": f"{primary_metric} moved {pct:.1f}% across the visible window.",
                "data": {"delta": delta, "percent": pct},
            }
        )

    if dimensions and len(rows) >= 3:
        dim = dimensions[0]
        ranked = sorted(rows, key=lambda r: (r.get(primary_metric) is None, r.get(primary_metric)), reverse=True)
        leaders = [r.get(dim) for r in ranked[:3]]
        insights.append(
            {
                "type": "rank",
                "title": "Top contributors",
                "body": "Top segments by the selected metric are: " + ", ".join(map(str, leaders)),
                "data": {"leaders": leaders},
            }
        )

    return insights
