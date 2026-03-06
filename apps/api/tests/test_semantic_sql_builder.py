from semantic.models import QueryFilter, QueryPlan, SortSpec
from semantic.sql_builder import build_sql


def test_build_sql_multi_join_chain() -> None:
    plan = QueryPlan(
        metrics=["revenue"],
        dimensions=["region"],
        filters=[QueryFilter(field="region", operator="=", value="North")],
        sort=[SortSpec(field="revenue", direction="desc")],
        limit=25,
    )

    sql = build_sql(
        plan,
        base_table="orders",
        base_alias="orders",
        metric_sql={"revenue": "SUM(orders.amount)"},
        dimension_sql={"region": "regions.name"},
        joins=[
            {
                "left_table": "orders",
                "right_table": "customers",
                "left_alias": "orders",
                "right_alias": "customers",
                "left_field": "customer_id",
                "right_field": "id",
                "join_type": "left",
            },
            {
                "left_table": "customers",
                "right_table": "regions",
                "left_alias": "customers",
                "right_alias": "regions",
                "left_field": "region_id",
                "right_field": "id",
                "join_type": "left",
            },
        ],
    )

    assert "FROM orders AS orders" in sql
    assert "LEFT JOIN customers AS customers ON orders.customer_id = customers.id" in sql
    assert "LEFT JOIN regions AS regions ON customers.region_id = regions.id" in sql
    assert "WHERE regions.name = 'North'" in sql
    assert "ORDER BY revenue DESC" in sql
    assert sql.endswith("LIMIT 25")


def test_build_sql_rejects_unsafe_filter_operator() -> None:
    plan = QueryPlan(
        metrics=["revenue"],
        dimensions=["region"],
        filters=[QueryFilter(field="region", operator="drop", value="North")],
    )

    try:
        build_sql(
            plan,
            base_table="orders",
            base_alias="orders",
            metric_sql={"revenue": "SUM(orders.amount)"},
            dimension_sql={"region": "orders.region"},
            joins=[],
        )
    except ValueError as exc:
        assert "Unsafe filter operator" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsafe filter operator")
