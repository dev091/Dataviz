from collections import deque
from collections.abc import Mapping
import re
from typing import Any

from semantic.models import QueryPlan
from semantic.safety import is_safe_expression, is_safe_identifier


ALIAS_REF_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\.")
ALLOWED_JOIN_TYPES = {"left", "inner", "right", "full"}
ALLOWED_FILTER_OPS = {"=", "!=", ">", "<", ">=", "<=", "like", "ilike"}


def _extract_alias_refs(expression: str) -> set[str]:
    refs: set[str] = set()
    for match in ALIAS_REF_RE.finditer(expression):
        refs.add(match.group(1))
    return refs


def _literal_sql(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _resolve_join_steps(*, base_alias: str, required_aliases: set[str], joins: list[dict[str, str]]) -> list[tuple[dict[str, str], str, str]]:
    if not required_aliases:
        return []

    adjacency: dict[str, list[tuple[dict[str, str], str]]] = {}
    for spec in joins:
        left_alias = spec["left_alias"]
        right_alias = spec["right_alias"]
        adjacency.setdefault(left_alias, []).append((spec, right_alias))
        adjacency.setdefault(right_alias, []).append((spec, left_alias))

    if base_alias not in adjacency and required_aliases:
        raise ValueError("No join topology found for selected fields")

    included: set[tuple[str, str, str, str]] = set()
    joined: set[str] = {base_alias}
    steps: list[tuple[dict[str, str], str, str]] = []

    for target_alias in sorted(required_aliases):
        if target_alias in joined:
            continue

        queue: deque[str] = deque([base_alias])
        prev: dict[str, tuple[str, dict[str, str]] | None] = {base_alias: None}

        while queue and target_alias not in prev:
            node = queue.popleft()
            for spec, neighbor in adjacency.get(node, []):
                if neighbor not in prev:
                    prev[neighbor] = (node, spec)
                    queue.append(neighbor)

        if target_alias not in prev:
            raise ValueError(f"Unable to resolve join path from '{base_alias}' to '{target_alias}'")

        chain: list[tuple[dict[str, str], str, str]] = []
        cur = target_alias
        while prev[cur] is not None:
            parent, spec = prev[cur]
            chain.append((spec, parent, cur))
            cur = parent
        chain.reverse()

        for spec, from_alias, to_alias in chain:
            edge_key = (
                min(spec["left_alias"], spec["right_alias"]),
                max(spec["left_alias"], spec["right_alias"]),
                spec["left_field"],
                spec["right_field"],
            )
            if edge_key in included:
                joined.add(to_alias)
                continue
            steps.append((spec, from_alias, to_alias))
            included.add(edge_key)
            joined.add(to_alias)

    return steps


def build_sql(
    plan: QueryPlan,
    *,
    base_table: str,
    base_alias: str,
    metric_sql: Mapping[str, str],
    dimension_sql: Mapping[str, str],
    joins: list[dict[str, str]] | None = None,
) -> str:
    if not is_safe_identifier(base_table):
        raise ValueError("Unsafe base table")
    if not is_safe_identifier(base_alias):
        raise ValueError("Unsafe base alias")

    joins = joins or []

    selections: list[str] = []
    group_bys: list[str] = []
    where_clauses: list[str] = []

    expressions: list[str] = []

    for dim in plan.dimensions:
        expr = dimension_sql[dim]
        if not is_safe_expression(expr):
            raise ValueError(f"Unsafe dimension expression for '{dim}'")
        selections.append(f"{expr} AS {dim}")
        group_bys.append(expr)
        expressions.append(expr)

    for metric in plan.metrics:
        expr = metric_sql[metric]
        if not is_safe_expression(expr):
            raise ValueError(f"Unsafe metric expression for '{metric}'")
        selections.append(f"{expr} AS {metric}")
        expressions.append(expr)

    for f in plan.filters:
        operator = f.operator.lower()
        if operator not in ALLOWED_FILTER_OPS:
            raise ValueError(f"Unsafe filter operator '{f.operator}'")

        expr = dimension_sql.get(f.field)
        if not expr:
            raise ValueError(f"Filter field '{f.field}' not found in dimensions")
        if not is_safe_expression(expr):
            raise ValueError(f"Unsafe filter expression for '{f.field}'")

        where_clauses.append(f"{expr} {operator.upper()} {_literal_sql(f.value)}")
        expressions.append(expr)

    if not selections:
        raise ValueError("No selections in query plan")

    required_aliases: set[str] = set()
    for expr in expressions:
        required_aliases.update(alias for alias in _extract_alias_refs(expr) if alias != base_alias)

    join_steps = _resolve_join_steps(base_alias=base_alias, required_aliases=required_aliases, joins=joins)

    sql = f"SELECT {', '.join(selections)} FROM {base_table} AS {base_alias}"

    for spec, from_alias, to_alias in join_steps:
        join_type = spec.get("join_type", "left").lower()
        if join_type not in ALLOWED_JOIN_TYPES:
            raise ValueError(f"Unsupported join type '{join_type}'")

        left_alias = spec["left_alias"]
        right_alias = spec["right_alias"]
        left_field = spec["left_field"]
        right_field = spec["right_field"]

        for value in [left_alias, right_alias, from_alias, to_alias, left_field, right_field, spec["left_table"], spec["right_table"]]:
            if not is_safe_identifier(value):
                raise ValueError("Unsafe join identifier")

        if from_alias == left_alias and to_alias == right_alias:
            on_clause = f"{left_alias}.{left_field} = {right_alias}.{right_field}"
        elif from_alias == right_alias and to_alias == left_alias:
            on_clause = f"{right_alias}.{right_field} = {left_alias}.{left_field}"
        else:
            raise ValueError("Invalid join path orientation")

        sql += f" {join_type.upper()} JOIN {spec['right_table'] if to_alias == right_alias else spec['left_table']} AS {to_alias} ON {on_clause}"

    if where_clauses:
        sql += f" WHERE {' AND '.join(where_clauses)}"

    if group_bys:
        sql += f" GROUP BY {', '.join(group_bys)}"

    if plan.sort:
        order_parts = []
        for spec in plan.sort:
            direction = "ASC" if spec.direction == "asc" else "DESC"
            order_parts.append(f"{spec.field} {direction}")
        sql += f" ORDER BY {', '.join(order_parts)}"

    sql += f" LIMIT {int(plan.limit)}"
    return sql

