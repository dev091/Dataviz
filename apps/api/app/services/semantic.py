import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import CalculatedField, Dataset, SemanticDimension, SemanticMetric, SemanticModel


ALLOWED_AGG = {"sum", "avg", "count", "min", "max"}
ALLOWED_JOIN_TYPES = {"left", "inner", "right", "full"}
SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
AGG_EXPR_RE = re.compile(r"^(SUM|AVG|COUNT|MIN|MAX)\(\s*([A-Za-z_][A-Za-z0-9_]*|\*)\s*\)$", re.IGNORECASE)


def _safe_identifier(value: str) -> bool:
    return bool(SAFE_IDENTIFIER_RE.fullmatch(value))


def _normalize_alias(value: str) -> str:
    alias = re.sub(r"[^A-Za-z0-9_]", "_", value.lower().strip())
    alias = re.sub(r"_+", "_", alias).strip("_")
    if not alias:
        alias = "dataset"
    if alias[0].isdigit():
        alias = f"d_{alias}"
    return alias


def _qualified_dimension_expression(field_ref: str, base_alias: str) -> str:
    if "." in field_ref:
        return field_ref
    if _safe_identifier(field_ref):
        return f"{base_alias}.{field_ref}"
    return field_ref


def _qualified_metric_expression(formula: str, base_alias: str) -> str:
    if "." in formula:
        return formula

    if _safe_identifier(formula):
        return f"{base_alias}.{formula}"

    match = AGG_EXPR_RE.fullmatch(formula.strip())
    if not match:
        return formula

    agg, field = match.groups()
    if field == "*":
        return f"{agg.upper()}(*)"
    return f"{agg.upper()}({base_alias}.{field})"


def _build_alias_map(base_dataset: Dataset, datasets: list[Dataset]) -> dict[str, str]:
    alias_by_dataset: dict[str, str] = {}
    used: set[str] = set()

    def assign(dataset: Dataset) -> str:
        base_alias = _normalize_alias(dataset.name)
        alias = base_alias
        i = 2
        while alias in used:
            alias = f"{base_alias}_{i}"
            i += 1
        used.add(alias)
        alias_by_dataset[dataset.id] = alias
        return alias

    assign(base_dataset)
    for dataset in datasets:
        if dataset.id not in alias_by_dataset:
            assign(dataset)

    return alias_by_dataset


def validate_semantic_payload(
    *,
    base_dataset: Dataset | None,
    joins: list[dict],
    metrics: list[dict],
    dimensions: list[dict],
    calculated_fields: list[dict],
) -> list[str]:
    errors: list[str] = []
    if not base_dataset:
        errors.append("Base dataset not found")

    for join in joins:
        left_dataset_id = join.get("left_dataset_id")
        right_dataset_id = join.get("right_dataset_id")
        left_field = join.get("left_field")
        right_field = join.get("right_field")
        join_type = str(join.get("join_type", "left")).lower()

        if not left_dataset_id or not right_dataset_id:
            errors.append("Join must include left_dataset_id and right_dataset_id")
        if not left_field or not right_field:
            errors.append("Join must include left_field and right_field")
        if join_type not in ALLOWED_JOIN_TYPES:
            errors.append(f"Unsupported join_type '{join_type}'")

        for field_name, value in [("left_field", left_field), ("right_field", right_field)]:
            if value and not _safe_identifier(str(value)):
                errors.append(f"Unsafe join identifier '{field_name}'")

    metric_names = set()
    for metric in metrics:
        if metric["name"] in metric_names:
            errors.append(f"Duplicate metric name '{metric['name']}'")
        metric_names.add(metric["name"])

        agg = metric.get("aggregation", "sum").lower()
        if agg not in ALLOWED_AGG:
            errors.append(f"Unsupported aggregation '{agg}' for metric '{metric['name']}'")

        formula = metric.get("formula", "")
        if ";" in formula or "--" in formula:
            errors.append(f"Unsafe formula detected for metric '{metric['name']}'")

    dim_names = set()
    for dim in dimensions:
        if dim["name"] in dim_names:
            errors.append(f"Duplicate dimension name '{dim['name']}'")
        dim_names.add(dim["name"])

        field_ref = dim.get("field_ref", "")
        if ";" in field_ref or "--" in field_ref:
            errors.append(f"Unsafe field reference in dimension '{dim['name']}'")

    for calc in calculated_fields:
        expr = calc.get("expression", "")
        if ";" in expr or "--" in expr:
            errors.append(f"Unsafe expression in calculated field '{calc['name']}'")

    return errors


