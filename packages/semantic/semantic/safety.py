import re

from semantic.models import QueryPlan


SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SAFE_EXPR = re.compile(r"^[A-Za-z0-9_\s\(\)\+\-\*\/,\.\'\"=:]+$")
SAFE_FILTER_OPS = {"=", "!=", ">", "<", ">=", "<=", "like", "ilike"}


def is_safe_identifier(value: str) -> bool:
    return bool(SAFE_IDENTIFIER.fullmatch(value))


def is_safe_expression(value: str) -> bool:
    return bool(SAFE_EXPR.fullmatch(value)) and ";" not in value and "--" not in value


def validate_plan(plan: QueryPlan, allowed_metrics: set[str], allowed_dimensions: set[str]) -> list[str]:
    errors: list[str] = []

    for metric in plan.metrics:
        if metric not in allowed_metrics:
            errors.append(f"Metric '{metric}' is not allowed")

    for dimension in plan.dimensions:
        if dimension not in allowed_dimensions:
            errors.append(f"Dimension '{dimension}' is not allowed")

    for sort in plan.sort:
        if sort.field not in allowed_metrics and sort.field not in allowed_dimensions:
            errors.append(f"Sort field '{sort.field}' is not allowed")

    for f in plan.filters:
        if f.field not in allowed_dimensions:
            errors.append(f"Filter field '{f.field}' must be a permitted dimension")
        if f.operator.lower() not in SAFE_FILTER_OPS:
            errors.append(f"Filter operator '{f.operator}' is not allowed")

    if plan.limit < 1 or plan.limit > 500:
        errors.append("Limit must be between 1 and 500")

    return errors
