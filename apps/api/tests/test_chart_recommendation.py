from analytics.charting import recommend_chart


def test_recommend_chart_prefers_funnel_for_pipeline_questions() -> None:
    plan = {"question": "show funnel conversion by stage", "metrics": ["revenue"], "dimensions": ["stage"]}
    rows = [
        {"stage": "Lead", "revenue": 120},
        {"stage": "Qualified", "revenue": 80},
        {"stage": "Won", "revenue": 35},
    ]

    chart = recommend_chart(plan, rows)

    assert chart["type"] == "funnel"


def test_recommend_chart_prefers_heatmap_for_two_dimensions() -> None:
    plan = {"question": "show a heatmap of sales by region and month", "metrics": ["sales"], "dimensions": ["region", "month"]}
    rows = [
        {"region": "North", "month": "Jan", "sales": 10},
        {"region": "North", "month": "Feb", "sales": 14},
        {"region": "South", "month": "Jan", "sales": 9},
    ]

    chart = recommend_chart(plan, rows)

    assert chart["type"] == "heatmap"
    assert chart["x_categories"] == ["North", "South"]
    assert chart["y_categories"] == ["Jan", "Feb"]


def test_recommend_chart_prefers_combo_for_two_metrics_over_time() -> None:
    plan = {"question": "compare revenue and cost by month", "metrics": ["revenue", "cost"], "dimensions": ["month"]}
    rows = [
        {"month": "2025-01", "revenue": 100, "cost": 60},
        {"month": "2025-02", "revenue": 120, "cost": 72},
    ]

    chart = recommend_chart(plan, rows)

    assert chart["type"] == "combo_line_bar"
    assert len(chart["series"]) == 2