def create_semantic_model(
    db: Session,
    *,
    workspace_id: str,
    created_by: str,
    name: str,
    model_key: str,
    description: str | None,
    base_dataset_id: str,
    joins: list[dict],
    metrics: list[dict],
    dimensions: list[dict],
    calculated_fields: list[dict],
) -> SemanticModel:
    latest_version = (
        db.scalar(
            select(func.max(SemanticModel.version)).where(
                SemanticModel.workspace_id == workspace_id,
                SemanticModel.model_key == model_key,
            )
        )
        or 0
    )

    model = SemanticModel(
        workspace_id=workspace_id,
        created_by=created_by,
        name=name,
        model_key=model_key,
        description=description,
        version=latest_version + 1,
        is_active=True,
        base_dataset_id=base_dataset_id,
        joins=joins,
        definition={"status": "published"},
    )
    db.add(model)
    db.flush()

    for metric in metrics:
        db.add(
            SemanticMetric(
                semantic_model_id=model.id,
                name=metric["name"],
                label=metric["label"],
                formula=metric["formula"],
                aggregation=metric.get("aggregation", "sum"),
                value_format=metric.get("value_format"),
                visibility=metric.get("visibility", "public"),
            )
        )

    for dimension in dimensions:
        db.add(
            SemanticDimension(
                semantic_model_id=model.id,
                name=dimension["name"],
                label=dimension["label"],
                field_ref=dimension["field_ref"],
                data_type=dimension["data_type"],
                time_grain=dimension.get("time_grain"),
                visibility=dimension.get("visibility", "public"),
            )
        )

    for calc in calculated_fields:
        db.add(
            CalculatedField(
                semantic_model_id=model.id,
                name=calc["name"],
                expression=calc["expression"],
                data_type=calc["data_type"],
            )
        )

    db.flush()
    return model


def semantic_context(db: Session, semantic_model_id: str) -> dict:
    model = db.get(SemanticModel, semantic_model_id)
    if not model:
        raise ValueError("Semantic model not found")

    base_dataset = db.get(Dataset, model.base_dataset_id)
    if not base_dataset:
        raise ValueError("Base dataset not found")

    datasets = db.scalars(select(Dataset).where(Dataset.workspace_id == model.workspace_id)).all()
    dataset_by_id = {dataset.id: dataset for dataset in datasets}

    alias_by_dataset_id = _build_alias_map(base_dataset, datasets)
    base_alias = alias_by_dataset_id[base_dataset.id]

    joins: list[dict[str, str]] = []
    for join in model.joins:
        left_dataset_id = join.get("left_dataset_id")
        right_dataset_id = join.get("right_dataset_id")
        left_field = join.get("left_field")
        right_field = join.get("right_field")
        join_type = str(join.get("join_type", "left")).lower()

        if not left_dataset_id or not right_dataset_id or not left_field or not right_field:
            continue

        left_dataset = dataset_by_id.get(left_dataset_id)
        right_dataset = dataset_by_id.get(right_dataset_id)
        if not left_dataset or not right_dataset:
            continue

        left_alias = str(join.get("left_alias") or alias_by_dataset_id[left_dataset_id])
        right_alias = str(join.get("right_alias") or alias_by_dataset_id[right_dataset_id])

        joins.append(
            {
                "left_table": left_dataset.physical_table,
                "right_table": right_dataset.physical_table,
                "left_alias": left_alias,
                "right_alias": right_alias,
                "left_field": str(left_field),
                "right_field": str(right_field),
                "join_type": join_type,
            }
        )

    metrics = db.scalars(select(SemanticMetric).where(SemanticMetric.semantic_model_id == model.id)).all()
    dimensions = db.scalars(select(SemanticDimension).where(SemanticDimension.semantic_model_id == model.id)).all()

    metric_sql = {metric.name: _qualified_metric_expression(metric.formula, base_alias) for metric in metrics}
    dimension_sql = {dimension.name: _qualified_dimension_expression(dimension.field_ref, base_alias) for dimension in dimensions}

    return {
        "model": model,
        "dataset": base_dataset,
        "base_table": base_dataset.physical_table,
        "base_alias": base_alias,
        "joins": joins,
        "metrics": metrics,
        "dimensions": dimensions,
        "metric_sql": metric_sql,
        "dimension_sql": dimension_sql,
    }
